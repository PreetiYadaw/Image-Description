import base64
from typing import List

import fitz  # PyMuPDF
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AzureOpenAI

# ══ Azure OpenAI config ═══════════════════════════════════════════════════════
AZURE_ENDPOINT = "https://sbi-qualitia-ai-services.openai.azure.com/"
AZURE_API_KEY  = "34MLhvjvwIRhWArwx5Qi3cIUXkTewA4v8mFn1hnIMpOtqT74gbzfXJ3w3AAABACOG8iKr"
AZURE_API_VER  = "2024-12-01-preview"
AZURE_MODEL    = "gpt-4.1-mini"

app = FastAPI(title="PDF Image Describer API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    api_key=AZURE_API_KEY,
    api_version=AZURE_API_VER,
)


# ── Pydantic models ───────────────────────────────────────────────────────────
class PageDescription(BaseModel):
    page_number: int
    width: int
    height: int
    description: str


class PDFDescriptionResponse(BaseModel):
    filename: str
    total_pages: int
    descriptions: List[PageDescription]


# ── Core helpers ──────────────────────────────────────────────────────────────
def render_pages_as_images(pdf_bytes: bytes, dpi: int = 150) -> List[dict]:
    """
    Render every PDF page as a PNG (captures vector graphics,
    flowcharts, diagrams — everything visible on the page).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)          # scale factor from 72-DPI base
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")

        pages.append({
            "page_number": page_num + 1,
            "bytes":       img_bytes,
            "width":       pix.width,
            "height":      pix.height,
            "mime":        "image/png",
        })

    doc.close()
    return pages


def describe_page(img_bytes: bytes, page_number: int, total_pages: int) -> str:
    """Send one rendered page to Azure OpenAI and return its description."""
    b64 = base64.b64encode(img_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model=AZURE_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"This is page {page_number} of {total_pages} from a PDF document. "
                            "Describe everything visible on this page in detail. "
                            "If there is a flowchart or diagram, explain: "
                            "(1) what process or system it represents, "
                            "(2) each step or node and what it means, "
                            "(3) the flow/connections between steps, "
                            "(4) any decision points (yes/no branches). "
                            "Also describe any other content — text blocks, tables, images. "
                            "Be thorough and structured."
                        ),
                    },
                ],
            }
        ],
        max_tokens=1000,
    )
    return response.choices[0].message.content


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/describe-pdf", response_model=PDFDescriptionResponse)
async def describe_pdf(file: UploadFile = File(...)):
    # Validate
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50 MB.")

    # Render pages
    try:
        pages = render_pages_as_images(pdf_bytes, dpi=150)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {str(exc)}")

    total_pages = len(pages)

    # Describe each page
    descriptions: List[PageDescription] = []
    for pg in pages:
        try:
            desc_text = describe_page(pg["bytes"], pg["page_number"], total_pages)
        except Exception as exc:
            desc_text = f"Could not describe this page: {str(exc)}"

        descriptions.append(PageDescription(
            page_number=pg["page_number"],
            width=pg["width"],
            height=pg["height"],
            description=desc_text,
        ))

    return PDFDescriptionResponse(
        filename=file.filename or "uploaded.pdf",
        total_pages=total_pages,
        descriptions=descriptions,
    )
