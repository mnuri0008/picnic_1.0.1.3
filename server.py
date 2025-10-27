import os, secrets, smtplib, ssl
from datetime import datetime
from email.message import EmailMessage
from hashlib import sha256
from flask import Flask, request, redirect, make_response, render_template, jsonify, url_for, abort, flash
from models import init_db, SessionLocal, User, Session, OTP, Room, Item
from sqlalchemy.exc import IntegrityError
from email_validator import validate_email, EmailNotValidError

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

init_db()

def now(): return datetime.utcnow()
def hash_pw(p): return sha256((p + os.environ.get("PW_SALT","salt")).encode()).hexdigest()
def gen_token(): return secrets.token_urlsafe(32)
def get_lang(): return request.args.get("lang") or request.cookies.get("lang") or "tr"

def t(key):
    lang = get_lang()
    TR = {"login_title":"Giriş Yap","email":"E-Posta","password":"Şifre","login":"Giriş",
          "register":"Kayıt Ol","forgot":"Şifremi Unuttum","logout":"Çıkış","send_code":"Kod Gönder",
          "reset_pass":"Şifreyi Sıfırla","otp_code":"Doğrulama Kodu","username":"Kullanıcı Adı",
          "home_title":"Piknik Vakti"}
    EN = {"login_title":"Sign In","email":"Email","password":"Password","login":"Login",
          "register":"Sign Up","forgot":"Forgot Password","logout":"Logout","send_code":"Send Code",
          "reset_pass":"Reset Password","otp_code":"OTP Code","username":"Username",
          "home_title":"Picnic Time"}
    return (TR if lang=='tr' else EN).get(key,key)

def template_links():
    ep = request.endpoint or "home"
    args = dict(request.view_args or {})
    args.update(request.args.to_dict(flat=True))
    args.pop("lang", None)
    tr_link = url_for(ep, **args, lang="tr")
    en_link = url_for(ep, **args, lang="en")
    return tr_link, en_link

def current_user():
    token = request.cookies.get("session")
    if not token: return None
    db = SessionLocal()
    sess = db.query(Session).filter(Session.token==token, Session.expires_at > now()).first()
    if not sess: 
        db.close(); return None
    user = db.query(User).get(sess.user_id)
    db.close()
    return user

def send_email(to_email, subject, body):
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT","587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    if not all([smtp_host,smtp_user,smtp_pass]):
        app.logger.warning("SMTP creds missing; email printed to logs.")
        app.logger.info(f"TO:{to_email}\nSUBJECT:{subject}\n{body}")
        return False
    msg = EmailMessage()
    msg["From"] = smtp_user; msg["To"] = to_email; msg["Subject"] = subject
    msg.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls(context=context); s.login(smtp_user, smtp_pass); s.send_message(msg)
    return True

@app.get("/")
def home():
    user = current_user()
    if not user: return redirect(url_for("login", lang=get_lang()))
    tr_link, en_link = template_links()
    resp = make_response(render_template("index.html", t=t, lang=get_lang(), tr_link=tr_link, en_link=en_link, user=user))
    resp.set_cookie("lang", get_lang(), max_age=31536000)
    return resp

@app.get("/auth/login")
def login():
    tr_link, en_link = template_links()
    return render_template("login.html", t=t, lang=get_lang(), tr_link=tr_link, en_link=en_link)

@app.post("/auth/login")
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    pw = request.form.get("password") or ""
    try:
        validate_email(email)
    except EmailNotValidError:
        flash("Geçerli bir e-posta girin."); return redirect(url_for("login", lang=get_lang()))
    db = SessionLocal()
    user = db.query(User).filter(User.email==email).first()
    if not user or user.password_hash != hash_pw(pw):
        db.close(); flash("E-posta veya şifre hatalı."); return redirect(url_for("login", lang=get_lang()))
    token = gen_token(); sess = Session(user_id=user.id, token=token)
    db.add(sess); db.commit(); db.close()
    resp = make_response(redirect(url_for("home", lang=get_lang())))
    resp.set_cookie("session", token, max_age=864000, httponly=True, samesite="Lax")
    return resp

@app.get("/auth/register")
def register():
    tr_link, en_link = template_links()
    return render_template("register.html", t=t, lang=get_lang(), tr_link=tr_link, en_link=en_link)

