#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import streamlit as st
from PIL import Image
import cv2
import numpy as np
import requests
import base64
import tempfile
import os
from pprint import pprint

# ----------------------------
# KONFIG
# ----------------------------
PASSWORD = "finatinalozinka"
WHATFONTIS_API_KEY = "0e5df78fa808573355086c921b893de84ee9b290ab18f1c59d2f45e675f35c5d"
WHATFONTIS_API_URL = "https://www.whatfontis.com/api2/"

# ----------------------------
# LOGIN (NE DIRAMO)
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
    st.title("🎨 Font Matcher — WhatFontIs API")

    uploaded_file = st.file_uploader("📤 Uploadajte sliku s tekstom", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        # Učitavanje slike
        image = Image.open(uploaded_file).convert("RGB")
        st.image(image, caption="📸 Uploadana slika", use_container_width=True)

        # ----------------------------
        # Opcionalna obrada slike: razdvajanje slova ako su spojena
        # ----------------------------
        np_img = np.array(image)
        gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        # Morfološka operacija za razdvajanje slova
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        processed = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # Privremeni fajl
        tmp_path = tempfile.mktemp(suffix=".png")
        cv2.imwrite(tmp_path, cv2.bitwise_not(processed))

        # Prikaz obrade
        st.image(processed, caption="🧩 Obradjena slika za prepoznavanje", use_container_width=True)

        # ----------------------------
        # Pretvori sliku u Base64
        # ----------------------------
        with open(tmp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        # ----------------------------
        # Poziv prema WhatFontIs API-ju
        # ----------------------------
        st.info("📡 Šaljem sliku na WhatFontIs API...")
        params = {
            "API_KEY": WHATFONTIS_API_KEY,
            "IMAGEBASE64": 1,
            "NOTTEXTBOXSDETECTION": 1, #0,
            "FREEFONTS": 0, #1,
            "limit": 10,
            "urlimagebase64": img_b64
        }

        try:
            r = requests.post(WHATFONTIS_API_URL, data=params, timeout=60)
            if r.status_code != 200:
                st.error(f"❌ API greška: {r.status_code} — {r.text}")
            else:
                try:
                    results = r.json()
                except Exception:
                    st.error("⚠️ API nije vratio valjani JSON odgovor.")
                    results = []

                if isinstance(results, list) and len(results) > 0:
                    pprint(results)
                    st.success(f"✅ Pronađeno {len(results)} fontova!")
                    st.markdown("## 🏆 Najsličniji fontovi:")

                    for i, font in enumerate(results, 1):
                        title = font.get("title", "Nepoznat font")
                        url = font.get("url", "")
                        img = font.get("image", "")
                        img1 = font.get("image1", "")
                        img2 = font.get("image2", "")

                        st.markdown(f"### {i}. [{title}]({url})")
                        if img:
                            st.image(img,  width="stretch") #caption=f"Preview: {title}"
                            if img1:
                                st.image(img1, width="stretch")
                            if img2:
                                st.image(img2, width="stretch")
                        else:
                            st.info("⚠️ Nema preview slike.")
                        st.divider()
                else:
                    st.warning("⚠️ Nije pronađen nijedan font u odgovoru API-ja.")
        except Exception as e:
            st.error(f"💥 Greška prilikom slanja zahtjeva: {e}")

        # Briši privremeni fajl
        try:
            os.remove(tmp_path)
        except:
            pass
