FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN --mount=type=secret,id=build_ca \
    set -eu; \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 STUDIO_PUBLIC=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core tesseract-ocr tesseract-ocr-eng blender espeak-ng \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN --mount=type=secret,id=build_ca \
    set -eu; \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    python -m venv .venv; \
    .venv/bin/python -m pip install -r requirements.txt
COPY backend ./backend
COPY scripts/start.sh scripts/render_story.py ./scripts/
COPY --from=frontend /build/dist ./dist
RUN useradd --create-home --uid 10001 studio && chown -R studio:studio /app
USER studio
EXPOSE 8000
CMD ["bash", "scripts/start.sh"]