@app.post("/auth/register")
def register_post():
    email = (request.form.get("email") or "").strip().lower()
    username = (request.form.get("username") or "").strip()
    pw = request.form.get("password") or ""
    try:
        validate_email(email)
    except EmailNotValidError:
        flash("Geçerli bir e-posta girin."); return redirect(url_for("register", lang=get_lang()))
    if len(pw) < 6: flash("Şifre en az 6 karakter."); return redirect(url_for("register", lang=get_lang()))
    db = SessionLocal()
    try:
        u = User(email=email, username=username, password_hash=hash_pw(pw))
        db.add(u); db.commit()
    except IntegrityError:
        db.rollback(); db.close(); flash("Bu e-posta kayıtlı."); return redirect(url_for("register", lang=get_lang()))
    db.close(); flash("Kayıt başarılı."); return redirect(url_for("login", lang=get_lang()))

@app.get("/auth/forgot")
def forgot():
    tr_link, en_link = template_links()
    return render_template("forgot.html", t=t, lang=get_lang(), tr_link=tr_link, en_link=en_link)

@app.post("/auth/forgot")
def forgot_post():
    email = (request.form.get("email") or "").strip().lower()
    try:
        validate_email(email)
    except EmailNotValidError:
        flash("Geçerli bir e-posta girin."); return redirect(url_for("forgot", lang=get_lang()))
    import secrets
    code = f"{secrets.randbelow(10000):04d}"
    db = SessionLocal()
    db.add(OTP(email=email, code=code, purpose="reset")); db.commit(); db.close()
    sent = send_email(email, "Piknik Vakti Şifre Kodu", f"Kodunuz: {code} (10 dk geçerli)")
    if not sent: flash("SMTP ayarlanmadı; kod loglara yazıldı.")
    return redirect(url_for("verify_otp", email=email, lang=get_lang()))

@app.get("/auth/verify")
def verify_otp():
    tr_link, en_link = template_links()
    return render_template("verify.html", t=t, lang=get_lang(), tr_link=tr_link, en_link=en_link, email=request.args.get("email",""))

@app.post("/auth/verify")
def verify_otp_post():
    email = (request.form.get("email") or "").strip().lower()
    code = (request.form.get("code") or "").strip()
    new_pw = request.form.get("new_password") or ""
    db = SessionLocal()
    rec = db.query(OTP).filter(OTP.email==email, OTP.code==code, OTP.purpose=="reset", OTP.expires_at > datetime.utcnow()).first()
    if not rec:
        db.close(); flash("Kod geçersiz/süresi dolmuş."); return redirect(url_for("verify_otp", email=email, lang=get_lang()))
    user = db.query(User).filter(User.email==email).first()
    if not user:
        db.close(); flash("Kullanıcı yok."); return redirect(url_for("register", lang=get_lang()))
    if len(new_pw) < 6:
        db.close(); flash("Yeni şifre en az 6 karakter."); return redirect(url_for("verify_otp", email=email, lang=get_lang()))
    user.password_hash = hash_pw(new_pw)
    db.delete(rec); db.commit(); db.close()
    flash("Şifre güncellendi."); return redirect(url_for("login", lang=get_lang()))

@app.get("/logout")
def logout():
    resp = make_response(redirect(url_for("login", lang=get_lang()))); resp.delete_cookie("session"); return resp

@app.get("/room/<code>")
def room(code):
    user = current_user()
    if not user: return redirect(url_for("login", lang=get_lang()))
    tr_link, en_link = template_links()
    return render_template("room.html", t=t, lang=get_lang(), tr_link=tr_link, en_link=en_link, code=code, user=user)

@app.get("/api/room/<code>")
def api_room(code):
    db = SessionLocal()
    room = db.query(Room).filter(Room.code==code).first()
    if not room:
        room = Room(code=code, owner="system")
        db.add(room); db.commit()
    items = db.query(Item).filter(Item.room_id==room.id).all()
    out = [{"id":i.id,"name":i.name,"unit":i.unit,"amount":i.amount,"cat":i.cat,"who":i.who,"state":i.state} for i in items]
    db.close()
    return jsonify({"ok":True,"items":out})

@app.post("/api/room/<code>/add")
def api_add(code):
    db = SessionLocal()
    room = db.query(Room).filter(Room.code==code).first()
    if not room:
        room = Room(code=code, owner="system")
        db.add(room); db.commit()
    data = request.json or {}
    it = Item(room_id=room.id, name=data.get("name","Ürün"), amount=str(data.get("amount","1")))
    db.add(it); db.commit(); db.close()
    return jsonify({"ok":True})

@app.get("/service-worker.js")
def sw():
    from flask import Response
    js = open(os.path.join("static","service-worker.js")).read()
    return Response(js, mimetype="application/javascript")

@app.get("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
