# ---- builder: install dependencies into a venv ----
FROM python:3.12-slim AS builder
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# requirements before source: this layer only re-runs when deps change
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- final: slim runtime, non-root, no build toolchain ----
FROM python:3.12-slim
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system app && adduser --system --ingroup app app

# Nothing is installed at runtime -- the app runs out of /opt/venv. But the
# base image's own pip and setuptools are still present in the final layer,
# and Trivy scans them: setuptools 70.3.0 is CVE-2025-47273 (path traversal
# in PackageIndex) and pip 25.0.1 vendors msgpack 1.1.2 (GHSA-6v7p-g79w-8964).
# Upgrade both, pinned, because an unpinned --upgrade makes the image
# unreproducible and that is the property this whole pipeline is built on.
RUN /usr/local/bin/python -m pip install --no-cache-dir --upgrade \
      "pip==26.2.1" "setuptools==84.0.0"
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts

USER app
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]
