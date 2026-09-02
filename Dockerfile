FROM python:3.11-slim

WORKDIR /app

# Cloud mode calls a managed LLM, but retrieval still needs the small local
# embedding model. Build that artifact once so a request never downloads model
# weights and the Cloud Run instance can start deterministically.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/huggingface \
    TRANSFORMERS_CACHE=/opt/huggingface/hub

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN NIMBUS_ALLOW_MODEL_DOWNLOAD=1 python data/build_index.py

# The deployment script supplies NIMBUS_MODEL_BACKEND=google and the Google
# model settings. Keeping local as the application default preserves the
# original offline workshop path when this image is run without cloud config.
ENV NIMBUS_ALLOW_MODEL_DOWNLOAD=0 \
    PORT=8080

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app:app --app-dir 01_deploy --host 0.0.0.0 --port ${PORT:-8080}"]
