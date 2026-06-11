import base64
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AzureOpenAI

# ══ Azure OpenAI config ═══════════════════════════════════════════════════════
AZURE_ENDPOINT = "https://sbi-qualitia-ai-services.openai.azure.com/"
AZURE_API_KEY  = "34MLhvjvwIRhWArwx5Qi3cIUXkTewA4v8mFn1hnIMpOtqT74gbzfXJ3w3AAABACOG8iKr"
AZURE_API_VER  = "2024-12-01-preview"
AZURE_MODEL    = "gpt-4.1-mini"

app = FastAPI(title="Image Describer API", version="1.0.0")

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


class DescriptionResponse(BaseModel):
    description: str
    filename: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/describe", response_model=DescriptionResponse)
async def describe_image(file: UploadFile = File(...)):
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, GIF, WEBP."
        )

    image_bytes = await file.read()
    if len(image_bytes) > 20 * 1024 * 1024:  # 20 MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 20 MB.")

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    mime_type = file.content_type

    try:
        response = client.chat.completions.create(
            model=AZURE_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{b64_image}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Provide a detailed, structured description of this image. "
                                "Cover: (1) what the image shows overall, (2) key subjects or objects, "
                                "(3) colors, lighting and mood, (4) any text or notable details visible. "
                                "Be thorough but concise."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )
        description = response.choices[0].message.content

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Azure OpenAI error: {str(exc)}")

    return DescriptionResponse(description=description, filename=file.filename or "uploaded_image")
