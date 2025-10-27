# SMTP Sağlayıcıları

Gmail:
- `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`
- 2FA açık olmalı, **Uygulama Şifresi** üretip `SMTP_PASS` olarak girin.

Outlook/Office365:
- `SMTP_HOST=smtp.office365.com`, `SMTP_PORT=587`

Zoho:
- `SMTP_HOST=smtp.zoho.eu` (veya `.com`), `SMTP_PORT=587`

Diğerleri: Hostunuzun SMTP bilgilerini kullanın. SPF/DKIM kayıtlarını ekleyin.
