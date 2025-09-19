from typing import Annotated, AsyncGenerator, Optional, Literal

from fastapi import Depends, FastAPI, status, Response, HTTPException
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, HttpUrl, Field
from redis.asyncio import Redis
import uuid
import os
import httpx
from background_tasks.summarizer import summarize_with_gemma3, SummarizationError
import asyncio


app = FastAPI(
    title="LLM Summariser Service",
    version="0.1.0",
    description=(
        "Asynchronous API to fetch web content and produce concise summaries using a local "
        "Ollama model (Gemma3). Create a document with a URL to start background summarization, "
        "then poll the document resource to retrieve progress and the final summary."
    ),
    contact={
        "name": "LLM Summariser Team",
        "url": "https://example.com",
    },
    license_info={
        "name": "MIT",
        "identifier": "MIT",
    },
    openapi_tags=[
        {
            "name": "health",
            "description": "Health and root endpoints used for basic service checks.",
        },
        {
            "name": "documents",
            "description": (
                "Operations to create a document summarization job and retrieve its status/summary."
            ),
        },
    ],
)


@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    description="Returns a simple status payload indicating the API is responsive.",
)
async def health_check() -> dict:
    return {"status": "ok"}


@app.get(
    "/",
    tags=["health"],
    summary="Service root",
    description="Basic welcome message for the LLM Summariser Service API.",
)
async def root() -> dict:
    return {"message": "LLM Summariser Service API"}


# Pydantic models
class DocumentCreate(BaseModel):
    """Payload to request summarization of a public web page.

    Provide a human-friendly name and a valid absolute URL to the content that should be
    fetched and summarized in the background.
    """

    name: str = Field(
        ..., min_length=1,
        description="Human-readable name for the document/job.",
        json_schema_extra={"examples": ["Example Doc", "FastAPI Tutorial"]},
    )
    URL: HttpUrl = Field(
        ..., description="Absolute URL to the public web page to summarize.",
        json_schema_extra={"examples": ["https://example.com/article", "https://fastapi.tiangolo.com"]},
    )


class DocumentResponse(BaseModel):
    """Representation of a document summarization job state and result."""

    document_uuid: str = Field(
        ..., description="Server-generated UUID for the document/job.",
        json_schema_extra={"examples": ["4b1b2a5a-2f2c-4f18-8f7b-1d1a9f1f5c3e"]},
    )
    status: Literal["PENDING", "SUCCESS", "FAILED"] = Field(
        ..., description="Current processing state of the job.",
        json_schema_extra={"examples": ["PENDING"]},
    )
    name: str = Field(
        ..., description="Echo of the submitted name.",
        json_schema_extra={"examples": ["Example Doc"]},
    )
    URL: HttpUrl = Field(
        ..., description="Echo of the submitted URL (normalized).",
        json_schema_extra={"examples": ["https://example.com/"]},
    )
    summary: Optional[str] = Field(
        default=None,
        description=(
            "Summary text produced by the model when status is SUCCESS; null otherwise."
        ),
        json_schema_extra={"examples": ["This article explains..."]},
    )
    data_progress: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Progress indicator from 0.0 to 1.0 across fetch, summarize, and store steps.",
        json_schema_extra={"examples": [0.0, 0.25, 0.5, 0.75, 1.0]},
    )


# Redis dependency
async def get_redis() -> AsyncGenerator[Redis, None]:
    redis = Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"),
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
    )
    try:
        yield redis
    finally:
        await redis.aclose()


@app.post(
    "/documents/",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentResponse,
    tags=["documents"],
    summary="Create a summarization job",
    description=(
        "Create a new document resource by providing a name and a public URL. The server "
        "fetches the content and performs summarization asynchronously. Use the Location "
        "header or the document UUID to poll job status and retrieve the result."
    ),
    responses={
        202: {
            "description": "Job accepted; polling endpoint returned in Location header.",
            "model": DocumentResponse,
        },
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def create_document(payload: DocumentCreate, 
redis: Annotated[Redis, Depends(get_redis)],
response:Response,
) -> DocumentResponse:
    document_uuid = str(uuid.uuid4())

    # Prepare fields to store in Redis hash
    hash_key = f"document:{document_uuid}"
    fields = {
        "status": "PENDING",
        "name": payload.name,
        "URL": str(payload.URL),
        "summary": "",  # store empty string to represent null
        "data_progress": "0.0",
    }

    await redis.hset(hash_key, mapping=fields)
    response.headers["Location"] = app.url_path_for("get_document", document_uuid=document_uuid)

    async def process_document() -> None:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                fetch_resp = await client.get(
                    str(payload.URL),
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/125.0.0.0 Safari/537.36"
                        )
                    },
                )
                fetch_resp.raise_for_status()
                content_text = fetch_resp.text
            # 25% - content fetched
            await redis.hset(hash_key, mapping={"data_progress": "0.25"})

            # 50% - about to start summarization
            await redis.hset(hash_key, mapping={"data_progress": "0.50"})

            summary_text = await summarize_with_gemma3(content_text)

            # 75% - summarization complete, about to store
            await redis.hset(hash_key, mapping={"data_progress": "0.75"})

            await redis.hset(hash_key, mapping={
                "status": "SUCCESS",
                "summary": summary_text,
                "data_progress": "1.0",
            })
        except (httpx.HTTPError, SummarizationError, Exception):
            await redis.hset(hash_key, mapping={
                "status": "FAILED",
                "summary": "",
                "data_progress": "1.0",
            })

    # fire-and-forget background work
    task = asyncio.create_task(process_document())
    


    return DocumentResponse(
        document_uuid=document_uuid,
        status="PENDING",
        name=payload.name,
        URL=payload.URL,
        summary=None,
        data_progress=0.0,
    )


@app.get(
    "/documents/{document_uuid}/",
    response_model=DocumentResponse,
    tags=["documents"],
    summary="Get a summarization job",
    description=(
        "Retrieve the current state of a document summarization job, including progress and "
        "final summary when available."
    ),
    responses={
        200: {"description": "Current job state returned.", "model": DocumentResponse},
        404: {"description": "Document not found"},
        500: {"description": "Corrupt document record"},
    },
)
async def get_document(document_uuid: str, 
redis: Annotated[Redis, Depends(get_redis)]) -> DocumentResponse:
    hash_key = f"document:{document_uuid}"
    data = await redis.hgetall(hash_key)

    if not data:
        raise HTTPException(status_code=404, detail="Document not found")

    summary_value = data.get("summary")
    summary_normalized = None if summary_value in (None, "") else summary_value
    progress_raw = data.get("data_progress", "0.0")
    try:
        progress_value = float(progress_raw)
    except (TypeError, ValueError):
        progress_value = 0.0

    if "URL" not in data or "name" not in data or "status" not in data:
        raise HTTPException(status_code=500, detail="Corrupt document record")

    return DocumentResponse(
       document_uuid=document_uuid,
       status=data["status"],
       name=data["name"],
       URL=data["URL"],
       summary=summary_normalized,
       data_progress=progress_value,
    )
