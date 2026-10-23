"""Gera os QR codes do slide final como SVG (módulos brancos, fundo transparente).

Uso: uv run --with "qrcode[pil]" python apresentacao/gerar_qr.py
Edite URLS abaixo; os arquivos saem em apresentacao/qr-<nome>.svg.
"""

from pathlib import Path

import qrcode
import qrcode.image.svg

AQUI = Path(__file__).parent
URLS = {
    "github": "https://github.com/Gabriel-Marques-tech/Galaxies",
    "linkedin": "",  # preencher com o link do perfil
}

for nome, url in URLS.items():
    if not url:
        print(f"{nome}: sem URL, pulado")
        continue
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    svg = img.to_string(encoding="unicode")
    svg = svg.replace('fill="#000000"', 'fill="#ffffff"').replace("fill:#000000", "fill:#ffffff")
    (AQUI / f"qr-{nome}.svg").write_text(svg)
    print(f"{nome}: qr-{nome}.svg ({qr.modules_count} módulos) -> {url}")
