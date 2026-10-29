# Rank Studio

A personal AI director, editor and MP4 renderer for ranking Shorts: exactly five clips, #5 → #1, portrait 9:16, sound effects and a short English neural voiceover per clip (1–7 words).

## Complete scenes, original audio and sound preview

Free selection preserves each detected continuous scene in full when it is 2–30 seconds long, instead of taking four seconds from its middle. For a longer shot, a local motion profile chooses a 30-second window with setup and aftermath around a peak. This is a conservative heuristic, not perfect semantic recognition of a punchline. Hard cuts are approximate boundaries. Paid selection samples four chronological frames per bounded candidate scene; it also cannot guarantee complete understanding.

New previews preserve the original source aspect ratio. New clips default to **Celý obraz** (`framing: fit`): portrait export pads with black rather than cutting off action at a landscape video's edges. **Vyplnit 9:16** (`fill`) remains available deliberately in **Upravit střih**. The source cleanup detector, manual mask editor and renderer use the same framing. Existing masks are transformed when the frame mode changes.

**Upravit střih** opens retained original footage with start/end controls, playback of the selection and a full-image choice. A new asset is created when applying a 2–30-second cut; the original is retained. Source and scene boundaries are persisted in metadata. **Celý původní zdroj** also allows deliberate selection beyond a detected hard-cut boundary. Older cuts may use provenance retained in the browser project. If original media is gone, it cannot be reconstructed from a four-second file. **Znovu vybrat celé scény** rebuilds all five current cuts from their retained original shots, retaining custom notes and narration and transforming masks. Failure keeps the current editor project intact; duplicate physical shots are rejected.

Original audio defaults to 80% instead of 12–15%; those exact legacy defaults are migrated in saved browser projects. User mute/other custom levels persist. The visible **Původní zvuk** slider supports 0–150% in the rendered mix; the direct source player is capped at its native 100%. Clips with no actual audio track show **Zdroj bez zvuku**. Editing cannot restore an absent source track.

The source montage player only plays original audio. **Připravit voiceover zdarma** writes brief rank announcements and enables the keyless voice/SFX settings; it does not pretend to analyze the scene. **Vytvořit náhled se zvukem** generates the same actual MP4 as export with selected original audio, enabled voiceover and enabled effects. Its player appears immediately under the montage; downloading is separate. Live voice service availability still must be checked on the user's connection.

## Clean ranking notes

The video contains the main heading, numbers and short notes beside the numbers. Source titles in lime, criteria at the bottom and the preview's studio footer/watermark/dots are removed, including when restoring older projects with `show_label`/`show_criteria` enabled. The active medal number has no automatic gray background; the optional explicit badge preset remains available. Source text already burned into a downloaded video is handled by the source blur editor.

Each clip has an editable **Poznámka u čísla** (`rank_note`, at most four words / 40 characters). New selections receive varied short English/Czech reactions from a local bank. There are no duplicates within the five, and the next set avoids the previous set even when intervening source downloads generate their own labels. **Obměnit poznámky** explicitly requests another set. These are editable reactions, not AI descriptions of the footage. Existing saved notes stay unchanged on reload, reorder and export. Notes follow their clips during reorder and persist with the project. An explicit empty note stays empty. **Poznámky u čísel** controls their visibility (`captions` in the API). Column view shows the note beside each position; single view shows the current clip's note. Voiceover text is independent and no longer printed at the bottom. Preview and actual MP4 use the same note text and bundled template font. Legacy caption placement and source-label fields remain accepted for old API projects but do not add overlays.

## Windows desktop launch

