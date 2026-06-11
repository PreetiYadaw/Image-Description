import base64
import io
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

app = FastAPI(title="PDF Image Describer API", version="2.0.0")

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


class ImageDescription(BaseModel):
    image_index: int       # 1-based index across the whole PDF
    page_number: int       # page where the image was found
    width: int
    height: int
    description: str


class PDFDescriptionResponse(BaseModel):
    filename: str
    total_pages: int
    total_images_found: int
    descriptions: List[ImageDescription]


def extract_images_from_pdf(pdf_bytes: bytes) -> List[dict]:
    """
    Extract every embedded image from a PDF using PyMuPDF.
    Returns a list of dicts: {page, img_index, bytes, width, height, mime}.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    global_idx = 1

    for page_num in range(len(doc)):
        page = doc[page_num]
        img_list = page.get_images(full=True)

        for img_info in img_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                ext = base_image["ext"].lower()          # e.g. "jpeg", "png"
                width = base_image["width"]
                height = base_image["height"]

                # Skip tiny images (icons, bullets, decorations)
                if width < 50 or height < 50:
                    continue

                mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"

                images.append({
                    "image_index": global_idx,
                    "page_number": page_num + 1,
                    "bytes": img_bytes,
                    "width": width,
                    "height": height,
                    "mime": mime,
                })
                global_idx += 1

            except Exception:
                continue  # skip unreadable image streams

    doc.close()
    return images


def describe_single_image(img_bytes: bytes, mime: str, image_index: int, page_number: int) -> str:
    """Send one image to Azure OpenAI and return its description."""
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
                            "url": f"data:{mime};base64,{b64}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"This is image #{image_index} from page {page_number} of a PDF document. "
                            "Provide a detailed, structured description covering: "
                            "(1) overall subject or purpose of the image, "
                            "(2) key objects, people, or elements visible, "
                            "(3) colors, layout, and visual style, "
                            "(4) any text, labels, or data visible in the image. "
                            "Be thorough but concise."
                        ),
                    },
                ],
            }
        ],
        max_tokens=800,
    )
    return response.choices[0].message.content


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/describe-pdf", response_model=PDFDescriptionResponse)
async def describe_pdf(file: UploadFile = File(...)):
    # Validate PDF
    if file.content_type not in ("application/pdf", "application/octet-stream") and \
       not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()

    if len(pdf_bytes) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50 MB.")

    # Extract images
    try:
        images = extract_images_from_pdf(pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {str(exc)}")

    if not images:
        raise HTTPException(status_code=404, detail="No images found in this PDF.")

    # Get page count
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    doc.close()

    # Describe each image via Azure OpenAI
    descriptions: List[ImageDescription] = []
    for img in images:
        try:
            desc_text = describe_single_image(
                img["bytes"], img["mime"], img["image_index"], img["page_number"]
            )
        except Exception as exc:
            desc_text = f"Could not describe this image: {str(exc)}"

        descriptions.append(ImageDescription(
            image_index=img["image_index"],
            page_number=img["page_number"],
            width=img["width"],
            height=img["height"],
            description=desc_text,
        ))

    return PDFDescriptionResponse(
        filename=file.filename or "uploaded.pdf",
        total_pages=total_pages,
        total_images_found=len(images),
        descriptions=descriptions,
    )
