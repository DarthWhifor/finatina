from PIL import Image, ImageDraw, ImageFont
import imagehash
import json
import os

DB_FILE = "data/fonts_db.json"

# Load font metadata (hashove koristimo iz baze)
with open(DB_FILE, "r") as f:
    font_db = json.load(f)

def find_most_similar_font(uploaded_image, top_n=3):
    uploaded_hash = imagehash.average_hash(uploaded_image.convert("L"))
    scores = []

    for entry in font_db:
        fname = entry["file"]
        fpath = os.path.join("data/all_fonts_flat", fname)
        try:
            font = ImageFont.truetype(fpath, 64)
            img = Image.new("L", (800, 200), 255)
            draw = ImageDraw.Draw(img)
            draw.text((10, 50), "Sample Text", font=font, fill=0)
            fhash = imagehash.average_hash(img)
            score = uploaded_hash - fhash
            scores.append((fname, score))
        except Exception:
            continue

    scores.sort(key=lambda x: x[1])
    return scores[:top_n]
