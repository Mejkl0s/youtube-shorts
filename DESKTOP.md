# Rank Studio Desktop — architecture and delivery

## Decision (before implementation)

The existing product is a React 19 / TypeScript / Vite editor with a FastAPI
Python 3.12 backend. FFmpeg/ffprobe perform real media processing; yt-dlp and
public search retrieve remote sources; Piper/ONNX provide offline speech,
Edge TTS requires Microsoft connectivity, and Tesseract is optional OCR.
There is no cloud database. Media, source sessions and exports live in
`.runtime`; the web editor stores its project, source history and conversation
in browser localStorage. Optional owner authentication protects web hosting.
Existing local vision uses a fixed loopback Ollama endpoint and allowlisted
Qwen models. The existing launcher and public image block paid AI by default.

Electron is selected over Tauri because the project already has a Node build
toolchain, needs reliable Chromium H.264/AAC video playback and desktop download
handling, and can reuse its complete React editor. A separate Rust layer would
not replace the Python video/AI dependencies. Electron costs more RAM; no claim
of Tauri-like footprint is made. This is an installed, offline-capable application
with an owned bundled backend, native dialogs, tray, persistent app data and
secure credentials, rather than a window loading the Render website.

## Boundaries

- Electron main owns the app lifecycle, windows, tray, file dialogs, app
  settings, update client and a private Python sidecar process. Credentials
  have a separate encrypted store.
- The production renderer loads only the bundled editor through an authenticated
  loopback origin on an ephemeral port. No Vite or externally hosted frontend is
  needed. Node integration is disabled; context isolation and sandboxing are on.
  A narrow preload API validates IPC senders; external navigation is denied.
- The sidecar binds only 127.0.0.1, requires a per-launch random token, and owns
  cancellable media and AI work. Electron injects the token into requests to
  that origin only. Keys are never embedded in URLs or renderer storage.
- Desktop AI configuration, model discovery and provider adapters are separate
  modules. Ollama native chat, OpenAI-compatible APIs, Anthropic Messages and
  Gemini have distinct request/response adapters. Model IDs come from provider
  discovery; unavailable/unsupported capabilities are reported explicitly.
- Local endpoints must be loopback URLs. Cloud endpoints require HTTPS.
  Neither redirects nor environment proxies may redirect provider credentials.
  Cloud use is explicit; there is no silent provider fallback.
- Windows credentials are protected with user-scoped DPAPI, separate from
  ordinary configuration. Non-Windows development uses memory-only secrets,
  with the limitation shown in the UI. No plaintext fallback is permitted.
  Credentials are scoped by provider and endpoint origin; changing a custom
  server does not forward its old key to a different authority.
- A job snapshots its AI selection: changing the default affects new jobs and
  does not change the provider halfway through an existing review.
- Offline editing, existing local media, exports and installed local models
  remain usable; internet search/download, Edge TTS, cloud AI, model downloads
  and update discovery require connectivity.

## Data and migration

Desktop data lives under Electron's per-user application directory, outside the
installation. The sidecar uses its `runtime` subdirectory for existing media
formats. Desktop projects/history use versioned local snapshots with atomic
writes and backups. Browser localStorage cannot be read from a different browser
profile automatically; explicit web export / desktop import is required.
Importing an existing studio folder copies its media and records a migration
marker; originals are retained. Project export/import includes referenced local
assets, and excludes credentials, `.env` and source cookies. Uninstall and update
must retain user data. No destructive database migration is involved.

## Windows distribution and trust

NSIS produces a per-user x64 `.exe` installer and Start menu entry. PyInstaller
bundles the Python sidecar and its media/voice dependencies; FFmpeg binaries and
licenses are included as build resources. A standalone Node binary is bundled
for yt-dlp JavaScript challenges; Electron's RunAsNode fuse stays disabled.
Optional OCR and large models are separate,
user-triggered installations. Models use their service's official APIs and
storage format. No model weights are silently included in the installer.

Update installation is disabled until a release feed and expected Windows code
signing publisher are configured. Production signing credentials belong in CI
secrets, never the repository. The update client must verify package integrity
and publisher signatures; unsigned development builds must not present updates
as production-ready. Native installer/tray/DPAPI validation requires Windows.

## Delivery checklist

1. Preserve the web editor, controls, visual selection and 40-second export limit.
2. Installed desktop lifecycle, sidecar authentication and safe shutdown.
3. First-run, repeatable five-step AI wizard and central settings.
4. Synchronized topbar/settings provider and model selection.
5. Cloud adapters: OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter, custom.
6. Local adapters: Ollama, LM Studio, llama.cpp, custom local endpoint.
7. DPAPI secrets, endpoint validation, capability errors, cancellation.
8. Local model downloads/progress/cancellation/deletion and hardware inspection.
9. Persistent projects/history, safe import/export and existing-data migration.
10. Tray, optional login startup, close behavior, offline status and signed updates.
11. Reproducible Windows build, icons, CI and production signing instructions.
12. Automated regressions and explicit record of unverified live/native scenarios.
