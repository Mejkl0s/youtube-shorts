# Short Story Studio

An English-first studio for short 3D stories with an English male narrator, action-aware pauses and video references. Play the bundled example immediately in the web app. See [DEPLOY.md](DEPLOY.md) for hosting. Earlier ranking tools are retained at `/?workspace=ranking`.

A personal AI director, editor and MP4 renderer for ranking Shorts: exactly five clips, #5 → #1, portrait 9:16, sound effects and a short English neural voiceover per clip (1–7 words).

## Run

Requires Node 20.19+ (Node 24 tested), Python 3.12, Blender, FFmpeg with libx264/drawtext, ffprobe and DejaVu Sans Bold. Python and Node dependencies are locked in `requirements.txt` and `package-lock.json`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
npm run build
# Optional local alternative: .venv/bin/python scripts/download_models.py --language en
cp .env.example .env # local machines only; fill keys securely
bash scripts/start.sh
```

For Codex cloud use secure environment settings, rather than storing keys in a file. If no `.env` file is used, start directly:

```bash
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Development: run the API on port 8000 and `npm run dev` in another terminal. Vite proxies `/api` and `/media` to the backend. Production serves the built frontend and API from the same process.

## Automatic workflow

**Free is the default discovery mode.** Enter a topic and click **Najít klipy** without any provider key. Public Bing RSS / DuckDuckGo HTML results are searched for individual TikTok videos and Instagram Reels, with optional YouTube Shorts supplementation. URLs must be real returned links on supported domains; profiles, unrelated text matches and duplicate canonical video URLs are rejected. Only public search is used; login, challenges and rate limits are not bypassed.

yt-dlp attempts actual downloads. Deterministic rules select exactly five 2–4-second continuous scenes using topical title/snippet matches, sampled grayscale motion, edges and exposure. TikTok/Instagram remain primary; YouTube fills missing positions. This is **not AI understanding or a judgement of the best moments**. Review relevance, order and trims yourself. No generated commentary is fabricated, and free discovery switches narration off in the editor. Add your own short comments if desired. Effects, ranking overlays and MP4 export work without paid APIs. The free flow never calls OpenAI, even if an API key is configured.

Search/downloads can be blocked or return too few usable videos. The job fails clearly when five real usable clips are unavailable, and retains discovered source links for inspection. It never substitutes a synthetic demo or announces a successful five-clip selection when the real operation failed. The health `free_search` flag denotes implementation availability, not verified access to the external engines. Cloud networking must allow `www.bing.com` and `html.duckduckgo.com` in addition to the social video/CDN hosts.

The optional **AI výběr · placené API** mode and **Osobní AI režisér** use the paid OpenAI workflow below. Premium male speech is independently optional and requires its provider's key. There is no bypass of provider billing.

1. Enter a topic. The primary sources are **TikTok and Instagram**; optionally include relevant YouTube videos. No stock-video library is used.
2. With `OPENAI_API_KEY`, web search discovers 8, 12 or 20 candidate URLs. The server validates provider domains and individual video URLs, and yt-dlp attempts to download publicly available videos, at most 120 seconds / 300 MB each.
3. FFmpeg detects hard scene changes. AI evaluates two sampled frames per candidate scene, selects five different source videos, ranks them, explains why they fit, and writes a grounded sentence of 1–7 words per clip. Selected segments are 2–5 seconds by default and do not cross detected scene cuts.
4. Edit the selected moments, order and voiceover. Manual trims allow 2–8 seconds, for a final 10–40-second Short. Background sound, effects and voice levels are adjustable.
5. Render an actual MP4 (1080×1920 or 720×1280, H.264/AAC, 30 fps). It includes ranking numbers, the heading, optional captions and per-clip sound effects. Speech is fitted without truncating the final words or speeding it up beyond 1.25×. In assistant mode, an overly long sentence is automatically shortened once, and the updated captions/comments are returned to the editor. If it still does not fit, the renderer reports the problem.

