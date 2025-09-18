FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=2.2.0 \
    POETRY_HOME=/opt/poetry
RUN curl -sSL https://install.python-poetry.org | python3 - --yes && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Copy only pyproject files first for better caching
COPY pyproject.toml poetry.lock* ./

# Configure Poetry to not create virtualenvs inside Docker
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copy the rest of the application
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


