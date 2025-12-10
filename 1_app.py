#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import streamlit as st
from PIL import Image
import json, os, time, torch
from torchvision import models, transforms
import numpy as np
from search_font_vision import find_most_similar_font
from render_font_preview import render_font_preview
import clip  # OpenAI CLIP

# ----------------------------
# KONFIG
# ----------------------------
PASSWORD = "finatinalozinka"
FONT_DB_FILE = "data/fonts_db.json"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ----------------------------
# UČITAJ ResNet MODEL
# ----------------------------
if "resnet_model" not in st.session_state:
    with st.spinner("🧠 Učitavam ResNet50 model..."):
        model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        model = torch.nn.Sequential(*(list(model.children())[:-1]))  # bez fc sloja
        model.eval().to(DEVICE)

        preprocess = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

        st.session_state["resnet_model"] = model
        st.session_state["resnet_preprocess"] = preprocess
        st.session_state["resnet_device"] = DEVICE
    st.success("✅ ResNet50 model spreman!")

# ----------------------------
# UČITAJ CLIP MODEL (opcionalno)
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
        st.warning(f"⚠️ CLIP nije učitan: {e}")
        st.session_state["clip_model"] = None
        st.session_state["clip_preprocess"] = None
        st.session_state["clip_device"] = None

# ----------------------------
# LOGIN
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
    st.title("🎨 Font Matcher — hibrid (ResNet50 + SSIM + CLIP)")

    # ----------------------------
    # IZBOR MODA PRETRAŽIVANJA
    # ----------------------------
    search_mode = st.sidebar.radio(
        "⚙️ Način pretrage:",
        ["ResNet50 (brza)", "Hibridna (ResNet + SSIM)"],
        index=0,
    )

    if search_mode == "Hibridna (ResNet + SSIM)":
        from search_font_vision_hybrid import find_most_similar_font
    else:
        from search_font_vision import find_most_similar_font
    st.write(f"🧠 Aktivni modul: {search_mode}")

    uploaded_file = st.file_uploader("Uploadajte sliku s tekstom", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None:
        upload_path = "data/upload_tmp.png"
        image = Image.open(uploaded_file).convert("RGB")
        image.save(upload_path)
        st.image(image, caption="📸 Uploadana slika", use_container_width=True)

        st.info("🔍 Tražim najsličnije fontove...")
        progress = st.progress(0.0)

        start_time = time.time()
        try:
            results = find_most_similar_font(upload_path, top_n=10)
        except Exception as e:
            st.error(f"⚠️ Greška prilikom pretrage: {e}")
            results = []

        elapsed = time.time() - start_time
        st.success(f"✅ Pretraga završena u {elapsed:.2f} sekundi")

        filtered = []
        for res in results:
            font_path = None
            fname = res.get("file")
            if fname:
                for base_dir in ["data/all_fonts_flat", "data/all_fonts_flat_converted"]:
                    fpath = os.path.join(base_dir, fname)
                    if os.path.exists(fpath):
                        font_path = fpath
                        break
            if not font_path:
                continue

            img_preview = render_font_preview(
                font_path,
                text="ABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz\n0123456789"
            )
            if img_preview is not None:
                res["preview_img"] = img_preview
                filtered.append(res)

            if len(filtered) >= 3:
                break

        if filtered:
            st.markdown("## 🏆 Najsličniji fontovi")
            for i, res in enumerate(filtered, 1):
                fname = res["file"]
                score = res["score"]
                fullname = res.get("full_name") or fname
                licenca = res.get("license") or "Nepoznata"
                izvor = res.get("source") or "Nepoznata"

                st.markdown(f"### {i}. {fullname}")
                st.write(f"📊 Ukupni score: {score:.2f}/100")
                st.write(f"🔹 Embedding: {res['embed_score']:.2f} | 🔹 SSIM: {res['ssim_score']:.2f}")
                st.write(f"📄 Licenca: {licenca}")
                st.write(f"🌐 Izvor: {izvor}")

                img_preview = res.get("preview_img")
                if img_preview is not None:
                    st.image(img_preview, caption=f"Preview: {fname}", use_container_width=True)
                else:
                    st.info(f"⚠️ Nije moguće generirati preview za {fname}.")
        else:
            st.warning("⚠️ Nije pronađen nijedan font s valjanim prikazom.")
