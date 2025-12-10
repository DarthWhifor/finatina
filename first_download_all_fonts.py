#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import requests
import zipfile
import shutil
import hashlib
import json
import logging
import re
from tempfile import mkdtemp

try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("⚠️ Install fontTools for better metadata: pip install fonttools")
    TTFont = None

# --- Folders ---
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# --- STAGING PATHS ---
BASE_DIR = "data/all_fonts_new"
FLAT_DIR = "data/all_fonts_flat_new"
PREVIEW_DIR = "data/previews_new"
DB_FILE = "data/fonts_db_new.json"
LOG_FILE = os.path.join(LOG_DIR, "script_new.log")

# --- ACTIVE PATHS ---
ACTIVE_BASE = "data/all_fonts"
ACTIVE_FLAT = "data/all_fonts_flat"
ACTIVE_PREVIEWS = "data/previews"
ACTIVE_DB = "data/fonts_db.json"

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(FLAT_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)

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

def get_font_name(path, original_path=None):
    """Vrati čitljivo ime fonta, ili naziv datoteke kao fallback."""
    if not TTFont:
        return os.path.basename(path)
    try:
        font = TTFont(path)
        for record in font["name"].names:
            if record.nameID == 4:
                try:
                    name = record.toUnicode().strip()
                except Exception:
                    name = str(record.string, errors="ignore").strip()
                if "\x00" in name or not name:
                    raise ValueError("Invalid name encoding")
                return name
    except Exception as e:
        logging.warning(f"⚠️ Fallback name for {path}: {e}")

    # ako ništa nije vraćeno, koristi ime iz original_path
    if original_path:
        return os.path.splitext(os.path.basename(original_path))[0]
    return os.path.splitext(os.path.basename(path))[0]

def safe_replace(new_path, target_path):
    if os.path.exists(target_path):
        shutil.rmtree(target_path, ignore_errors=True)
    shutil.move(new_path, target_path)
    logging.info(f"✅ Replaced {target_path} with new download")

def parse_google_license(folder):
    meta_file = os.path.join(folder, "METADATA.pb")
    if not os.path.exists(meta_file):
        return "Unknown", None
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            text = f.read()
        match = re.search(r'license:\s*"([^"]+)"', text)
        if match:
            return match.group(1), True
    except Exception as e:
        logging.error(f"Error parsing license in {meta_file}: {e}")
    return "Unknown", None

def parse_fontsource_license(folder):
    package_file = os.path.join(folder, "package.json")
    if not os.path.exists(package_file):
        return "Unknown", None
    try:
        with open(package_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        license_name = data.get("license", "Unknown")
        free = not any(word in license_name.lower() for word in ["proprietary", "commercial", "non-free"])
        return license_name, free
    except Exception as e:
        logging.error(f"Error parsing license in {package_file}: {e}")
    return "Unknown", None

# --- Download izvora ---
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

def collect_fonts():
    logging.info("\n➡️ Collecting font files into flat directory...")
    db = []
    font_exts = (".ttf", ".otf", ".woff", ".woff2")
    for source in os.listdir(BASE_DIR):
        source_dir = os.path.join(BASE_DIR, source)
        for root, _, files in os.walk(source_dir):
            for file in files:
                if not file.lower().endswith(font_exts):
                    continue
                src_path = os.path.join(root, file)
                dest_path = os.path.join(FLAT_DIR, file)
                if not os.path.exists(dest_path):
                    shutil.copy2(src_path, dest_path)
                full_name = get_font_name(dest_path, src_path)
                if "google-fonts" in source:
                    license_name, free = parse_google_license(root)
                elif "fontsource" in source:
                    license_name, free = parse_fontsource_license(root)
                else:
                    license_name, free = "Unknown", None
                db.append({
                    "file": os.path.basename(dest_path),
                    "source": source,
                    "original_path": src_path,
                    "full_name": full_name,
                    "license": license_name,
                    "free": free
                })
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    logging.info(f"✅ Collected {len(db)} fonts into {FLAT_DIR}")

def atomic_replace(old_path, new_path):
    backup_path = old_path + "_old"
    if os.path.exists(backup_path):
        shutil.rmtree(backup_path, ignore_errors=True)
    if os.path.exists(old_path):
        os.rename(old_path, backup_path)
    os.rename(new_path, old_path)
    logging.info(f"✅ Switched {old_path} → novi sadržaj aktiviran.")

if __name__ == "__main__":
    try:
        logging.info("🚀 Starting full font update pipeline...")
        download_google_fonts()
        clone_repo("fontsource", "https://github.com/fontsource/font-files.git")
        collect_fonts()
        logging.info("🎨 Pokrećem generate_preview_batch.py za nove previewe...")
        subprocess.run(["python3", "generate_preview_batch.py"], check=False)
        logging.info("🔄 Switching new directories into production...")
        atomic_replace(ACTIVE_BASE, BASE_DIR)
        atomic_replace(ACTIVE_FLAT, FLAT_DIR)
        atomic_replace(ACTIVE_PREVIEWS, PREVIEW_DIR)
        if os.path.exists(DB_FILE):
            os.replace(DB_FILE, ACTIVE_DB)
        logging.info("🎉 All new fonts and previews are live! Update complete.")
    except Exception as e:
        logging.error(f"❌ Pipeline terminated due to error: {e}")
