import os
import subprocess
import requests
import zipfile
import shutil
import hashlib
import json
import logging
import re
from datetime import datetime
from tempfile import mkdtemp

try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("⚠️ Install fontTools for better metadata: pip install fonttools")
    TTFont = None

# --- Paths ---
BASE_DIR = "all_fonts"
FLAT_DIR = "all_fonts_flat"
DB_FILE = "fonts_db.json"
LOG_FILE = "script.log"

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(FLAT_DIR, exist_ok=True)

# --- Logger setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# --- Helpers ---
def sha256sum(filename):
    h = hashlib.sha256()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def get_font_name(path):
    if not TTFont:
        return None
    try:
        font = TTFont(path)
        name_records = font["name"].names
        for record in name_records:
            if record.nameID == 4:  # Full font name
                return str(record.string, errors="ignore")
    except Exception as e:
        logging.error(f"Failed to read font name from {path}: {e}")
    return None

def safe_replace(new_path, target_path):
    if os.path.exists(target_path):
        backup = target_path + "_backup_" + datetime.now().strftime("%Y%m%d%H%M%S")
        shutil.move(target_path, backup)
        logging.info(f"Renamed old {target_path} to {backup}")

    shutil.move(new_path, target_path)
    logging.info(f"✅ Replaced {target_path} with new download")

# --- License extraction ---
def parse_google_license(folder):
    """Extract license from METADATA.pb in Google Fonts"""
    meta_file = os.path.join(folder, "METADATA.pb")
    if not os.path.exists(meta_file):
        return "Unknown", None
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            text = f.read()
        match = re.search(r'license:\s*"([^"]+)"', text)
        if match:
            license_name = match.group(1)
            return license_name, True  # Google Fonts su uvijek free
    except Exception as e:
        logging.error(f"Error parsing license in {meta_file}: {e}")
    return "Unknown", None

def parse_fontsource_license(folder):
    """Extract license from package.json in Fontsource"""
    package_file = os.path.join(folder, "package.json")
    if not os.path.exists(package_file):
        return "Unknown", None
    try:
        with open(package_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        license_name = data.get("license", "Unknown")
        # Ako piše nešto tipa MIT, OFL, Apache → free
        free = not any(word in license_name.lower() for word in ["proprietary", "commercial", "non-free"])
        return license_name, free
    except Exception as e:
        logging.error(f"Error parsing license in {package_file}: {e}")
    return "Unknown", None

# --- Download sources ---
def download_google_fonts():
    url = "https://github.com/google/fonts/archive/refs/heads/main.zip"
    tmp_dir = mkdtemp(prefix="google-fonts-")
    target_dir = os.path.join(BASE_DIR, "google-fonts")

    try:
        logging.info("➡️ Downloading Google Fonts...")
        r = requests.get(url, stream=True, timeout=300)
        r.raise_for_status()

        zip_path = os.path.join(tmp_dir, "google-fonts.zip")
        with open(zip_path, "wb") as f:
            f.write(r.content)

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp_dir)

        extracted = os.path.join(tmp_dir, "fonts-main")
        if not os.path.exists(extracted):
            raise RuntimeError("Google Fonts archive did not contain fonts-main folder")

        safe_replace(extracted, target_dir)
        logging.info("✅ Google Fonts updated successfully")

    except Exception as e:
        logging.error(f"❌ Failed to download Google Fonts: {e}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

def clone_repo(name, repo_url):
    tmp_dir = mkdtemp(prefix=f"{name}-")
    target_dir = os.path.join(BASE_DIR, name)

    try:
        logging.info(f"➡️ Cloning {name}...")
        subprocess.run(["git", "clone", "--depth=1", repo_url, tmp_dir], check=True)
        safe_replace(tmp_dir, target_dir)
        logging.info(f"✅ {name} updated successfully")
    except Exception as e:
        logging.error(f"❌ Failed to clone {name}: {e}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

# --- Collect fonts ---
def collect_fonts():
    logging.info("\n➡️ Collecting font files into flat directory...")

    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
    else:
        db = []

    existing_hashes = {entry["hash"] for entry in db}
    font_exts = (".ttf", ".otf", ".woff", ".woff2")
    count_new, count_skipped = 0, 0

    for source in os.listdir(BASE_DIR):
        source_dir = os.path.join(BASE_DIR, source)
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.lower().endswith(font_exts):
                    src_path = os.path.join(root, file)
                    try:
                        font_hash = sha256sum(src_path)
                    except Exception as e:
                        logging.error(f"Hashing failed for {src_path}: {e}")
                        continue

                    if font_hash in existing_hashes:
                        count_skipped += 1
                        continue

                    dest_path = os.path.join(FLAT_DIR, file)
                    if os.path.exists(dest_path):
                        base, ext = os.path.splitext(file)
                        dest_path = os.path.join(FLAT_DIR, f"{base}_{font_hash[:8]}{ext}")

                    try:
                        shutil.copy2(src_path, dest_path)
                        full_name = get_font_name(dest_path)

                        # Extract license
                        if "google-fonts" in source:
                            license_name, free = parse_google_license(root)
                        elif "fontsource" in source:
                            license_name, free = parse_fontsource_license(root)
                        else:
                            license_name, free = "Unknown", None

                        db.append({
                            "file": os.path.basename(dest_path),
                            "hash": font_hash,
                            "source": source,
                            "original_path": src_path,
                            "full_name": full_name,
                            "license": license_name,
                            "free": free
                        })
                        existing_hashes.add(font_hash)
                        count_new += 1
                    except Exception as e:
                        logging.error(f"Failed to copy {src_path} → {dest_path}: {e}")

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

    logging.info(f"✅ Added {count_new} new fonts, skipped {count_skipped} duplicates.")
    logging.info(f"📂 All fonts in {FLAT_DIR}, metadata in {DB_FILE}")

# --- Main ---
if __name__ == "__main__":
    try:
        download_google_fonts()
        clone_repo("fontsource", "https://github.com/fontsource/font-files.git")
        collect_fonts()
        logging.info("\n🎉 All done! Run again anytime, JSON DB will keep track of duplicates.")
    except Exception as e:
        logging.error(f"Script terminated due to error: {e}")