Download and extract the [repository ZIP](https://github.com/Mejkl0s/youtube-shorts/archive/refs/heads/main.zip), then double-click **SPUSTIT-WINDOWS.bat**. It uses winget to install missing Python 3.12 x64, Node.js LTS (24+), FFmpeg and optional Tesseract, installs the locked app dependencies and opens the same web editor on the user's PC. No Render account or paid API key is required for the free workflow. **OVERIT-WINDOWS.bat** performs a real offline MP4/codec/font/path check. See [the Czech Windows guide](WINDOWS.md) for setup, local session imports, persistence and troubleshooting. The launcher binds to loopback only and refuses an occupied port instead of opening an unrelated app.

Running locally is an alternative network location to test; it is not proof that TikTok, Instagram, YouTube, search engines or online speech will allow requests. Native Windows installation and live source access must be verified on that PC. Common launcher, editor and export behavior can be tested in Linux without claiming Windows execution.

## Video title

Typing the full heading into **Co dnes rankujeme?** updates the video title immediately, with the same capitalization and without adding “TOP 5”. Topic and title both support up to 100 characters. Under **NÁZEV VE VIDEU**, choose the title's font, size and color; these settings apply to the preview and actual MP4. The title font is independent of numbers/captions, with an option to inherit the template font. Text case is preserved in exported title files.

Click a word under the title controls to highlight that exact word in yellow, then choose any color with **Barva vybraného slova**. Other words keep the base title color. Matching repeated words share a color; changing the title never shifts an index-based highlight onto a different word. **Vzhled písma** offers outline, shadow, plain and dark-background treatments independently of the font family. These choices and word colors persist with the project and are rendered as a safe RGBA title layer using pinned Pillow and the bundled fonts, then composited into the actual MP4.

**Písmo nadpisu** opens a searchable, Word-like picker with 12 named families and live samples: DejaVu Sans Bold, DejaVu Sans Condensed Bold, DejaVu Serif Bold, Liberation Sans, Liberation Serif, Carlito, Anton, Bebas Neue, Poppins Bold, Lato Bold, Archivo Black and Barlow Condensed Bold. Searching “Arial”, “Times New Roman” or “Calibri” finds clearly labeled lookalikes (Liberation Sans, Liberation Serif and Carlito), not renamed Microsoft font files. The same picker is available for the overall template font.

All faces and licenses are bundled for offline rendering on Windows and Render. A shared `backend/fonts/catalog.json` drives font validation and UI metadata; the browser fetches each exact file from `/api/fonts/{id}` and export reads the same file. New Google Fonts downloads are pinned by commit and recorded with SHA-256 checksums in `backend/fonts/sources.json`. See the font directory for licenses. The frontend build includes the shared catalog; the local launcher also tracks it when deciding whether to rebuild.

Editing the title directly makes it a custom heading, so later search-topic changes do not overwrite it. Re-enable **Přebírat nadpis z „Co dnes rankujeme?“** to copy the current topic and resume automatic updates. Saving a project retains that choice and the title styling.

## Finish the ranking

The default video overlay keeps all five positions visible in a vertical column: **1 at the top through 5 at the bottom**, with fixed medal colors: gold for 1, silver for 2, light bronze for 3 and white for 4–5. The medal colors remain fixed during playback, with no automatic active-rank background. **Barvy pořadí** also offers the previous custom active-rank color. **Žebříček 1–5** applies the column preset without OCR or a paid API. The clip playback still counts down from #5 to #1. The layout setting `rank_display` can explicitly select `column` or the previous `single` counter; both browser preview and MP4 rendering use the selected mode. Column font size and spacing shrink automatically to keep all five rows on screen.

After finding five clips, choose **Výrazný ranking** (large yellow number with a black outline) or **Číslo v rámečku**. These presets hide source filenames and ranking criteria from the video. Font, positions, colors and number treatment remain editable and apply to the live layout and real FFmpeg export; imported reference settings are preserved until a preset is explicitly chosen.

**Uvedení pořadí zdarma** prepares two-word English/Czech position announcements, selects the keyless male voice and enables speech, effects and captions. These are position announcements, not invented descriptions of the scene. They follow reordering and language changes; manually edited text is preserved. Write a specific 2–4-word comment yourself, or use the optional paid **AI komentáře · 2–4 slova**, which checks the requested limit against real scene frames. The existing seven-word maximum remains available for manual comments.

**Exportovat Short** mixes the selected voice, whooshes (#5–#2) and winner chord (#1). The source player previews editing with original audio; after export, **Hotové video se zvukem** plays the actual MP4 inline, including the rendered layout and enabled audio tracks. AAC padding is removed per segment before the final audio join so sound stays aligned at the cuts. Free online speech still depends on service availability and never falls back to a paid provider.

## Run

Requires Node 24+, Python 3.12, FFmpeg with libx264/drawtext and ffprobe. The font catalog, bundled typefaces and their redistribution licenses are included in `backend/fonts`; the editor and exported video use those same fonts on Linux and Windows. Python and Node dependencies are locked in `requirements.txt` and `package-lock.json`; uvloop is skipped on Windows. FFmpeg filter paths handle drive letters, spaces, apostrophes and filter delimiters, and title/caption files are written as UTF-8.

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

yt-dlp attempts actual downloads. Search titles/snippets must match every essential topic concept, with ordinary English plurals and a small explicit winter/fail vocabulary: “winter fails” accepts “snow wipeouts” but rejects Vivaldi’s “Winter” and unrelated fails. Generic style words such as “funny” cannot replace a subject. This text filter can still misread misleading descriptions or miss synonyms. Deterministic rules select exactly five 2–30-second continuous scenes using those topical matches, sampled grayscale motion, edges and exposure. TikTok/Instagram remain primary; YouTube fills missing positions. This is **not AI understanding or a judgement of the best moments**. Review relevance, order and trims yourself. No generated commentary is fabricated, and free discovery switches narration off in the editor. Add your own short comments if desired. Effects, ranking overlays and MP4 export work without paid APIs. The free flow never calls OpenAI, even if an API key is configured.

Search/downloads can be blocked or return too few usable videos. The job fails clearly when five real usable clips are unavailable, and retains discovered source links for inspection. It never substitutes a synthetic demo or announces a successful five-clip selection when the real operation failed. The health `free_search` flag denotes implementation availability, not verified access to the external engines. Cloud networking must allow `www.bing.com` and `html.duckduckgo.com` in addition to the social video/CDN hosts.

With **+ YouTube** enabled, fewer than five usable downloaded scenes trigger a separate YouTube round, even when TikTok/Instagram filled the initial candidate budget. The round uses public yt-dlp search plus a YouTube-only web-search supplement, with up to another selected candidate count. Canonical IDs deduplicate Shorts/watch links across rounds. TikTok and Instagram remain preferred; YouTube fills missing positions. Two consecutive server-wide refusals/timeouts pause further attempts for that source. A private YouTube video alone does not pause the entire YouTube source. The results panel shows found/downloaded totals and bounded failure categories for every source. Disabling YouTube prevents the extra round.

### Optional TikTok/Instagram sessions

Expand **Přihlášení ke zdrojům · volitelné** to import your own exported **Netscape cookies.txt** for TikTok or Instagram. This is session import, not an OAuth integration: opening the social site's login in another tab does not transfer its browser session to Render. The studio never asks for social-network passwords. Cookie files authorize account access and should only be uploaded to your password-protected studio, never sent in chat or committed to Git. No browser export extension is bundled or required by this code.

Imports are bounded to 256 KB, reject malformed/expired data, filter cookies to the chosen platform, and preserve an existing valid import when a new one is invalid. They are stored under `.runtime/private/source-sessions` with directory mode 0700/file mode 0600, outside served media. APIs expose status/count only. Downloads get a private disposable copy for the matching platform, deleted after success or failure; TikTok/Instagram cookies are never attached to YouTube. **Odpojit** removes the saved file. Imported sessions are not included in browser-saved projects. Free Render restarts/redeploys can erase them. “Relace nahraná” means saved, not confirmed login: actual downloading must verify it, and platforms can still reject an expired session or a cloud IP. Login challenges/rate limits are reported rather than bypassed.

The Docker runtime includes Node 24 and pinned `yt-dlp-ejs` matching yt-dlp's declared default dependency, so ordinary supported YouTube extraction has its JavaScript runtime. Runtime fetching of external JS components is disabled. Local installs use the existing Node prerequisite plus the locked Python dependency. The requirements include yt-dlp's `default` and `curl-cffi` extras with pinned transitive packages: the base package alone omitted its supported browser transport, Brotli, requests, metadata and crypto dependencies. TikTok's extractor requests that transport; installing it supplies a supported capability rather than establishing that an inaccessible page can now be downloaded. The offline Windows doctor verifies that yt-dlp actually lists `curl_cffi` targets, not just that the package name can be imported. TLS verification and configured proxies remain enabled. These dependencies do not remove login requirements, IP restrictions or search-engine outages.

The optional **AI výběr · placené API** mode and **Osobní AI režisér** use the paid OpenAI workflow below. Premium male speech is independently optional and requires its provider's key. There is no bypass of provider billing.

1. Enter a topic. The primary sources are **TikTok and Instagram**; optionally include relevant YouTube videos. No stock-video library is used.
2. With `OPENAI_API_KEY`, web search discovers 8, 12 or 20 candidate URLs. The server validates provider domains and individual video URLs, and yt-dlp attempts to download publicly available videos, at most 600 seconds (10 minutes) / 300 MB each.
3. FFmpeg detects hard scene changes. AI evaluates four chronological sampled frames per candidate scene, selects five distinct shots (preferably from different sources), ranks them, explains why they fit, and writes a grounded sentence of 1–7 words per clip. Selected segments are 2–30 seconds, preserving whole short scenes and do not cross detected scene cuts.
4. Edit the selected moments, order and voiceover. Manual trims allow 2–30 seconds, for a final 10–150-second Short. Background sound, effects and voice levels are adjustable.
5. Render an actual MP4 (1080×1920 or 720×1280, H.264/AAC, 30 fps). It includes ranking numbers, the heading, optional notes beside the numbers and per-clip sound effects. Speech is fitted without truncating the final words or speeding it up beyond 1.25×. In assistant mode, an overly long sentence is automatically shortened once, and the updated speech comments are returned to the editor. If it still does not fit, the renderer reports the problem.

Uploads and a clearly labelled synthetic test-pattern demo also work without external APIs. Save project stores the editor state in this browser; original media and exports remain in `.runtime/` on the server. Browser previews show the clip montage and text; generated voice and effects are heard in the rendered output or the individual voice-preview button.

## AI and network configuration

`OPENAI_API_KEY` is required only for optional AI discovery, visual scene selection, automatic scripts and research. It stays on the server. Calls go only to `api.openai.com`. Discovery/research use the Responses API `gpt-4.1` with web search; image analysis uses `OPENAI_TEXT_MODEL` (default `gpt-4o-mini`). Public video pages and CDN domains for TikTok, Instagram and YouTube must be allowed in the cloud network settings.

New browser projects select **Andrew / Antonín · zdarma bez klíče**: keyless online Microsoft Edge read-aloud through the pinned `edge-tts` client. English uses `en-US-AndrewMultilingualNeural`; Czech uses `cs-CZ-AntoninNeural`. Both are male voices. No service registration or user API key is needed. This is an unofficial service integration, not a guaranteed free public API or offline engine; Microsoft may change or refuse it. Only the requested speech text is sent to Microsoft. The host must reach `speech.platform.bing.com` over HTTPS/WebSocket. Proxy settings are respected; TLS verification stays enabled. A failed request produces a clear error, cleans partial audio and never invokes a paid provider.

The free option is available for both the voice preview and real MP4 export, with adjustable speed (0.85–1.2×, new-project default 0.95×). It uses its voice's normal delivery and does not interpret style prompts. Enter original comments of 1–7 words yourself when using free clip discovery; free speech does not add free AI script generation. Preview buttons play the actual selected voice, with a Czech sample when Czech is selected. Existing saved provider choices are retained; **Použít hlas zdarma** switches a saved unavailable paid provider explicitly. The `free_voice` health flag means the client is installed, not that a live service request succeeded. Tests simulate the remote speech bytes but exercise real audio decoding and MP4 mixing. The live service was blocked by this cloud instance's egress proxy, so its audio quality and availability on Render remain unverified. It is not an exact narrator match to the reference.

Optional **OpenAI Onyx / Echo** use `gpt-4o-mini-tts`. The same `OPENAI_API_KEY` powers the paid assistant, search/analysis and speech. OpenAI delivery instructions and speed are adjustable. Older API calls omitting explicit `voice_settings` retain their Onyx default for compatibility; the browser always sends its selected provider. Live premium audio quality was not evaluated because no provider key was present.

**Piper / en_US-lessac-medium** is an explicitly selected local alternative. `scripts/download_models.py` downloads the official model from Hugging Face using TLS and validates the publisher's lengths and checksums; the model card is retained beside the model. A Czech model is optional (`--language cs`). No voice model is bundled into Git. Piper and each model have their own upstream licenses.

Alternatively set `ELEVENLABS_API_KEY` and explicitly select **Adam**, **Josh** or **Antoni** in the male voice selector. To use a particular voice ID, select **Vlastní / ElevenLabs** and set `ELEVENLABS_VOICE_ID`. Providers never silently fall back to a different voice. A named voice is not proof it matches the reference video. Do not put keys in chat or client-side code. The OpenAI and ElevenLabs operations may incur provider charges.

TikTok/Instagram/YouTube can refuse downloads, require login or present a bot challenge. The application reports and skips unavailable candidates; it does not promise access or bypass login requirements. Only reuse videos you have permission to publish; the editor retains each original source link. Web search cannot find every video or guarantee the requested candidate count. If fewer than five relevant, downloadable videos remain, the job stays failed, but technically usable downloaded scenes are returned as `partial_clips` and placed in the editor with empty remaining slots. Upload the missing clips there; the app never repeats a continuous shot to fill the ranking and export still requires exactly five clips. Partial recovery uses technical scene selection, without AI assessment or narration, including for interrupted AI discovery. This also preserves partial results in the assistant's project and stops subsequent scripts/render actions. A downloaded video with no usable continuous scene is not counted as a recovered clip. Deployment/restarts on free Render can still erase these files.

Public search inspects each enabled platform before applying the candidate limit. TikTok and Instagram results are interleaved so a full TikTok pool cannot hide all Instagram candidates; YouTube fills remaining positions and retains its independent fallback round. TikTok queries request video pages, and DuckDuckGo relevance uses both titles and actual result snippets, including generic Instagram titles. A source with no matching URLs is reported separately from download failure: uploading login cookies cannot supply missing search results. Diagnostics distinguish explicit IP denial, missing page metadata, TLS trust failures, missing formats and a downloaded file failing media preparation, without exposing raw provider messages or credentials. These changes do not remove cloud-IP blocks or search-engine outages; successful unit tests do not establish live social downloading.

## Research and reference style

The research action queries public YouTube search evidence for **Aura Shorts and other ranking channels**, and returns linked observations, suggestions and limits. It does not claim to have watched or heard videos it cannot access. It does not fabricate channel statistics or identify a narrator from metadata.

The current video design supports mixed-case, word-colored titles, a vertical medal-colored ranking and short captions. **The exact design and voice from `IujvEGCadfU` have not been verified:** YouTube was blocked during implementation. An accessible reference video is needed to match them accurately. The editor preview uses the same font and colors, but export is the definitive placement reference.

**Compilations and source cleanup:** Search strips title boilerplate (for example, `ranking funniest winter fails` searches for `funny winter fails`) without modifying the displayed video title. YouTube web queries include ordinary watch videos as well as Shorts. Sources up to 10 minutes / 300 MB are accepted. The selector prefers one physical shot per source, then uses different shots from a compilation if slots remain. One continuous shot counts only once, including when its motion profile is analyzed. Selected compilation shots are actually cut into separate short source files with their own media IDs and previews; a repeated playback of the whole compilation cannot slip into export. Original source links are retained. **Nahrát a rozstříhat kompilaci** runs the same technical selection on a local upload, without a search provider or paid API. Fewer than five detected usable shots remain an incomplete job with recovered clips, never a fabricated five-clip success.

**Automaticky rozmazat nalezený text** runs local Tesseract on three portrait samples of each selected scene and applies up to eight bounded source masks per clip. This option is enabled for new searches and uploaded compilations. **Rozmazání** on each clip opens an editor: draw a rectangle, click it to remove, inspect other timestamps, or rerun text detection. Masks are fixed over the selected clip's duration; OCR may miss moving text, logos or other obstructions, so inspect and edit them. Blur hides the selected source pixels; it does not reconstruct what was behind a caption. Masks are saved with the project, previewed underneath the studio's overlays and applied in FFmpeg before the studio's own title, rank numbers and captions. OCR availability depends on local Tesseract; manual masks and export work without it. No remote API is used. This editing workflow does not remove search/download refusals by source sites.

Scene detection is heuristic: it detects hard cuts, not every transition or semantic action boundary. AI selection is based on sampled images rather than full video/audio understanding. Final editor review is still useful, especially for compilations with subtle cuts.

## Validation

```bash
npm run build
.venv/bin/python -m pytest -q
# Start server on 8000 before the browser checks:
npm run test:browser
node scripts/compilation-browser-test.mjs
node scripts/context-browser-test.mjs
# Self-contained real browser login/logout check (starts its own isolated server):
node scripts/browser-login-test.mjs
```

The backend checks exercise actual FFmpeg rendering and scene detection, validation, provider URL restrictions and missing-integration responses. Browser checks exercise the chat’s missing-key handling, male voice selection, editor, demo, ordering, word limit, saved project and real export. Live AI/search/voice calls require the credentials, model and network destinations above; mocked provider responses do not establish that those integrations work live.

This is a single-user application with optional owner password protection and no automatic publishing. Uploaded media/exports are retained until `.runtime/` is removed. It is not designed as a public multi-user service.

## Deploy the web app on Render

The repository includes a multi-stage Dockerfile and `render.yaml` Blueprint for one **free** web service. Deploy this repository through Render's Blueprint flow, connecting your GitHub account if needed. Enter these values securely in Render, never in chat or Git:

- `STUDIO_PASSWORD`: a strong password you choose for your personal studio. The username is `owner` (`STUDIO_USERNAME`). The app shows its own HTML login form so embedded browsers need no native Basic Auth popup. Login is also available at `/login`. Successful login sets a signed, HttpOnly, SameSite=Lax cookie that expires after 12 hours and is Secure on public hosting. Changing the password or username invalidates existing sessions. Use **Odhlásit se** in the editor to clear the cookie. Passwords are never stored in cookies or browser local storage. Explicit Basic Auth remains supported for API clients. Cross-origin browser requests that change state are rejected.
- Optional `OPENAI_API_KEY`: add your own OpenAI API key for AI discovery, the AI director and premium male speech only if desired. Provider usage is billed by OpenAI independently of Render. Free public discovery, demo clips, manual uploads, keyless online speech and exports with narration disabled work without this key. The free Blueprint does not require it.

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

Expand **Doladit čísla, nadpis a titulky** to adjust colors, font, sizes, positions, title alignment, margins and header darkness in the live preview. **Uložit vzhled předlohy** saves that layout with visual preferences for the assistant; the current layout also drives actual FFmpeg export. Instructions typed alongside the reference are forwarded with the next assistant command. Free OCR works from the image; interpreting written preferences requires the optional AI mode and a configured API key. AI analysis additionally estimates the closest available bundled font and header darkness. Exact font, animation and narrator matching is not promised from a still frame. **Uložit projekt** retains the reference settings, preferences and selected male voice in this browser; uploaded media remain subject to the host's storage lifetime.

This is a personal application using configured AI providers, rather than a newly trained model. Your prompts, sampled clip images, reference frame and voiceover text are sent to the chosen providers only for the requested AI operations. There is no model training pipeline or automatic publication.

### Repeated discovery and automatic mixed preview

Discovery supports 8–40 candidates (24 by default) and bounded `exclude_urls` (up to 200 validated social-video URLs). Original-topic relevance still applies to expanded queries; winter-fail aliases cannot admit scenery or music. Previously selected sources are remembered in browser-local history (180 URLs), excluded before provider budgets and enforced again before download. YouTube reads further into results and tries related queries. Unavailable public engines are not repeatedly retried for every variant; safe diagnostics include recognized HTTP status codes. No challenge/login bypass or guaranteed network availability is implied.

The search panel exposes independent voice, SFX, automatic-preview and source-reuse controls. A successful five-clip discovery prepares missing rank announcements when voice is enabled, then optionally starts the real MP4 render with the chosen mix. Free discovery no longer disables voice. Failed or partial searches do not start a render. After an accepted new search, the editor starts empty and retains the old clips in a separate recoverable browser backup. Zero results cannot look like a successful old 5/5 selection; **Vrátit předchozí klipy** is an explicit restoration action. Incomplete export is disabled. Restored legacy projects with five unversioned four-second cuts receive a prominent source-recovery notice. Live voice failures retain selected clips and report the render failure without a paid fallback. Source scenes keep variable lengths up to 30s; long-shot motion selection remains a heuristic with manual review.

Run `node scripts/discovery-browser-test.mjs` for an isolated real discovery/edit/render test using local search and speech fixtures: different source URLs on repeated searches, retained 3–12 second scenes, automatic actual MP4 mixing, speech-frequency presence/absence, independent switches, history across refresh, opt-in reuse and zero-result preservation. It does not test external search availability or live TTS quality.

### Source identity and unverified punchlines

`exclude_asset_ids` (up to 200 validated local IDs) resolves retained original sources and compares their exact SHA-256 files before preparing downloaded media. Byte-identical files are rejected even under different public URLs, including repeats within one search. A cut follows original-source metadata rather than hashing only its old four-second excerpt. Missing expired assets do not crash the search; URL exclusions still apply. This does not identify differently encoded visual reposts. Downloader metadata now persists its public source URL.

Automatic source selection and automatic recutting explicitly retain `review_required`; free motion/edge scores are technical metrics, not semantic fall/punchline verification. A `selection_version` distinguishes new whole-scene selections and deliberate manual cuts from old unversioned four-second projects. Blurring accepts the full 2–30-second editing range.

Synthetic scene, audio and export tests verify the mechanics but cannot establish that a real source contains a complete fall or punchline. Verifying an omitted ending requires the retained source footage; it cannot be reconstructed from an already clipped MP4.

### Bounded discovery and incremental preparation

Discovery has a shared 300-second monotonic budget across link search, hashing, download, preview preparation, scene selection, cut creation and OCR. Public queries are round-robin across sources and stop adding variants after a 35-second phase; direct YouTube search has a 45-second phase and shorter per-command limits. Free selection runs in batches and stops once five usable scenes exist; per-source scene analyses are cached within the job. Browser-compatible H.264/AAC candidates and generated cuts are remuxed for preview rather than encoded twice. Original media and timeline lengths are retained. Paid semantic selection still uses its explicit paid mode.

`POST /api/jobs/{id}/cancel` signals the active discovery, terminates its owned subprocess tree, preserves completed media and releases the single worker slot only after cleanup. Windows uses `taskkill /T /F`; Linux descendant termination is exercised with real subprocesses. Native Windows process-tree cleanup still needs confirmation on that platform. HTTP reads are bounded and cooperative, so cancellation/deadline finalization may take a short grace period. Job polling reports elapsed/remaining seconds and the current phase. Stop requests racing with job completion do not discard its result or automatically start another preview.

On cancellation/deadline, already analyzed windows can be recovered using the full retained source and original start/duration without starting new transcoding. Incomplete sources are not presented as successful ranking scenes; completed but unanalysed source videos are linked separately. Optional rendering/TTS after discovery is a separate task and is not covered by the discovery budget.
