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
COPY --from=builder /opt/venv /opt/venv

# Strip the package managers out of the runtime image. The app runs uvicorn
# from /opt/venv and never installs anything, so pip and setuptools are dead
# weight. They are also where the last two HIGH findings came from, and not
# in the way it looked: pip ships _vendor/vendor.txt, a manifest listing what
# it bundles, and Trivy reads it as an installed package list. It named
# msgpack==1.1.2 (GHSA-6v7p-g79w-8964) and setuptools==70.3.0
# (CVE-2025-47273) no matter what was really on disk, which is why upgrading
# the real ones to 26.2.1 and 84.0.0 changed the report by nothing at all.
# Deleting the code is the honest fix rather than an ignore rule, and a
# runtime with no package manager also cannot be made to install anything by
# a process that gets a foothold in it.
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip \
           /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
           /usr/local/lib/python3.12/site-packages/setuptools \
           /usr/local/lib/python3.12/site-packages/setuptools-*.dist-info \
           /usr/local/lib/python3.12/site-packages/pkg_resources \
           /opt/venv/lib/python3.12/site-packages/pip \
           /opt/venv/lib/python3.12/site-packages/pip-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12 \
           /opt/venv/bin/pip /opt/venv/bin/pip3 /opt/venv/bin/pip3.12
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY scripts ./scripts

USER app
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]