Uploads and a clearly labelled synthetic test-pattern demo also work without external APIs. Save project stores the editor state in this browser; original media and exports remain in `.runtime/` on the server. Browser previews show the clip montage and text; generated voice and effects are heard in the rendered output or the individual voice-preview button.

## AI and network configuration

`OPENAI_API_KEY` is required only for optional AI discovery, visual scene selection, automatic scripts and research. It stays on the server. Calls go only to `api.openai.com`. Discovery/research use the Responses API `gpt-4.1` with web search; image analysis uses `OPENAI_TEXT_MODEL` (default `gpt-4o-mini`). Public video pages and CDN domains for TikTok, Instagram and YouTube must be allowed in the cloud network settings.

The default quality English male voice is **OpenAI Onyx** with `gpt-4o-mini-tts`; **Echo** is a second male option. The same `OPENAI_API_KEY` powers the assistant, search/analysis and speech. Delivery instructions and speed (0.85–1.2×) are adjustable, with a preview button before export. Live audio quality was not evaluated because no provider key was present.

**Piper / en_US-lessac-medium** is an explicitly selected local alternative. `scripts/download_models.py` downloads the official model from Hugging Face using TLS and validates the publisher's lengths and checksums; the model card is retained beside the model. A Czech model is optional (`--language cs`). No voice model is bundled into Git. Piper and each model have their own upstream licenses.

Alternatively set `ELEVENLABS_API_KEY` and explicitly select **Adam**, **Josh** or **Antoni** in the male voice selector. To use a particular voice ID, select **Vlastní / ElevenLabs** and set `ELEVENLABS_VOICE_ID`. Providers never silently fall back to a different voice. A named voice is not proof it matches the reference video. Do not put keys in chat or client-side code. The OpenAI and ElevenLabs operations may incur provider charges.

TikTok/Instagram/YouTube can refuse downloads, require login or present a bot challenge. The application reports and skips unavailable candidates; it does not promise access or bypass login requirements. Only reuse videos you have permission to publish; the editor retains each original source link. Web search cannot find every video or guarantee the requested candidate count. If fewer than five relevant, downloadable videos remain, the workflow fails rather than fabricating clips.

## Research and reference style

The research action queries public YouTube search evidence for **Aura Shorts and other ranking channels**, and returns linked observations, suggestions and limits. It does not claim to have watched or heard videos it cannot access. It does not fabricate channel statistics or identify a narrator from metadata.

The current video design uses a bold uppercase title, lime ranking numbers and white short captions. **The exact design and voice from `IujvEGCadfU` have not been verified:** YouTube was blocked during implementation. An accessible reference video is needed to match them accurately. The editor preview uses the same font and colors, but export is the definitive placement reference.

Scene detection is heuristic: it detects hard cuts, not every transition or semantic action boundary. AI selection is based on sampled images rather than full video/audio understanding. Final editor review is still useful, especially for compilations with subtle cuts.

## Validation

```bash
npm run build
.venv/bin/python -m pytest -q
# Start server on 8000 before the browser checks:
npm run test:browser
```

The backend checks exercise actual FFmpeg rendering and scene detection, validation, provider URL restrictions and missing-integration responses. Browser checks exercise the chat’s missing-key handling, male voice selection, editor, demo, ordering, word limit, saved project and real export. Live AI/search/voice calls require the credentials, model and network destinations above; mocked provider responses do not establish that those integrations work live.

This is a single-user application with optional owner password protection and no automatic publishing. Uploaded media/exports are retained until `.runtime/` is removed. It is not designed as a public multi-user service.

## Deploy the web app on Render

The repository includes a multi-stage Dockerfile and `render.yaml` Blueprint for one **free** web service. Deploy this repository through Render's Blueprint flow, connecting your GitHub account if needed. Enter these values securely in Render, never in chat or Git:

