from flask import Flask, render_template, request, jsonify, abort, send_from_directory, make_response, redirect, url_for, session
from datetime import datetime, timedelta
import threading, itertools

# Flask yapılandırması
app = Flask(
    __name__,
    static_folder='static',
    static_url_path='/static',
    template_folder='templates'
)

# Session secret (demo):
app.secret_key = 'picnic-demo-secret-key'


# Basit kullanıcı deposu (in-memory, sınırsız kullanıcı)
USERS = {}  # username -> {"password":"...", "color":"...", "secret_q":"...", "secret_a":"..."}

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("login_page", next=request.path, lang=request.args.get("lang","tr")))
        return fn(*args, **kwargs)
    return wrapper
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
@login_required
def home():
    lang = request.args.get("lang", session.get("lang","tr"))
    username = session.get("username","")
    # Eski index.html aynı kalsın diye querystring ile de username/lang geçelim
    return redirect(url_for("index_page", username=username, lang=lang))


@app.route("/room/<code>")
@login_required
def room(code):
    username = session.get('username') or request.args.get('username','')
    lang = request.args.get('lang', session.get('lang','tr'))
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



# ------- Basit arayüz rotaları (3 arayüz) -------
# ------- Auth endpoints -------
@app.route("/login", methods=["GET"])
def login_page():
    lang = request.args.get("lang", session.get("lang","tr"))
    return render_template("login.html", lang=lang)

@app.post("/auth/login")
def auth_login():
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    lang = (data.get("lang") or request.args.get("lang") or "tr").strip()
    if not username or not password:
        abort(400, description="missing credentials")
    # kabul: kullanıcı yoksa demo amaçlı otomatik oluşturma yerine kayıt şartı
    user = USERS.get(username)
    if not user or user.get("password") != password:
        abort(401, description="bad credentials")
    session["username"] = username
    session["lang"] = lang
    return jsonify(ok=True)

@app.post("/auth/register")
def auth_register():
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    color    = (data.get("color") or "").strip()
    secret_q = (data.get("secret_q") or "").strip()
    secret_a = (data.get("secret_a") or "").strip()
    lang = (data.get("lang") or request.args.get("lang") or "tr").strip()
    if not username or not password or not color or not secret_q or not secret_a:
        abort(400, description="missing fields")
    if username in USERS:
        abort(409, description="user exists")
    USERS[username] = {"password": password, "color": color, "secret_q": secret_q, "secret_a": secret_a}
    return jsonify(ok=True)

@app.post("/auth/forgot")
def auth_forgot():
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    answer   = (data.get("secret_a") or "").strip()
    if not username or username not in USERS:
        abort(404, description="user not found")
    if not answer or answer.lower().strip() != USERS[username].get("secret_a","").lower().strip():
        abort(403, description="wrong answer")
    USERS[username]["password"] = "1234"
    return jsonify(ok=True, temp_password="1234")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/register")
def register_page():
    # İkinci arayüz: mevcut index/oda mantığıyla çalışacak bir kayıt formu iskeleti
    return render_template("index.html")

@app.route("/forgot")
def forgot_page():
    # Üçüncü arayüz: şifre sıfırlama iskeleti (mevcut arayüz değişmeden)
    return render_template("index.html")



def list_rooms():
    with LOCK:
        data = []
        for code, r in ROOMS.items():
            data.append({
                "code": code,
                "owner": r.get("owner",""),
                "date": r.get("date",""),
                "count": len(r.get("items", []))
            })
        # Son eklenenler önce görünsün
        data.sort(key=lambda x: x.get("date",""), reverse=True)
        return data

@app.route("/home")
def index_page():
    # Eski index.html'i aynen render edelim
    lang = request.args.get("lang", session.get("lang","tr"))
    username = request.args.get("username", session.get("username",""))
    return render_template("index.html", rooms=list_rooms(), lang=lang, username=username)

# ------- Ana çalıştırma -------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
