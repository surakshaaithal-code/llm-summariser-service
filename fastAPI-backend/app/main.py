from fastapi import FastAPI


app = FastAPI(title="LLM Summariser Service", version="0.1.0")


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict:
    return {"message": "LLM Summariser Service API"}
