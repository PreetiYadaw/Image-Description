import streamlit as st
import requests

st.set_page_config(
    page_title="PDF Analyzer",
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
    .hero p { color: #8B92A8; font-size: 1.05rem; font-weight: 300; max-width: 560px; margin: 0 auto; }

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
        border-radius: 16px; padding: 1.5rem; margin-bottom: 1.5rem;
    }
    .page-header {
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;
    }
    .page-badge {
        background: linear-gradient(135deg, #6C8EFF22, #A78BFA22);
        border: 1px solid #6C8EFF44; color: #A78BFA;
        border-radius: 8px; padding: 0.25rem 0.75rem; font-size: 0.82rem; font-weight: 600;
    }
    .dim-tag { color: #3D4466; font-size: 0.75rem; }

    .section-label {
        font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
        text-transform: uppercase; margin-bottom: 0.5rem;
    }
    .desc-box {
        background: #0F1117; border: 1px solid #1E2540;
        border-left: 3px solid #6C8EFF; border-radius: 0 10px 10px 0;
        padding: 1rem 1.25rem; color: #C8CCDD;
        line-height: 1.85; font-size: 0.94rem; white-space: pre-wrap;
    }
    .ocr-box {
        background: #0F1117; border: 1px solid #1E2540;
        border-left: 3px solid #F472B644; border-radius: 0 10px 10px 0;
        padding: 0.75rem 1rem; color: #7B8099;
        font-family: monospace; font-size: 0.8rem;
        line-height: 1.7; max-height: 220px; overflow-y: auto;
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

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>PDF Analyzer</h1>
    <p>Combines OCR text extraction + visual AI analysis for accurate flowchart and diagram understanding.</p>
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
                    text-transform:uppercase;color:#6C8EFF;margin-bottom:1rem;">Enhanced Analysis Pipeline</div>
        <div style="color:#8B92A8;font-size:0.92rem;line-height:2.3;">
            ① Upload PDF<br>
            ② Each page is rendered at 200 DPI<br>
            ③ OCR extracts text + exact positions<br>
            ④ LLM receives image <b>+</b> text map together<br>
            ⑤ Accurate flowchart flow is reconstructed
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Results ───────────────────────────────────────────────────────────────────
if uploaded_file and analyze_btn:
    st.markdown("---")

    with st.spinner("Running OCR + AI analysis on each page…"):
        try:
            uploaded_file.seek(0)
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            response = requests.post(f"{BACKEND_URL}/describe-pdf", files=files, timeout=600)

            if response.status_code == 200:
                data = response.json()
                pages = data["pages"]
                total_text_blocks = sum(len(p["text_blocks"]) for p in pages)

                # Stats
                st.markdown(f"""
                <div class="stats-bar">
                    <div class="stat">
                        <div class="stat-val">{data['total_pages']}</div>
                        <div class="stat-lbl">Pages</div>
                    </div>
                    <div class="stat">
                        <div class="stat-val">{total_text_blocks}</div>
                        <div class="stat-lbl">Text Elements Extracted</div>
                    </div>
                    <div class="stat">
                        <div class="stat-val">{len(pages)}</div>
                        <div class="stat-lbl">Pages Analyzed</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # One card per page
                for pg in pages:
                    st.markdown(f"""
                    <div class="page-card">
                        <div class="page-header">
                            <span class="page-badge">Page {pg['page_number']}</span>
                            <span class="dim-tag">
                                {pg['page_width']:.0f} × {pg['page_height']:.0f} pt
                                &nbsp;·&nbsp; {len(pg['text_blocks'])} text elements
                            </span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # AI Description
                    st.markdown(
                        '<div class="section-label" style="color:#6C8EFF;">🤖 AI Description</div>',
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f'<div class="desc-box">{pg["description"]}</div>',
                        unsafe_allow_html=True
                    )

                    # OCR Text Map (collapsible)
                    if pg["text_blocks"]:
                        with st.expander(f"📋 Raw OCR text ({len(pg['text_blocks'])} elements) — Page {pg['page_number']}"):
                            ocr_lines = []
                            for i, tb in enumerate(pg["text_blocks"], 1):
                                ocr_lines.append(
                                    f"[{i:02d}]  \"{tb['text']}\"  "
                                    f"@ x={tb['x']:.0f}, y={tb['y']:.0f}  "
                                    f"({tb['width']:.0f}×{tb['height']:.0f})"
                                )
                            st.markdown(
                                f'<div class="ocr-box">' + "<br>".join(ocr_lines) + "</div>",
                                unsafe_allow_html=True
                            )

                    st.markdown("<br>", unsafe_allow_html=True)

                # Download report
                report_lines = [
                    "PDF Analysis Report",
                    f"File: {data['filename']}",
                    f"Total pages: {data['total_pages']}",
                    f"Total text elements: {total_text_blocks}",
                    "=" * 70,
                ]
                for pg in pages:
                    report_lines += [
                        f"\n{'='*70}",
                        f"PAGE {pg['page_number']}  "
                        f"({pg['page_width']:.0f}×{pg['page_height']:.0f} pt  |  "
                        f"{len(pg['text_blocks'])} text elements)",
                        "=" * 70,
                        "\n[AI DESCRIPTION]",
                        pg["description"],
                        "\n[OCR TEXT ELEMENTS]",
                    ]
                    for i, tb in enumerate(pg["text_blocks"], 1):
                        report_lines.append(
                            f"  [{i}] \"{tb['text']}\"  x={tb['x']}, y={tb['y']}"
                        )

                st.download_button(
                    label="⬇ Download full report",
                    data="\n".join(report_lines),
                    file_name=f"{uploaded_file.name}_analysis.txt",
                    mime="text/plain",
                )

            else:
                detail = response.json().get("detail", response.text)
                st.error(f"Error {response.status_code}: {detail}")

        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the backend. Make sure FastAPI is running on port 8000.")
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")
