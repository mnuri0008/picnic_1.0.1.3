# Picnic Vakti — Patch Bundle (SMTP + OTP + Dil Link Fix)

Bu paket, orijinal arayüze (kategoriler, ikonlar, room.html) dokunmadan:
- **Gerçek e‑posta gönderimi** için SMTP entegrasyonu,
- **4 haneli OTP** ile şifre sıfırlama akışı (10 dk geçerlilik),
- Jinja'daki `**kwargs` kısıtı nedeniyle oluşan **dil bağlantısı (TR/EN)** hatasını düzeltmek
amacıyla hazırlanmış yardımcı kodları içerir.

## İçerik
- `server_patch.py` — Mevcut `server.py`nin üstüne eklenebilecek yardımcı fonksiyonlar ve blueprint.
- `templates/base_patch_example.html` — Sadece dil bağlantılarını güvenli şekilde kuran örnek. 
  > *Not*: Görsel düzen değişmez. Mevcut `base.html`’ınızda **yalnızca dil butonu satırını** bu örnektekine uyarlayın.
- `.env.example` — SMTP ortam değişkenleri örneği.
- `README_SMTP.md` — Gmail/Outlook/Zoho vs. kurulum yönergeleri.

## Hızlı Uygulama
1) **SMTP ortam değişkenlerini** Render veya lokal `.env` içine girin (aşağıya bak).
2) `server_patch.py` içindeki `register_patch(app)` fonksiyonunu, uygulama oluşturduğunuz yerde çağırın:
   ```python
   # server.py
   from server_patch import register_patch
   register_patch(app)
   ```
3) `base.html` içinde dil bağlantısı satırlarını aşağıdaki gibi değiştirin:
   ```html
   <a class="lang" href="{{ LANG_TR_URL }}">TR</a>
   <a class="lang" href="{{ LANG_EN_URL }}">EN</a>
   ```
4) Şifre sıfırlama için uç noktalar:
   - `POST /auth/request-reset`  body: `{ "email": "kullanici@..." }`
   - `POST /auth/verify-reset`   body: `{ "email": "...", "code": "1234" }`
   - `POST /auth/do-reset`       body: `{ "email": "...", "code": "1234", "new_password": "..." }`

`send_mail()` SMTP ENV varsa **gerçekten yollar**, yoksa **log'a yazar**.
