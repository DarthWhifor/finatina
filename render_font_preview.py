#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
render_font_preview.py — radna verzija (bez kontrast provjere)
Radi i kad font ne podržava sve znakove.
"""

import io
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from fontTools.ttLib.woff2 import decompress as woff2_decompress

def render_font_preview(font_path, text=None, size=64, image_size=(512, 256)):
    try:
        if font_path.lower().endswith(".woff2"):
            with open(font_path, "rb") as input_buf:
                output_buf = io.BytesIO()
                woff2_decompress(input_buf, output_buf)
                output_buf.seek(0)
                font = ImageFont.truetype(output_buf, size)
        elif font_path.lower().endswith(".woff"):
            font = TTFont(font_path)
            output_buf = io.BytesIO()
            font.save(output_buf)
            output_buf.seek(0)
            font = ImageFont.truetype(output_buf, size)
        else:
            font = ImageFont.truetype(font_path, size)
    except Exception as e:
        print(f"⚠️  Ne mogu učitati font: {font_path} ({e})")
        return None

    if text is None:
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz\n0123456789"

    img = Image.new("L", image_size, 255)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, font=font, fill=0)

    # 🔹 Pojačaj kontrast i malo zadebljaj tekst da SSIM ima što mjeriti
    from PIL import ImageEnhance, ImageFilter

    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = img.filter(ImageFilter.MinFilter(3))  # malo zgusni poteze
    img = img.resize((image_size[0] // 2, image_size[1] // 2), Image.NEAREST)
    img = img.resize(image_size, Image.NEAREST)

    return img.convert("RGB")

