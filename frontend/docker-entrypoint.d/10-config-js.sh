#!/bin/sh
# nginx:alpine runs everything in /docker-entrypoint.d/ before starting nginx.
# This writes the runtime config the browser reads (index.html loads
# /config.js before the bundle), turning environment variables into
# configuration WITHOUT a rebuild.
#
# This is the file that makes build-once-deploy-many true for the frontend.
# The alternative -- import.meta.env.VITE_API_URL -- is inlined by Vite at
# build time and would give us one image per environment.
set -eu

: "${API_BASE:=/api}"

cat > /usr/share/nginx/html/config.js <<EOF
// Generated at container start. Do not commit; do not edit by hand.
window.__CIVICPULSE_CONFIG__ = {
  apiBase: "${API_BASE}"
};
EOF

echo "[entrypoint] wrote /config.js with apiBase=${API_BASE}"