- `STUDIO_PASSWORD`: a strong password you choose for your personal studio. The username is `owner` (`STUDIO_USERNAME`). The browser requests this login before opening the editor.
- Optional `OPENAI_API_KEY`: add your own OpenAI API key for AI discovery, the AI director and premium male speech only if desired. Provider usage is billed by OpenAI independently of Render. Free public discovery, demo clips, manual uploads and exports with narration disabled work without this key. The free Blueprint does not require it.

Render sets `PORT` automatically; the container serves the frontend, API and media together. `STUDIO_PUBLIC=1` makes a missing studio password block the app rather than expose your videos or let strangers use your AI key. `/api/health` remains accessible for Render's health check. Optional ElevenLabs credentials can be added in Render's environment settings.

The free service has limited memory/CPU, sleeps when idle, and uses ephemeral storage. Restarts/deploys lose uploaded clips and rendered files; save/download your work before leaving. Browser-saved projects cannot recover source files lost on the server. Rendering 720p is the lighter starting option. No paid plan or persistent disk is provisioned automatically. After Render reports a successful deploy, use the **actual service URL** shown in its dashboard; a Blueprint deploy link is not the running app.

For API-driven deployment, configure `RENDER_API_KEY` securely in the Codex environment. This key is only for deployment and does not belong in the application's container or frontend. Secrets configured in Codex are not automatically copied into Render; configure the application password/provider key there separately.

## Original commentary

The editor includes an explicit editorial angle (ranking criteria). AI comments explain the visible reason for each ranked position instead of copying dialogue or supplying generic filler. The output adds its own heading, editorial labels, ranking, short analytical captions, neural narration and original synthesized effects. These features support an original commentary format; effects, voiceover and rearrangement alone do **not** establish fair use, legal transformativeness, monetization eligibility or permission to reuse someone else’s videos.

## Personal AI director and custom templates

Use the chat instead of filling out every control. For example:

- “Udělej top 5 fotbalových momentů z TikToku a Instagramu. Použij hlubší mužský hlas.”
- “Použij tuto šablonu, nech červená čísla a bílé titulky.”
- “Otoč pořadí, zkrať každý klip na tři sekundy a exportuj.”
- “Zkoumej Aura Shorts a další ranking kanály.”

The assistant interprets a natural command plus the current project and the last twelve messages, then runs a validated sequence of actual tools. Available actions are template analysis, discovery, comment writing, YouTube research and MP4 rendering; edits/order/settings are validated too. It cannot execute arbitrary shell commands or publish. Missing topics/references prompt a clarification. A plan is never shown as successful until the underlying work finishes; partial work is retained if a later step fails. The chat retains up to thirty messages in this browser. A browser refresh does not reattach an in-progress assistant job; its last result is marked unverified.

The visible **Vzhled podle předlohy** section accepts PNG/JPEG/WebP or a short video, up to 40 MB / 120 seconds, by file picker or drag and drop. An actual frame is extracted locally; for video you can select its timestamp. Uploading automatically applies the selected analysis mode. The default **Základní odhad · zdarma** uses local Tesseract OCR to estimate title/rank/caption positions, sizes, colors and title/caption alignment. It makes no paid API calls, even when an OpenAI key is configured. When text cannot be recognized, the current layout is retained and the limitation is shown. Tesseract with English language data is included in the Docker image; local installs can use `apt-get install tesseract-ocr tesseract-ocr-eng` or equivalent.

Expand **Doladit čísla, nadpis a titulky** to adjust colors, font, sizes, positions, alignment, margins, header darkness and editorial labels in the live preview. **Uložit vzhled předlohy** saves that layout with visual preferences for the assistant; the current layout also drives actual FFmpeg export. Instructions typed alongside the reference are forwarded with the next assistant command. Free OCR works from the image; interpreting written preferences requires the optional AI mode and a configured API key. AI analysis additionally estimates the closest of three supported fonts and header darkness. Exact font, animation and narrator matching is not promised from a still frame. **Uložit projekt** retains the reference settings, preferences and selected male voice in this browser; uploaded media remain subject to the host's storage lifetime.

