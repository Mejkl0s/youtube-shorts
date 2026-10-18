FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 STUDIO_PUBLIC=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core tesseract-ocr tesseract-ocr-eng libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
COPY backend ./backend
COPY scripts/start.sh ./scripts/start.sh
COPY --from=frontend /build/dist ./dist
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
RUN useradd --create-home --uid 10001 studio && chown -R studio:studio /app
USER studio
EXPOSE 8000
CMD ["bash", "scripts/start.sh"]
