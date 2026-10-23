"""Gera os QR codes do slide final no estilo do app: módulos arredondados, gradiente do Stars
(azul → roxo → rosa) e o logo do Stars no centro, sobre um azulejo branco.

Uso: uv run --with "qrcode[pil]" --with cairosvg python apresentacao/gerar_qr.py
Saída: apresentacao/qr-<nome>.png (1024 px).
"""

from pathlib import Path

import cairosvg
import qrcode
from PIL import Image, ImageDraw
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import HorizontalGradiantColorMask
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer

AQUI = Path(__file__).parent
URLS = {
    "github": "https://github.com/Gabriel-Marques-tech/Galaxies",
    "linkedin": "https://www.linkedin.com/in/gabrielmarquesinteli",
}
AZUL, ROXO, ROSA = (66, 133, 244), (155, 114, 203), (217, 101, 112)


def logo_no_centro(tamanho: int) -> Image.Image:
    """Logo do Stars num disco branco com borda em gradiente, para o meio do QR."""
    png = cairosvg.svg2png(url=str(AQUI / "logo.svg"), output_width=tamanho, output_height=tamanho)
    logo = Image.open(__import__("io").BytesIO(png)).convert("RGBA")
    caixa = int(tamanho * 1.25)
    fundo = Image.new("RGBA", (caixa, caixa), (0, 0, 0, 0))
    d = ImageDraw.Draw(fundo)
    d.ellipse((0, 0, caixa - 1, caixa - 1), fill=(155, 114, 203, 255))
    d.ellipse((6, 6, caixa - 7, caixa - 7), fill=(255, 255, 255, 255))
    fundo.alpha_composite(logo, ((caixa - tamanho) // 2, (caixa - tamanho) // 2))
    return fundo


for nome, url in URLS.items():
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=24, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(radius_ratio=1),
        color_mask=HorizontalGradiantColorMask(back_color=(255, 255, 255), left_color=AZUL, right_color=ROSA),
    ).convert("RGBA")
    # o roxo no meio do gradiente: mistura uma faixa central
    largura = img.width
    faixa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pix = img.load()
    for x in range(largura):
        t = x / (largura - 1)
        peso = max(0.0, 1 - abs(t - 0.5) * 2.4)  # 1 no centro, 0 nas bordas
        if peso <= 0:
            continue
        for y in range(img.height):
            r, g, b, a = pix[x, y]
            if (r, g, b) != (255, 255, 255):
                pix[x, y] = (
                    int(r * (1 - peso) + ROXO[0] * peso),
                    int(g * (1 - peso) + ROXO[1] * peso),
                    int(b * (1 - peso) + ROXO[2] * peso),
                    a,
                )
    logo = logo_no_centro(int(largura * 0.21))
    img.alpha_composite(logo, ((largura - logo.width) // 2, (largura - logo.height) // 2))
    img = img.resize((1024, 1024), Image.LANCZOS)
    img.save(AQUI / f"qr-{nome}.png")
    print(f"{nome}: qr-{nome}.png ({qr.modules_count} módulos) -> {url}")
