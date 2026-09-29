# syntax=docker/dockerfile:1
#
# Multi-stage, pinned, non-root (§3.1).
#
# Stage 1 has Node, the TypeScript compiler, 300-odd MB of node_modules and
# every test file. Stage 2 has nginx and a directory of static assets.
# Nothing from stage 1 reaches the final image except dist/, which is the
# entire point of the split: the attack surface that ships is nginx plus
# HTML, not a Node toolchain.
#
# Measured on this repo, arm64 / Apple Silicon (docs/evidence/image-sizes.txt):
#   builder stage   432 MB
#   final image      86 MB
#
# 85 MB of that final figure is nginx:1.30.5-alpine itself on arm64; the built
# assets are ~200 KB. §3.1's ~60 MB line is about whether the Node toolchain
# leaked into the runtime stage, and it did not: `which node` finds nothing in
# the final image and /app does not exist. On amd64 the same Dockerfile lands
# near 55 MB because the alpine base is smaller there.

# ---- stage 1: build ----------------------------------------------------
FROM node:22.9.0-alpine AS builder

WORKDIR /app

# Manifests before source. This layer is cached until a dependency actually
# changes, so editing a component does not re-run npm ci (§3.1 "cache-friendly
# COPY order"). `npm ci` not `npm install`: it installs exactly the lockfile.
COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src

# tsc --noEmit runs first: a type error fails the image build rather than
# shipping a bundle that throws in a citizen's browser.
RUN npm run build

# ---- stage 2: serve ----------------------------------------------------
FROM nginx:1.30.5-alpine AS runtime

# Patch the OS packages sitting on top of the pinned base. Trivy flagged
# libexpat 2.8.4-r0 (CVE-2026-93990, XML injection via malformed UTF-16),
# fixed in 2.8.5-r0. Alpine has shipped the fix; the nginx image has not been
# rebuilt with it yet, and base images are always rebuilt on a slower cadence
# than CVEs land. The tag stays pinned -- this patches what is inside it.
# The cost is that the image is no longer byte-identical when rebuilt from
# the tag alone. That is acceptable here precisely because CD never redeploys
# by tag: it builds once, records the digest, and deploys that SHA, so what
# runs is identified by what was built and scanned rather than re-derived.
RUN apk --no-cache upgrade

# Config as a template: nginx:alpine's own entrypoint runs envsubst over
# /etc/nginx/templates/*.template at start, so BACKEND_ORIGIN is resolved per
# environment, not per build.
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.d/10-config-js.sh /docker-entrypoint.d/10-config-js.sh
COPY --from=builder /app/dist /usr/share/nginx/html

# Non-root. nginx:alpine already ships an unprivileged `nginx` user (uid 101),
# so the work is making the paths it must write to writable by that user and
# moving the listener off port 80 -- a non-root process cannot bind below 1024.
RUN chmod +x /docker-entrypoint.d/10-config-js.sh && \
    sed -i 's|^pid .*|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf && \
    sed -i '/^user /d' /etc/nginx/nginx.conf && \
    mkdir -p /var/cache/nginx /var/run && \
    chown -R nginx:nginx /var/cache/nginx /var/run /usr/share/nginx/html /etc/nginx/conf.d

ENV BACKEND_ORIGIN="http://backend:8000" \
    API_BASE="/api" \
    NGINX_ENTRYPOINT_QUIET_LOGS=1

USER nginx
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null 2>&1 || exit 1

# Exec form, so nginx is PID 1 and receives SIGTERM directly. In shell form
# the signal would go to /bin/sh and the rolling update would hard-kill it.
CMD ["nginx", "-g", "daemon off;"]
