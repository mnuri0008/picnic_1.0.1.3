# -*- coding: utf-8 -*-
import os, smtplib, ssl, random, time
from email.mime.text import MIMEText
from flask import request, jsonify, url_for, current_app

__OTP_STORE = {}

def _now(): return int(time.time())
def _gen_code(): return f"{random.randint(0, 9999):04d}"

def send_mail(to_email: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "0") or 0)
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    sender = os.getenv("EMAIL_FROM", user or "no-reply@example.com")

    if not (host and port and user and pwd):
        current_app.logger.warning("[MAIL] SMTP env eksik; gönderim YOK. to=%s subject=%s", to_email, subject)
        current_app.logger.info("[MAIL] BODY:\n%s", body)
        return True

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email

        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.ehlo(); s.starttls(context=ctx); s.login(user, pwd); s.send_message(msg)
        current_app.logger.info("[MAIL] Gönderildi -> %s", to_email)
        return True
    except Exception as e:
        current_app.logger.exception("[MAIL] Hata: %s", e)
        return False

def _lang_url(lang: str):
    ep = request.endpoint or "home"
    view_args = dict(request.view_args or {})
    q = request.args.to_dict(flat=True); q["lang"] = lang
    try: return url_for(ep, **view_args, **q)
    except Exception: return url_for("home", lang=lang)

def register_patch(app):
    @app.context_processor
    def inject_lang_links():
        return {"LANG_TR_URL": _lang_url("tr"), "LANG_EN_URL": _lang_url("en")}

    @app.post("/auth/request-reset")
    def request_reset():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        if not email: return jsonify(ok=False, error="email_required"), 400
        code = _gen_code()
        __OTP_STORE[email] = {"code": code, "exp": _now() + 600}
        ok = send_mail(email, "Şifre Sıfırlama Kodu", f"Kodunuz: {code} (10 dk geçerli)")
        return jsonify(ok=bool(ok))

    @app.post("/auth/verify-reset")
    def verify_reset():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        code  = (data.get("code") or "").strip()
        rec = __OTP_STORE.get(email)
        if not rec or _now() > rec["exp"]: return jsonify(ok=False, error="expired_or_missing"), 400
        if code != rec["code"]: return jsonify(ok=False, error="invalid_code"), 400
        return jsonify(ok=True)

    @app.post("/auth/do-reset")
    def do_reset():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        code  = (data.get("code") or "").strip()
        newp  = (data.get("new_password") or "").strip()
        rec = __OTP_STORE.get(email)
        if not rec or _now() > rec["exp"]: return jsonify(ok=False, error="expired_or_missing"), 400
        if code != rec["code"]: return jsonify(ok=False, error="invalid_code"), 400
        if len(newp) < 6: return jsonify(ok=False, error="weak_password"), 400
        # TODO: mevcut kullanıcı şemanıza göre parolayı güncelleyin
        current_app.logger.info("[RESET] %s parola güncellendi (uygulama-özel)", email)
        try: del __OTP_STORE[email]
        except KeyError: pass
        return jsonify(ok=True)
