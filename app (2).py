import streamlit as st
import requests
from PIL import Image
import io

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Image Describer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Backend URL ───────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:8000"

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        /* ── Base ── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        .stApp { background: #0F1117; color: #E8EAF0; }

        /* ── Hero header ── */
        .hero { text-align: center; padding: 3rem 1rem 2rem; }
        .hero h1 {
            font-family: 'Playfair Display', serif;
            font-size: clamp(2rem, 5vw, 3.5rem);
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, #6C8EFF 0%, #A78BFA 50%, #F472B6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        .hero p {
            color: #8B92A8;
            font-size: 1.05rem;
            font-weight: 300;
            max-width: 480px;
            margin: 0 auto;
        }

        /* ── Upload zone ── */
        [data-testid="stFileUploadDropzone"] {
            background: #161B2E !important;
            border: 2px dashed #2D3456 !important;
            border-radius: 16px !important;
            transition: border-color 0.2s;
        }
        [data-testid="stFileUploadDropzone"]:hover {
            border-color: #6C8EFF !important;
        }

        /* ── Image preview card ── */
        .preview-card {
            background: #161B2E;
            border: 1px solid #1E2540;
            border-radius: 16px;
            padding: 1rem;
            text-align: center;
        }
        .preview-label {
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #5B6285;
            margin-bottom: 0.75rem;
        }

        /* ── Description card ── */
        .desc-card {
            background: #161B2E;
            border: 1px solid #1E2540;
            border-left: 4px solid #6C8EFF;
            border-radius: 0 16px 16px 0;
            padding: 1.5rem 1.75rem;
            line-height: 1.8;
            font-size: 0.97rem;
            color: #C8CCDD;
        }
        .desc-label {
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #6C8EFF;
            margin-bottom: 0.75rem;
        }

        /* ── Analyze button ── */
        .stButton > button {
            background: linear-gradient(135deg, #6C8EFF, #A78BFA) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
            padding: 0.65rem 2.5rem !important;
            letter-spacing: 0.02em !important;
            width: 100% !important;
            transition: opacity 0.2s !important;
        }
        .stButton > button:hover { opacity: 0.88 !important; }

        /* ── Error / info boxes ── */
        .stAlert { border-radius: 12px !important; }

        /* ── Divider ── */
        hr { border-color: #1E2540 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero">
        <h1>Image Describer</h1>
        <p>Upload any image and get a detailed AI-powered description in seconds.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")

# ── Layout: upload + result ───────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    uploaded_file = st.file_uploader(
        "Drop an image here or click to browse",
        type=["jpg", "jpeg", "png", "gif", "webp"],
        label_visibility="visible",
    )

    if uploaded_file:
        image = Image.open(uploaded_file)
        st.markdown('<div class="preview-card">', unsafe_allow_html=True)
        st.markdown('<div class="preview-label">Preview</div>', unsafe_allow_html=True)
        st.image(image, use_container_width=True)
        st.caption(
            f"**{uploaded_file.name}**  ·  {uploaded_file.size / 1024:.1f} KB  ·  {image.width}×{image.height}px"
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        analyze_btn = st.button("Analyze Image ✦")
    else:
        st.info("Supported formats: JPEG · PNG · GIF · WEBP  |  Max 20 MB")
        analyze_btn = False

with col_right:
    if uploaded_file and analyze_btn:
        with st.spinner("Analyzing image…"):
            try:
                uploaded_file.seek(0)
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                response = requests.post(f"{BACKEND_URL}/describe", files=files, timeout=60)

                if response.status_code == 200:
                    data = response.json()
                    st.markdown('<div class="desc-label">Description</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="desc-card">{data["description"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        label="Download description",
                        data=data["description"],
                        file_name=f"{uploaded_file.name}_description.txt",
                        mime="text/plain",
                    )
                else:
                    detail = response.json().get("detail", response.text)
                    st.error(f"Error {response.status_code}: {detail}")

            except requests.exceptions.ConnectionError:
                st.error("Cannot reach the backend. Make sure FastAPI is running on port 8000.")
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")

    elif not uploaded_file:
        st.markdown(
            """
            <div style="height:100%;display:flex;flex-direction:column;justify-content:center;
                        align-items:center;padding:3rem;text-align:center;color:#3D4466;">
                <div style="font-size:3.5rem;margin-bottom:1rem;opacity:0.4;">🖼️</div>
                <div style="font-size:0.9rem;font-weight:500;">
                    Your image description will appear here
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