This is a personal application using configured AI providers, rather than a newly trained model. Your prompts, sampled clip images, reference frame and voiceover text are sent to the chosen providers only for the requested AI operations. There is no model training pipeline or automatic publication.

## English story studio and reference links

The main studio now starts in English, with English male narration, coherent prepared English scripts, English captions and a new English example. Earlier Czech browser projects are left untouched under their previous storage key; the English studio uses a separate versioned key. The older ranking tools remain available at `/?workspace=ranking` for compatibility and are not shown in the new studio navigation. More elaborate story writing is intentionally left for a later change.

Speech, captions and animation share `backend/storyboard.py`. The parcel pickup and handoff cues start their corresponding narration at the actual action, while complete thoughts have short pauses and scene transitions retain breathing room. The audio timeline is mixed into an exact-duration WAV. A line may be fitted up to 1.1× speed, but it is rejected rather than clipped if it cannot fit its action window. Dense commentary that leaves less than 16% breathing room is rejected. Pause placement follows these prepared story cues, not arbitrary video understanding.

The basic English male voice uses eSpeak NG `en-us+m3`. Optional English male Piper/Ryan is enabled after a verified `scripts/download_models.py --language en-male` installation. The pinned Ryan sizes/checksums come from the publisher's official `voices.json`; verification remains mandatory. Docker can opt into this model with build argument `INSTALL_STORY_NEURAL_VOICE=1`; model download is otherwise skipped so basic voice builds work offline after package installation. OpenAI Onyx is an explicitly selected optional natural voice using an existing server-side key. It can incur provider charges. Neither premium provider nor neural model is silently substituted for another voice.

**Reference video:** paste an individual public YouTube, TikTok or Instagram URL, choose basic visual analysis or optional AI analysis, and import it. The backend downloads a bounded video (120 seconds / 60 MB), extracts three actual frames, persists the reference and applies supported clothing colors, sky color, lighting and camera distance to the next preview/export. Basic analysis only estimates dominant colors/brightness and leaves framing at medium; it does not claim semantic understanding. Optional AI analysis sends those sampled images to the configured OpenAI vision model and uses a bounded style schema. It needs a working key and network and may incur usage charges. The renderer does not clone exact characters, environments, motion or voice from the reference. Direct file URLs, private network URLs, profile links and login-restricted videos are not accepted; public provider download restrictions are reported rather than bypassed. Removing the reference restores the default visual settings for the next render.

Actual local speech and timing, synthetic-video frame analysis and style persistence are covered by tests. Tests of AI responses mock the provider and do not establish live AI availability. Live model/reference downloads may be blocked by the cloud network; that is distinct from the local analysis/rendering checks. `npm run test:story` checks the English creation flow; `npm run test:web` checks the password-protected production app and English bundled example. `npm run test:browser` preserves the earlier ranking workflow through its compatibility URL.

`npm run test:reference` prepares a real local video fixture, samples its frames, then checks reference application in the browser and a real Blender preview. Only external downloading is replaced by the fixture; the analysis/render/media pipeline runs normally. The backend rejects unsupported/private-network links and never reports analysis success after a failed download.


Story duration defaults to automatic: actual synthesized narration determines the film length, leaving pauses at the shared action cues. It is no longer tied to 35/40/45 seconds. An optional 10–120 second override remains for the CPU renderer. The video-topic field accepts a short brief (about 2–3 sentences); “Create English script from topic” uses OPENAI_API_KEY to produce five editable English scene lines, adapted to the currently supported park choreography. No AI script or expanded choreography is claimed when the key is missing. Review the script before rendering. Automatic length uses measured speech for voiced exports and a reading-time estimate for silent exports/previews.
