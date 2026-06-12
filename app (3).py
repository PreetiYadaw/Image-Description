import streamlit as st
import requests

st.set_page_config(
    page_title="PDF Image Describer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BACKEND_URL = "http://localhost:8000"

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: #0F1117; color: #E8EAF0; }

    .hero { text-align: center; padding: 3rem 1rem 2rem; }
    .hero h1 {
        font-family: 'Playfair Display', serif;
        font-size: clamp(2rem, 5vw, 3.5rem); font-weight: 700;
        background: linear-gradient(135deg, #6C8EFF 0%, #A78BFA 50%, #F472B6 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .hero p { color: #8B92A8; font-size: 1.05rem; font-weight: 300; max-width: 520px; margin: 0 auto; }

    .stats-bar {
        display: flex; gap: 1.5rem; margin: 1rem 0 1.5rem;
        background: #161B2E; border: 1px solid #1E2540;
        border-radius: 12px; padding: 1rem 1.5rem;
    }
    .stat { text-align: center; flex: 1; }
    .stat-val { font-size: 1.6rem; font-weight: 700; color: #A78BFA; }
    .stat-lbl { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: #5B6285; margin-top: 2px; }

    .page-card {
        background: #161B2E; border: 1px solid #1E2540;
        border-radius: 16px; padding: 1.25rem 1.5rem; margin-bottom: 1.25rem;
    }
    .page-card-header {
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;
    }
    .page-badge {
        background: linear-gradient(135deg, #6C8EFF22, #A78BFA22);
        border: 1px solid #6C8EFF44; color: #A78BFA;
        border-radius: 8px; padding: 0.2rem 0.65rem; font-size: 0.78rem; font-weight: 600;
    }
    .dim-tag { color: #3D4466; font-size: 0.72rem; }
    .desc-text {
        color: #C8CCDD; line-height: 1.8; font-size: 0.95rem;
        border-left: 3px solid #6C8EFF44; padding-left: 1rem;
    }

    [data-testid="stFileUploadDropzone"] {
        background: #161B2E !important; border: 2px dashed #2D3456 !important; border-radius: 16px !important;
    }
    [data-testid="stFileUploadDropzone"]:hover { border-color: #6C8EFF !important; }

    .stButton > button {
        background: linear-gradient(135deg, #6C8EFF, #A78BFA) !important;
        color: white !important; border: none !important; border-radius: 10px !important;
        font-weight: 600 !important; font-size: 1rem !important;
        padding: 0.65rem 2.5rem !important; width: 100% !important;
    }
    .stButton > button:hover { opacity: 0.88 !important; }
    hr { border-color: #1E2540 !important; }
    .stAlert { border-radius: 12px !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>PDF Page Describer</h1>
    <p>Upload a PDF and get AI-powered descriptions of every page — including flowcharts, diagrams, and images.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

col_up, col_info = st.columns([1, 1], gap="large")

with col_up:
    uploaded_file = st.file_uploader("Drop a PDF here or click to browse", type=["pdf"])
    if uploaded_file:
        size_kb = uploaded_file.size / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
        st.success(f"📄 **{uploaded_file.name}** · {size_str}")
        analyze_btn = st.button("Analyze PDF ✦")
    else:
        st.info("Supported format: PDF  |  Max 50 MB")
        analyze_btn = False

with col_info:
    st.markdown("""
    <div style="padding:1.5rem;background:#161B2E;border:1px solid #1E2540;border-radius:16px;">
        <div style="font-size:0.75rem;font-weight:600;letter-spacing:0.08em;
                    text-transform:uppercase;color:#6C8EFF;margin-bottom:1rem;">How it works</div>
        <div style="color:#8B92A8;font-size:0.92rem;line-height:2.2;">
            ① Upload any PDF file<br>
            ② Each page is rendered as a high-res image<br>
            ③ GPT-4.1-mini reads every page visually<br>
            ④ Flowcharts, diagrams &amp; images are all described
        </div>
    </div>
    """, unsafe_allow_html=True)

if uploaded_file and analyze_btn:
    st.markdown("---")
    with st.spinner("Rendering pages and generating descriptions — this may take a moment…"):
        try:
            uploaded_file.seek(0)
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            response = requests.post(f"{BACKEND_URL}/describe-pdf", files=files, timeout=300)

            if response.status_code == 200:
                data = response.json()
                descriptions = data["descriptions"]

                st.markdown(f"""
                <div class="stats-bar">
                    <div class="stat">
                        <div class="stat-val">{data['total_pages']}</div>
                        <div class="stat-lbl">Total Pages</div>
                    </div>
                    <div class="stat">
                        <div class="stat-val">{len(descriptions)}</div>
                        <div class="stat-lbl">Pages Described</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                for item in descriptions:
                    st.markdown(f"""
                    <div class="page-card">
                        <div class="page-card-header">
                            <span class="page-badge">Page {item['page_number']}</span>
                            <span class="dim-tag">{item['width']} × {item['height']} px</span>
                        </div>
                        <div class="desc-text">{item['description']}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Build download report
                lines = [
                    "PDF Description Report",
                    f"File: {data['filename']}",
                    f"Total pages: {data['total_pages']}",
                    "=" * 60,
                ]
                for item in descriptions:
                    lines += [
                        f"\nPage {item['page_number']}  ({item['width']}×{item['height']} px)",
                        "-" * 40,
                        item["description"],
                    ]

                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    label="⬇ Download full report",
                    data="\n".join(lines),
                    file_name=f"{uploaded_file.name}_descriptions.txt",
                    mime="text/plain",
                )

            else:
                detail = response.json().get("detail", response.text)
                st.error(f"Error {response.status_code}: {detail}")

        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the backend. Make sure FastAPI is running on port 8000.")
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")
