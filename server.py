from flask import Flask, render_template, request, jsonify, abort, send_from_directory, make_response
from datetime import datetime, timedelta
import threading, itertools

# Flask yapılandırması
app = Flask(
    __name__,
    static_folder='static',
    static_url_path='/static',
    template_folder='templates'
)

# ===== Basic Auth (Session) =====
from flask import session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import json, os

app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
USERS_DB = os.path.join(os.path.dirname(__file__), "data", "users.json")

def _load_users():
    try:
        with open(USERS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_users(users):
    os.makedirs(os.path.dirname(USERS_DB), exist_ok=True)
    with open(USERS_DB, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def current_user():
    return session.get("user")

# Login wall for main screens
@app.before_request
def _auth_wall():
    open_paths = {
        "icon_192","icon_512","picnic_icon_192","picnic_icon_512",
        "manifest","service_worker","asset_links",
        "login","register","forgot","do_login","do_register","do_forgot"
    }
    # allow static and api endpoints that might be used pre-login for health
    if request.endpoint and (request.endpoint.startswith("static") or request.endpoint in open_paths):
        return
    # allow API for now; to hard-lock add: if request.path.startswith("/api/"): ...
    if request.path.startswith("/auth/"):
        return
    if request.path.startswith("/.well-known"):
        return
    # wall only for index and room
    if request.path.startswith("/room") or request.path == "/":
        if not current_user():
            return redirect(url_for("login"))

# Auth routes
@app.route("/auth/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("auth_login.html", error=None)
    data = request.form
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    users = _load_users()
    u = users.get(username)
    if not u or not check_password_hash(u["pw"], password):
        return render_template("auth_login.html", error="Kullanıcı adı veya şifre hatalı.")
    session["user"] = username
    return redirect(url_for("index")) if "index" in app.view_functions else redirect("/")

@app.route("/auth/register", methods=["GET","POST"])
def register():
    if request.method == "GET":
        return render_template("auth_register.html", error=None)
    data = request.form
    username = (data.get("username") or "").strip().lower()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return render_template("auth_register.html", error="Kullanıcı adı ve şifre gerekli.")
    users = _load_users()
    if username in users:
        return render_template("auth_register.html", error="Bu kullanıcı adı zaten kayıtlı.")
    users[username] = {"email": email, "pw": generate_password_hash(password)}
    _save_users(users)
    session["user"] = username
    return redirect(url_for("index")) if "index" in app.view_functions else redirect("/")


import os, smtplib, datetime
from email.message import EmailMessage

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER or "no-reply@example.com")

def _send_reset_code_via_email(to_email, code):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        print("SMTP not configured; skipping send to", to_email)
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = "Piknik Vakti - Şifre Sıfırlama Kodu"
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg.set_content(f"Şifre sıfırlama kodunuz: {code}\nBu kod 15 dakika içinde geçerlidir.")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print("Failed sending SMTP:", e)
        return False


@app.route("/auth/forgot", methods=["GET","POST"])
def forgot():
    # Dual-mode: POST without 'code' sends code to user's email if available.
    # POST with 'code' attempts verification and password reset.
    if request.method == "GET":
        return render_template("auth_forgot.html", error=None, ok=None)
    data = request.form
    username = (data.get("username") or "").strip().lower()
    users = _load_users()
    if not username or username not in users:
        return render_template("auth_forgot.html", error="Kullanıcı bulunamadı.", ok=None)
    user = users[username]
    # If form contains 'code' -> verify and set new password
    code = data.get("code")
    new_password = data.get("new_password") or ""
    # verify mode
    if code:
        token_info = user.get("reset_token")
        if not token_info or token_info.get("code") != code:
            return render_template("auth_forgot.html", error="Kod hatalı veya süresi dolmuş.", ok=None)
        # check expiry
        exp = datetime.datetime.fromisoformat(token_info.get("expires"))
        if datetime.datetime.utcnow() > exp:
            return render_template("auth_forgot.html", error="Kodun süresi dolmuş.", ok=None)
        if not new_password:
            return render_template("auth_forgot.html", error="Yeni şifre girin.", ok=None)
        users[username]["pw"] = generate_password_hash(new_password)
        users[username"].pop("reset_token", None)
        _save_users(users)
        return render_template("auth_forgot.html", error=None, ok="Şifre güncellendi. Giriş yapabilirsiniz.")
    # send code mode
    # require email exists
    email = user.get("email")
    if not email:
        return render_template("auth_forgot.html", error="Kullanıcıda e-posta yok. Kayıtlı e-posta gereklidir.", ok=None)
    # generate code and store with expiry
    code = secrets.token_hex(3).upper()  # 6 hex chars
    users[username]["reset_token"] = {"code": code, "expires": (datetime.datetime.utcnow() + datetime.timedelta(minutes=15)).isoformat()}
    _save_users(users)
    sent = _send_reset_code_via_email(email, code)
    if sent:
        return render_template("auth_forgot.html", error=None, ok="Kod gönderildi. E‑postanızı kontrol edin.")
    else:
        return render_template("auth_forgot.html", error="E‑posta gönderilemedi; sunucu yapılandırmasını kontrol edin.", ok=None)

# ===== End Basic Auth =====