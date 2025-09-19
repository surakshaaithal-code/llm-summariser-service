# LLM Summariser Service

FastAPI-based asynchronous web service that summarizes text content from URLs using a local Ollama Gemma3:1B LLM. Supports concurrent requests, task progress tracking, and Docker containerization for easy deployment.

## Features

- **Asynchronous Processing**: Submit URLs for summarization and poll for results
- **Progress Tracking**: Real-time progress updates from 0% to 100%
- **Interactive API Documentation**: SwaggerUI available at `/docs` endpoint
- **Docker Support**: Complete containerized setup with Redis and Ollama
- **Robust Error Handling**: Comprehensive error responses and status tracking

## Quick Start

### Using Docker Compose (Recommended)

1. **Start the services**:
   ```bash
   docker compose up -d --build
   ```

2. **Access the API**:
   - API Base URL: `http://localhost:8000`
   - Interactive Documentation: `http://localhost:8000/docs`
   - OpenAPI Schema: `http://localhost:8000/openapi.json`

3. **Test the API**:
   ```bash
   # Create a summarization job
   curl -X POST "http://localhost:8000/documents/" \
        -H "Content-Type: application/json" \
        -d '{"name": "Example Article", "URL": "https://example.com"}'
   
   # Check job status (use the returned document_uuid)
   curl "http://localhost:8000/documents/{document_uuid}/"
   ```

## API Documentation

### Interactive Documentation

Visit `http://localhost:8000/docs` to access the interactive SwaggerUI documentation where you can:

- Explore all available endpoints
- View request/response schemas with examples
- Test API calls directly from the browser
- Download the OpenAPI specification

### Endpoints

#### Health Check
- `GET /health` - Service health status
- `GET /` - Service welcome message

#### Document Operations
- `POST /documents/` - Create a new summarization job
- `GET /documents/{document_uuid}/` - Retrieve job status and summary

### Request/Response Examples

#### Create Document
```json
POST /documents/
{
  "name": "FastAPI Tutorial",
  "URL": "https://fastapi.tiangolo.com"
}
```

Response:
```json
{
  "document_uuid": "4b1b2a5a-2f2c-4f18-8f7b-1d1a9f1f5c3e",
  "status": "PENDING",
  "name": "FastAPI Tutorial",
  "URL": "https://fastapi.tiangolo.com",
  "summary": null,
  "data_progress": 0.0
}
```

#### Get Document Status
```json
GET /documents/{document_uuid}/
```

Response (when complete):
```json
{
  "document_uuid": "4b1b2a5a-2f2c-4f18-8f7b-1d1a9f1f5c3e",
  "status": "SUCCESS",
  "name": "FastAPI Tutorial",
  "URL": "https://fastapi.tiangolo.com",
  "summary": "FastAPI is a modern, fast web framework for building APIs with Python...",
  "data_progress": 1.0
}
```

## Architecture

### Services

- **FastAPI Backend**: Main API service running on port 8000
- **Redis**: In-memory data store for job state and results
- **Ollama**: Local LLM service hosting Gemma3:1B model
- **Ollama Init**: One-time setup container to pull the model

### Processing Flow

1. **Submit**: POST to `/documents/` with name and URL
2. **Process**: Background task fetches content and generates summary
3. **Track**: Poll `/documents/{uuid}/` to monitor progress
4. **Retrieve**: Get final summary when `status` is "SUCCESS"

### Status Values

- `PENDING`: Job is being processed
- `SUCCESS`: Summary completed successfully
- `FAILED`: Processing failed (check logs for details)

## Development

### Local Development

1. **Install dependencies**:
   ```bash
   cd fastAPI-backend
   poetry install
   ```

2. **Start services**:
   ```bash
   # Start Redis and Ollama
   docker compose up redis ollama -d
   
   # Start FastAPI (in another terminal)
   cd fastAPI-backend
   poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Run tests**:
   ```bash
   cd fastAPI-backend
   poetry run pytest
   ```

### Environment Variables

- `REDIS_URL`: Redis connection string (default: `redis://localhost:6379`)
- `OLLAMA_HOST`: Ollama service URL (default: `http://localhost:11434`)

## Troubleshooting

### Common Issues

1. **Document not found (404)**:
   - Ensure you're using the correct UUID from the creation response
   - Check that the document exists in Redis

2. **Summary not available**:
   - Wait for background processing to complete
   - Check the `status` field - it should be "SUCCESS"
   - If status is "FAILED", check container logs for errors

3. **Ollama connection issues**:
   - Ensure Ollama service is running: `docker compose ps`
   - Check model is available: `docker exec ollama ollama list`

### Logs

```bash
# View API logs
docker logs summarizer-api

# View Ollama logs
docker logs ollama

# View Redis logs
docker logs redis
```

## Integration Tests

The project includes comprehensive integration tests that test concurrent operations with real Redis and Ollama services.

### Running Integration Tests

1. **Start the required services:**
   ```bash
   # Start Redis and Ollama
   docker-compose up redis ollama ollama-init
   
   # In another terminal, start the API
   docker-compose up api
   ```

2. **Run the integration tests:**
   ```bash
   cd fastAPI-backend
   
   # Option 1: Use the test runner script
   python run_integration_tests.py
   
   # Option 2: Run pytest directly
   pytest tests/test_integration_concurrency.py -v -s
   ```

### What the Integration Tests Cover

The integration tests (`test_integration_concurrency.py`) include:

- **Concurrent Document Creation**: Tests creating multiple documents simultaneously using various URLs from moonhoneytravel.com
- **Concurrent Document Retrieval**: Tests retrieving document status and summaries concurrently
- **Completion Verification**: Waits for all documents to complete processing and verifies summaries
- **Stress Testing**: Tests high-concurrency scenarios with multiple batches of requests

### Test URLs

The integration tests use real URLs from [Moon & Honey Travel](https://www.moonhoneytravel.com):
- Homepage and about page
- Country-specific travel guides (Dolomites, Slovenia, Austria, Switzerland, Italy, Spain, Portugal, Montenegro)

### Prerequisites

- Redis running on `localhost:6379`
- Ollama running on `localhost:11434` with `gemma3:1b` model
- API running on `localhost:8000`
- Internet connection (to fetch test URLs)

## License

MIT License - see LICENSE file for details.
