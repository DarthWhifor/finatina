#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import streamlit as st
from PIL import Image
import json, os, time, torch
import numpy as np
import clip
from render_font_preview import render_font_preview
from sklearn.metrics.pairwise import cosine_similarity

# ----------------------------
# KONFIG
# ----------------------------
PASSWORD = "finatinalozinka"
FONT_DB_FILE = "data/fonts_db.json"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ----------------------------
# MODEL: CLIP
# ----------------------------
if "clip_model" not in st.session_state:
    try:
        with st.spinner("🧠 Učitavam CLIP (ViT-B/32)..."):
            clip_model, clip_preprocess = clip.load("ViT-B/32", device=DEVICE, jit=False)
            clip_model.eval()
            st.session_state["clip_model"] = clip_model
            st.session_state["clip_preprocess"] = clip_preprocess
            st.session_state["clip_device"] = DEVICE
        st.success("✅ CLIP spreman!")
    except Exception as e:
        st.error(f"⚠️ Greška pri učitavanju CLIP modela: {e}")
        st.stop()

# ----------------------------
# LOGIN (NETAKNUTO)
# ----------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if st.session_state.authenticated:
    with st.sidebar:
        st.success("✅ Ulogirani ste")
        if st.button("🚪 Odjava"):
            st.session_state.authenticated = False
            st.rerun()

if not st.session_state.authenticated:
    st.title("🔒 Prijava")
    with st.form("login_form"):
        password_input = st.text_input("Unesi lozinku:", type="password")
        submit = st.form_submit_button("Prijavi se")
        if submit:
            if password_input == PASSWORD:
                st.session_state.authenticated = True
                st.success("✅ Uspješno ste prijavljeni!")
                st.rerun()
            else:
                st.error("❌ Pogrešna lozinka")

# ----------------------------
# GLAVNI DIO
# ----------------------------
if st.session_state.authenticated:
    st.title("🎨 Font Matcher — CLIP vizualna pretraga")

    # ----------------------------
    # UČITAJ BAZU FONTOVA
    # ----------------------------
    if not os.path.exists(FONT_DB_FILE):
        st.error("❌ Datoteka s bazom fontova nije pronađena!")
        st.stop()

    with open(FONT_DB_FILE, "r", encoding="utf-8") as f:
        fonts_db = json.load(f)

    if not isinstance(fonts_db, list):
        st.error("⚠️ Datoteka fonts_db.json nije u ispravnom formatu (očekuje se lista).")
        st.stop()

    # ----------------------------
    # UPLOAD SLIKE
    # ----------------------------
    uploaded_file = st.file_uploader("📤 Uploadajte sliku s tekstom", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        image = Image.open(uploaded_file).convert("RGB")
        st.image(image, caption="📸 Uploadana slika", use_container_width=True)

        st.info("🔍 Generiram embedding slike...")
        clip_model = st.session_state["clip_model"]
        clip_preprocess = st.session_state["clip_preprocess"]

        with torch.no_grad():
            image_tensor = clip_preprocess(image).unsqueeze(0).to(DEVICE)
            image_emb = clip_model.encode_image(image_tensor)
            image_emb /= image_emb.norm(dim=-1, keepdim=True)
            image_emb = image_emb.cpu().numpy()

        # ----------------------------
        # IZRAČUNAJ SLIČNOST FONTOVA
        # ----------------------------
        st.info("🔍 Računam sličnost s fontovima...")
        font_embs = []
        valid_fonts = []

        for font in fonts_db:
            name = font.get("full_name") or font.get("file", "")
            if not name:
                continue
            try:
                tokens = clip.tokenize(name).to(DEVICE)
                with torch.no_grad():
                    txt_emb = clip_model.encode_text(tokens)
                    txt_emb /= txt_emb.norm(dim=-1, keepdim=True)
                    font_embs.append(txt_emb.cpu().numpy())
                    valid_fonts.append(font)
            except Exception as e:
                print(f"⚠️ Preskačem {name}: {e}")

        if not font_embs:
            st.error("⚠️ Nema valjanih fontova u bazi.")
            st.stop()

        font_embs = np.vstack(font_embs)
        sims = cosine_similarity(image_emb, font_embs)[0]
        top_indices = np.argsort(sims)[::-1][:10]
        results = [(valid_fonts[i], sims[i]) for i in top_indices]

        # ----------------------------
        # PRIKAZ REZULTATA
        # ----------------------------
        st.success("✅ Pretraga završena!")
        st.markdown("## 🏆 Najsličniji fontovi:")

        for i, (font, score) in enumerate(results, 1):
            fname = font.get("file", "N/A")
            fullname = font.get("full_name", fname)
            license = font.get("license", "Nepoznata")
            source = font.get("source", "Nepoznata")

            # koristi original_path ako postoji, inače fallback na all_fonts_flat
            path = font.get("original_path", os.path.join("data/all_fonts_flat", fname))

            preview = None
            if os.path.exists(path):
                try:
                    preview = render_font_preview(
                        path,
                        text="ABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz\n0123456789"
                    )
                except Exception as e:
                    st.warning(f"⚠️ Nije moguće generirati preview za {fname}: {e}")
            else:
                st.warning(f"⚠️ Font datoteka nije pronađena: {path}")

            st.markdown(f"### {i}. {fullname}")
            st.write(f"📊 Sličnost: {score:.3f}")
            st.write(f"📄 Licenca: {license} | 🌐 Izvor: {source}")
            if preview is not None:
                st.image(preview, caption=f"Preview: {fname}", use_container_width=True)
            st.divider()
