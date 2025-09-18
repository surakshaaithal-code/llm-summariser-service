from typing import Annotated, AsyncGenerator, Optional, Literal

from fastapi import Depends, FastAPI, status, Response, HTTPException
from pydantic import BaseModel, HttpUrl, Field
from redis.asyncio import Redis
import uuid
import os
import httpx
from background_tasks.summarizer import summarize_with_gemma3, SummarizationError
import asyncio


app = FastAPI(title="LLM Summariser Service", version="0.1.0")


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict:
    return {"message": "LLM Summariser Service API"}


# Pydantic models
class DocumentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    URL: HttpUrl


class DocumentResponse(BaseModel):
    document_uuid: str
    status: Literal["PENDING", "SUCCESS", "FAILED"]
    name: str
    URL: HttpUrl
    summary: Optional[str] = None


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


@app.post("/documents/", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponse)
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

            summary_text = await asyncio.to_thread(summarize_with_gemma3, content_text)

            await redis.hset(hash_key, mapping={
                "status": "SUCCESS",
                "summary": summary_text,
            })
        except (httpx.HTTPError, SummarizationError, Exception):
            await redis.hset(hash_key, mapping={
                "status": "FAILED",
                "summary": "",
            })

    # fire-and-forget background work
    task = asyncio.create_task(process_document())


    return DocumentResponse(
        document_uuid=document_uuid,
        status="PENDING",
        name=payload.name,
        URL=payload.URL,
        summary=None,
    )


@app.get("/documents/{document_uuid}/", response_model=DocumentResponse)
async def get_document(document_uuid: str, 
redis: Annotated[Redis, Depends(get_redis)]) -> DocumentResponse:
    hash_key = f"document:{document_uuid}"
    data = await redis.hgetall(hash_key)

    if not data:
        raise HTTPException(status_code=404, detail="Document not found")

    summary_value = data.get("summary")
    summary_normalized = None if summary_value in (None, "") else summary_value

    if "URL" not in data or "name" not in data or "status" not in data:
        raise HTTPException(status_code=500, detail="Corrupt document record")

    return DocumentResponse(
       document_uuid=document_uuid,
       status=data["status"],
       name=data["name"],
       URL=data["URL"],
       summary=summary_normalized,
    )
