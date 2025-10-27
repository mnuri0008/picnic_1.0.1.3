
# Piknik Vakti — Animated Icons Patch (CSS‑only)

## Kurulum
1) Bu dosyaları proje kökünde aynı yerlere koyun:
- `static/anim.css`
- `static/anim.js`

2) `templates/base.html` içinde, ana CSS/JS'den sonra aşağıyı ekleyin:
```html
<link rel="stylesheet" href="{{ url_for('static', filename='anim.css') }}">
<script defer src="{{ url_for('static', filename='anim.js') }}"></script>
```

## Kullanım
Chip köküne `.chip`, ikon elemana `.icon` verin. İsteğe bağlı sınıflar:
- `.is-breathing` (hafif döngüsel nefes)
- `.is-highlight` (yumuşak parıltı)

`templates/snippets/chips_snippet.html` içinde örnek blok var.
