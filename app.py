import streamlit as st
from PIL import Image
import os, json, requests, locale
from search_font import find_most_similar_font

# ==============================
#  Jednostavna autentifikacija
# ==============================
PASSWORD = "finatinalozinka"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Prijava")
    password = st.text_input("Unesi lozinku:", type="password")
    if password == PASSWORD:
        st.session_state.authenticated = True
        st.experimental_rerun()
    else:
        if password:  # ako je nešto upisano ali nije točno
            st.error("❌ Pogrešna lozinka")
    st.stop()  # prekini app dok se ne autentificira korisnik

# ==============================
#  Ako je lozinka OK, nastavi app
# ==============================

# Config
FONT_FOLDER = "data/all_fonts_flat"
FONT_DB_FILE = "data/fonts_db.json"
OLLAMA_PORT = 11434
GEMMA_MODEL = "gemma"
TOP_N = 3

# Load font metadata
with open(FONT_DB_FILE, "r") as f:
    font_db = json.load(f)

# Determine language for placeholders
sys_locale, _ = locale.getdefaultlocale()
if sys_locale and sys_locale.startswith("hr"):
    placeholder_text = "Unesi tekst sa slike"
    upload_label = "Uploadajte sliku sa tekstom"
    page_title = "Usporedba fontova + Gemma asistent"
else:
    placeholder_text = "Enter the text from the image"
    upload_label = "Upload an image with text"
    page_title = "Font Matcher + Gemma Assistant"

st.title(page_title)

uploaded_file = st.file_uploader(upload_label, type=["png","jpg","jpeg"])
text_sample = st.text_input(placeholder_text, "Sample Text")

# Gemma API call
def gemma_response(text_prompt, language="hr"):
    url = f"http://localhost:{OLLAMA_PORT}/v1/chat/completions"
    payload = {
        "model": GEMMA_MODEL,
        "messages": [{"role": "user", "content": text_prompt}],
        "language": language
    }
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            data = r.json()
            return data['choices'][0]['message']['content']
        else:
            return f"⚠ Gemma error: {r.status_code} {r.text}"
    except Exception as e:
        return f"⚠ Gemma request failed: {e}"

# Process uploaded image
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploadana slika", use_column_width=True)

    top_fonts = find_most_similar_font(image, top_n=TOP_N)

    if top_fonts:
        st.success(f"Top {TOP_N} najbližih fontova:")
        gemma_prompts = []

        for i, (fname, score) in enumerate(top_fonts, 1):
            entry = next((e for e in font_db if e["file"] == fname), {})
            licenca = entry.get("license", "Nepoznata")
            izvor = entry.get("source", "Nepoznata")
            st.write(f"{i}. {fname} (score: {score})")
            st.write(f"   📄 Licenca: {licenca}")
            st.write(f"   🌐 Izvor: {izvor}")
            gemma_prompts.append(f"{i}. Font: {fname}, Licenca: {licenca}, Izvor: {izvor}, score: {score}")

        prompt_text = "Uploadani tekst najviše podsjeća na ove fontove:\n" + "\n".join(gemma_prompts)
        gemma_lang = "hr" if sys_locale and sys_locale.startswith("hr") else "en"
        response = gemma_response(prompt_text, language=gemma_lang)
        st.write("💬 Gemma:", response)
    else:
        st.warning("Nije pronađen sličan font u bazi.")
