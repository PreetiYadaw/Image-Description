import base64
import json
from typing import List, Optional

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

app = FastAPI(title="PDF Analyzer API", version="4.0.0")

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


# ══ Pydantic models ════════════════════════════════════════════════════════════
class TextBlock(BaseModel):
    text: str
    x: float        # left position (points from left edge)
    y: float        # top position (points from top edge)
    width: float
    height: float


class PageAnalysis(BaseModel):
    page_number: int
    page_width: float
    page_height: float
    text_blocks: List[TextBlock]   # all OCR'd text with positions
    description: str               # combined LLM description


class PDFAnalysisResponse(BaseModel):
    filename: str
    total_pages: int
    pages: List[PageAnalysis]


# ══ Step 1 — Render page to PNG ════════════════════════════════════════════════
def render_page(page: fitz.Page, dpi: int = 200) -> bytes:
    """
    Render a single PDF page to PNG bytes.
    200 DPI gives crisp text in flowchart boxes — important for the LLM to read labels.
    """
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("png")


# ══ Step 2 — Extract text with positions (OCR-style) ═══════════════════════════
def extract_text_blocks(page: fitz.Page) -> List[TextBlock]:
    """
    Extract every text span from the page along with its bounding box.
    PyMuPDF gives us exact x,y coordinates for each piece of text —
    this is what lets the LLM understand spatial layout of flowchart nodes.

    get_text("rawdict") returns a nested structure:
      page → blocks → lines → spans → text + bbox
    """
    blocks_out: List[TextBlock] = []
    raw = page.get_text("rawdict")  # richest format: includes bbox per span

    for block in raw.get("blocks", []):
        if block.get("type") != 0:   # type 0 = text, type 1 = image — skip image blocks
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                bbox = span.get("bbox", [0, 0, 0, 0])  # [x0, y0, x1, y1]
                blocks_out.append(TextBlock(
                    text=text,
                    x=round(bbox[0], 1),
                    y=round(bbox[1], 1),
                    width=round(bbox[2] - bbox[0], 1),
                    height=round(bbox[3] - bbox[1], 1),
                ))

    return blocks_out


# ══ Step 3 — Format text map for the LLM prompt ════════════════════════════════
def format_text_map(text_blocks: List[TextBlock], page_width: float, page_height: float) -> str:
    """
    Convert positional text blocks into a human-readable spatial map.

    Instead of raw coordinates we use relative positions (top-left, center, etc.)
    so the LLM can reason about layout without needing to parse numbers.

    Also groups nearby text blocks that likely belong to the same flowchart node.
    """
    if not text_blocks:
        return "No text detected on this page."

    lines = [
        f"Page dimensions: {page_width:.0f} x {page_height:.0f} points",
        "Text elements found (with approximate positions):",
        ""
    ]

    for i, tb in enumerate(text_blocks, 1):
        # Convert absolute coords to relative position label
        rel_x = tb.x / page_width
        rel_y = tb.y / page_height

        if rel_x < 0.33:
            h_pos = "left"
        elif rel_x < 0.66:
            h_pos = "center"
        else:
            h_pos = "right"

        if rel_y < 0.25:
            v_pos = "top"
        elif rel_y < 0.50:
            v_pos = "upper-middle"
        elif rel_y < 0.75:
            v_pos = "lower-middle"
        else:
            v_pos = "bottom"

        lines.append(
            f"  [{i}] \"{tb.text}\"  →  position: {v_pos}-{h_pos}  "
            f"(x={tb.x:.0f}, y={tb.y:.0f})"
        )

    return "\n".join(lines)


# ══ Step 4 — Combined LLM call (image + text map) ══════════════════════════════
def describe_page_with_context(
    img_bytes: bytes,
    text_map: str,
    page_number: int,
    total_pages: int,
) -> str:
    """
    Sends BOTH the rendered page image AND the extracted text-with-positions
    to the LLM in a single call.

    System prompt:  sets the role and output format
    User prompt:    contains the image + the text map side by side
    """
    b64 = base64.b64encode(img_bytes).decode("utf-8")

    system_prompt = (
        "You are an expert document analyst specializing in flowcharts, "
        "process diagrams, and technical documentation. "
        "When analyzing a page that contains a flowchart or process diagram, "
        "you MUST describe the complete flow step-by-step in order, "
        "including every decision point and branch. "
        "Use the provided text position map to identify node labels accurately "
        "and cross-reference with the visual image to determine connections and arrows. "
        "Structure your response clearly with sections: "
        "OVERVIEW, FLOW DESCRIPTION (step-by-step), DECISION POINTS, and OTHER CONTENT."
    )

    user_prompt = (
        f"This is page {page_number} of {total_pages} from a PDF document.\n\n"
        "I am providing you TWO sources of information about this page:\n"
        "1. The rendered page image (visual)\n"
        "2. A text extraction map showing all text found on the page with their "
        "approximate positions\n\n"
        "Use BOTH sources together to give the most accurate description.\n"
        "The text map helps you read exact labels; the image shows you arrows, "
        "shapes, and connections.\n\n"
        "--- TEXT POSITION MAP ---\n"
        f"{text_map}\n"
        "--- END TEXT MAP ---\n\n"
        "Now analyze the page image along with the text map above and provide a "
        "detailed structured description. "
        "If this page contains a flowchart or diagram:\n"
        "  - List every node/step in the correct order\n"
        "  - Describe every arrow and what it connects\n"
        "  - Explain every YES/NO or other decision branch\n"
        "  - Describe the start and end points\n"
        "If the page has other content (text, tables, images), describe those too."
    )

    response = client.chat.completions.create(
        model=AZURE_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64}",
                            "detail": "high",   # high = full resolution analysis
                        },
                    },
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                ],
            },
        ],
        max_tokens=2000,   # increased — flowchart descriptions need more tokens
    )
    return response.choices[0].message.content


# ══ Endpoints ═════════════════════════════════════════════════════════════════
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/describe-pdf", response_model=PDFAnalysisResponse)
async def describe_pdf(file: UploadFile = File(...)):
    # ── Validate ──────────────────────────────────────────────────────────────
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 50 MB.")

    # ── Open PDF ──────────────────────────────────────────────────────────────
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {str(exc)}")

    total_pages = len(doc)
    pages_out: List[PageAnalysis] = []

    for page_num in range(total_pages):
        page = doc[page_num]
        page_width  = page.rect.width
        page_height = page.rect.height

        # Step 1: render to image
        try:
            img_bytes = render_page(page, dpi=200)
        except Exception as exc:
            img_bytes = None
            render_error = str(exc)

        # Step 2: extract text with positions
        try:
            text_blocks = extract_text_blocks(page)
        except Exception:
            text_blocks = []

        # Step 3: format text map
        text_map = format_text_map(text_blocks, page_width, page_height)

        # Step 4: call LLM with both image + text map
        if img_bytes:
            try:
                description = describe_page_with_context(
                    img_bytes, text_map, page_num + 1, total_pages
                )
            except Exception as exc:
                description = f"LLM error on page {page_num + 1}: {str(exc)}"
        else:
            description = f"Could not render page {page_num + 1}: {render_error}"

        pages_out.append(PageAnalysis(
            page_number=page_num + 1,
            page_width=round(page_width, 1),
            page_height=round(page_height, 1),
            text_blocks=text_blocks,
            description=description,
        ))

    doc.close()

    return PDFAnalysisResponse(
        filename=file.filename or "uploaded.pdf",
        total_pages=total_pages,
        pages=pages_out,
    )
