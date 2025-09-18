from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, status
from pydantic import BaseModel, HttpUrl, Field
from redis.asyncio import Redis
import uuid


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
    status: str
    name: str
    URL: HttpUrl
    summary: Optional[str] = None


# Redis dependency
async def get_redis() -> AsyncGenerator[Redis, None]:
    redis = Redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


@app.post("/documents/", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponse)
async def create_document(payload: DocumentCreate, redis: Redis = Depends(get_redis)) -> DocumentResponse:
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

    return DocumentResponse(
        document_uuid=document_uuid,
        status="PENDING",
        name=payload.name,
        URL=payload.URL,
        summary=None,
    )
