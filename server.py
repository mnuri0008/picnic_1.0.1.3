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

@app.route("/auth/forgot", methods=["GET","POST"])
def forgot():
    if request.method == "GET":
        return render_template("auth_forgot.html", error=None, ok=None)
    data = request.form
    username = (data.get("username") or "").strip().lower()
    new_password = data.get("new_password") or ""
    users = _load_users()
    if username not in users:
        return render_template("auth_forgot.html", error="Kullanıcı bulunamadı.", ok=None)
    users[username]["pw"] = generate_password_hash(new_password)
    _save_users(users)
    return render_template("auth_forgot.html", error=None, ok="Şifre güncellendi, giriş yapabilirsiniz.")

@app.route("/auth/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
# ===== End Basic Auth =====


# ------- ICON ALIASES (PWABuilder veya Play isteği 200 dönsün) -------
@app.route("/static/icons/icon-192.png")
def icon_192():
    return send_from_directory("static/icons", "icon-192.png", mimetype="image/png")

@app.route("/static/icons/icon-512.png")
def icon_512():
    return send_from_directory("static/icons", "icon-512.png", mimetype="image/png")

@app.route("/static/icons/picnic-icon-192.png")
def picnic_icon_192():
    return send_from_directory("static/icons", "icon-192.png", mimetype="image/png")

@app.route("/static/icons/picnic-icon-512.png")
def picnic_icon_512():
    return send_from_directory("static/icons", "icon-512.png", mimetype="image/png")

# ------- PWA DOSYALARI (manifest + service worker) -------
@app.route('/manifest.json')
def manifest():
    resp = make_response(send_from_directory('static', 'manifest.json'))
    resp.mimetype = 'application/manifest+json'
    resp.headers['Cache-Control'] = 'no-store, max-age=0'
    return resp

@app.route('/service-worker.js')
def service_worker():
    resp = make_response(send_from_directory(app.static_folder, 'service-worker.js'))
    resp.mimetype = 'application/javascript'
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp

# ------- Digital Asset Links (TWA doğrulaması) -------
@app.route('/.well-known/assetlinks.json')
def assetlinks():
    return send_from_directory('static/.well-known', 'assetlinks.json', mimetype='application/json')


# -------------------- APP LOGIC --------------------
ROOMS = {}  # code -> {"owner": str, "date": str(ISO minutes), "items":[{...}]}
IDGEN = itertools.count(1)
LOCK = threading.Lock()

def mask(code: str) -> str:
    code = str(code or "")
    return f"{code[:2]}**" if len(code) >= 2 else (code + "*")

def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="minutes")

def _as_dt(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '')).replace(second=0, microsecond=0)
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M")
        except Exception:
            return None


# ---------- SAYFALAR ----------
@app.route("/")
def home():
    lang = request.args.get("lang", "tr")
    now = datetime.utcnow()

    with LOCK:
        to_delete = []
        for code, r in list(ROOMS.items()):
            d = _as_dt(r.get("date") or "")
            if d and now > d + timedelta(days=10):
                to_delete.append(code)
        for c in to_delete:
            ROOMS.pop(c, None)

        rooms = []
        for code, r in ROOMS.items():
            d_str = r.get("date") or ""
            d_dt = _as_dt(d_str) or datetime.min
            rooms.append({
                "code": code,
                "date": d_str,
                "items": len(r.get("items", [])),
                "mask": mask(code),
                "_sort": d_dt
            })

    rooms.sort(key=lambda x: x["_sort"], reverse=True)
    for r in rooms:
        r.pop("_sort", None)

    return render_template("index.html", rooms=rooms, lang=lang)


@app.route("/room/<code>")
def room(code):
    username = request.args.get("username", "guest")
    lang = request.args.get("lang", "tr")
    view = request.args.get("view") == "1"
    return render_template("room.html", code=code, username=username, lang=lang, view=view)


# ---------- API ----------
@app.post("/api/room")
def api_create_room():
    data = request.get_json(force=True) or {}
    code = str(data.get("code", "")).strip()
    if not code:
        abort(400, description="code required")
    owner = (data.get("owner") or "").strip()
    date  = (data.get("date") or now_iso())[:16]
    with LOCK:
        ROOMS.setdefault(code, {"owner": owner, "date": date, "items": []})
    return "", 201

@app.get("/api/rooms")
def api_rooms():
    with LOCK:
        out = []
        for c, r in ROOMS.items():
            out.append({
                "code": c,
                "mask": mask(c),
                "date": r.get("date"),
                "items": len(r.get("items", []))
            })
    return jsonify(out)

@app.get("/api/room/<code>")
def api_room(code):
    with LOCK:
        r = ROOMS.setdefault(str(code), {"owner": "", "date": now_iso(), "items": []})
        return jsonify(r)

@app.post("/api/room/<code>/items")
def api_add_item(code):
    data = request.get_json(force=True) or {}
    name   = (data.get("name") or "").strip()
    unit   = (data.get("unit") or "").strip()
    amount = data.get("amount", 0)
    try:
        amount = float(amount)
    except Exception:
        abort(400, description="amount must be a number")
    cat    = (data.get("cat") or "Diğer").strip()
    user   = (data.get("user") or "").strip()

    if not name or not unit or not user:
        abort(400, description="name, unit and user are required")

    with LOCK:
        r = ROOMS.setdefault(str(code), {"owner": "", "date": now_iso(), "items": []})
        item = {
            "id": next(IDGEN),
            "name": name,
            "unit": unit,
            "amount": amount,
            "cat": cat,
            "user": user,
            "state": "needed"
        }
        r["items"].append(item)
    return "", 201

@app.patch("/api/room/<code>/items/<int:item_id>")
def api_patch_item(code, item_id):
    data = request.get_json(force=True) or {}
    user  = data.get("user", "")
    state = data.get("state", "needed")
    with LOCK:
        r = ROOMS.get(str(code))
        if not r:
            abort(404)
        owner = r.get("owner", "")
        for it in r.get("items", []):
            if it["id"] == item_id:
                if user != it["user"] and user != owner:
                    abort(403)
                it["state"] = state
                return "", 204
    abort(404)

@app.delete("/api/room/<code>/items/<int:item_id>")
def api_del_item(code, item_id):
    user = request.args.get("user", "")
    with LOCK:
        r = ROOMS.get(str(code))
        if not r:
            abort(404)
        owner = r.get("owner", "")
        for it in list(r.get("items", [])):
            if it["id"] == item_id:
                if user != it["user"] and user != owner:
                    abort(403)
                r["items"].remove(it)
                return "", 204
    abort(404)


# ------- Ana çalıştırma -------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
