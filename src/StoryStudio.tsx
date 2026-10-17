import { useEffect, useState } from "react";
import {
  Clapperboard,
  Download,
  Eye,
  Film,
  Link,
  LoaderCircle,
  Mic2,
  Sparkles,
  Volume2,
  X,
} from "lucide-react";
import "./story.css";
const EXAMPLE_VIDEO = "/examples/story-english.mp4";
const EXAMPLE_POSTER = "/examples/story-english-poster.png";
const STORAGE = "short-story-project-v2-en";
const STORIES = {
  parcel: {
    name: "The lost parcel",
    detail: "A small kindness changes an ordinary day.",
    lines: [
      "Alex was heading home through the park, expecting nothing out of the ordinary.",
      "Then he spotted a forgotten parcel beside the path. Its owner could still be close by.",
      "He picked it up carefully. Instead of walking away, he decided to help whoever had lost it.",
      "Sam recognized the parcel. A grateful wave said everything.",
      "They walked on together. A small act of kindness had turned strangers into friends.",
    ],
  },
  kindness: {
    name: "An unexpected gift",
    detail: "A thoughtful gesture for someone feeling alone.",
    lines: [
      "Alex had brought a small surprise for his friend.",
      "Sam was waiting by the bench, lost in thought.",
      "Alex picked up the gift he had brought along.",
      "He handed it to Sam, who waved his thanks.",
      "They headed home together. Sometimes, being remembered is the greatest gift.",
    ],
  },
  reunion: {
    name: "Together again",
    detail: "Two old friends cross paths after years apart.",
    lines: [
      "Alex was walking through a park he knew well.",
      "By the old bench, he noticed a familiar face.",
      "He stopped. It was Sam, a friend he had not seen in years.",
      "Sam waved. Some friendships never really fade.",
      "They walked on together, with years of stories to share.",
    ],
  },
};
type StoryKey = keyof typeof STORIES;
type Provider = "local" | "piper" | "openai";
type Reference = {
  id: string;
  url: string;
  mode: "basic" | "ai";
  notes: string;
  frames: string[];
  style: {
    coat_primary: string;
    coat_secondary: string;
    backdrop: string;
    lighting: string;
    framing: string;
  };
};
type Job = {
  id: string;
  status: string;
  progress: number;
  message: string;
  kind?: string;
  image?: string;
  video?: string;
  reference?: Reference;
};
type Capabilities = {
  local: boolean;
  piper: boolean;
  openai: boolean;
  ai: boolean;
  blender: boolean;
  beats: { start: number; end: number; speech_start: number }[];
};
type Saved = {
  story?: StoryKey;
  duration?: number | null;
  topic?: string;
  captions?: string[];
  provider?: Provider;
  voice?: boolean;
  job?: Job;
  image?: string;
  video?: string;
  reference?: Reference;
  referenceUrl?: string;
  referenceMode?: "basic" | "ai";
};
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch("/api/story" + path, {
    method: body === undefined ? "GET" : "POST",
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : Array.isArray(result.detail)
          ? result.detail.map((d: { msg: string }) => d.msg).join(" ")
          : "The request could not be completed.",
    );
  return result;
}
function load(): Saved {
  try {
    const s = JSON.parse(localStorage.getItem(STORAGE) || "{}");
    if (
      !Object.hasOwn(STORIES, s.story) ||
      (s.duration != null && (!Number.isInteger(s.duration) || s.duration < 10 || s.duration > 120)) ||
      !Array.isArray(s.captions) ||
      s.captions.length !== 5 ||
      s.captions.some((x: unknown) => typeof x !== "string" || x.length > 160)
    )
      return {};
    return s;
  } catch {
    return {};
  }
}
const stamp = (seconds: number) => `${seconds.toFixed(1).replace(/\.0$/, "")}s`;
export default function StoryStudio() {
  const [saved] = useState(load);
  const [story, setStory] = useState<StoryKey>(saved.story || "parcel");
  const [duration, setDuration] = useState<number | null>(saved.duration ?? null);
  const [topic, setTopic] = useState(saved.topic || "");
  const [writing, setWriting] = useState(false);
  const [captions, setCaptions] = useState(
    saved.captions || STORIES.parcel.lines,
  );
  const [provider, setProvider] = useState<Provider>(saved.provider || "local");
  const [voice, setVoice] = useState(saved.voice ?? true);
  const [caps, setCaps] = useState<Capabilities>({
    local: false,
    piper: false,
    openai: false,
    ai: false,
    blender: false,
    beats: [],
  });
  const [job, setJob] = useState<Job | null>(saved.job || null);
  const [image, setImage] = useState(saved.image || "");
  const [video, setVideo] = useState(saved.video || "");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [audio, setAudio] = useState("");
  const [stale, setStale] = useState(false);
  const [reference, setReference] = useState<Reference | null>(
    saved.reference || null,
  );
  const [referenceUrl, setReferenceUrl] = useState(saved.referenceUrl || "");
  const [referenceMode, setReferenceMode] = useState<"basic" | "ai">(
    saved.referenceMode || "basic",
  );
  const busy = writing || sending || (!!job && !["done", "failed"].includes(job.status));
  useEffect(() => {
    request<Capabilities>("/capabilities")
      .then(setCaps)
      .catch(() => setError("The server is unavailable."));
    if (saved.reference)
      request<Reference>("/references/" + saved.reference.id)
        .then(setReference)
        .catch(() => {
          setReference(null);
          setError(
            "The saved reference is no longer on the server. Import it again to use its style.",
          );
        });
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE,
        JSON.stringify({
          story,
          duration,
          topic,
          captions,
          provider,
          voice,
          job,
          image,
          video,
          reference,
          referenceUrl,
          referenceMode,
        }),
      );
    } catch {}
  }, [
    story,
    duration,
    topic,
    captions,
    provider,
    voice,
    job,
    image,
    video,
    reference,
    referenceUrl,
    referenceMode,
  ]);
  useEffect(() => {
    if (!job || ["done", "failed"].includes(job.status)) return;
    let disposed = false,
      polling = false;
    const timer = setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        const next = await request<Job>("/jobs/" + job.id);
        if (disposed) return;
        setJob(next);
        if (next.status === "done") {
          if (next.reference) {
            setReference(next.reference);
            setStale(true);
          } else {
            if (next.image) {
              setImage(next.image);
              setVideo("");
            }
            if (next.video) setVideo(next.video);
            setStale(false);
          }
        }
        if (next.status === "failed") setError(next.message);
      } catch (e) {
        if (!disposed) {
          setError((e as Error).message);
          setJob(null);
        }
      } finally {
        polling = false;
      }
    }, 1500);
    return () => {
      disposed = true;
      clearInterval(timer);
    };
  }, [job?.id, job?.status]);
  async function generate(preview: boolean) {
    if (busy) return;
    setSending(true);
    setError("");
    try {
      setJob(
        await request<Job>("/generate", {
          story,
          duration,
          captions,
          provider,
          voice,
          preview,
          reference_id: reference?.id || null,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }
  async function writeScript() {
    setWriting(true);
    setError("");
    try {
      const plan = await request<{story: StoryKey; captions: string[]}>("/script", {topic});
      setStory(plan.story);
      setCaptions(plan.captions);
      setDuration(null);
      setStale(true);
      setAudio("");
    } catch (e) { setError((e as Error).message); }
    finally { setWriting(false); }
  }
  async function voicePreview() {
    setPreviewing(true);
    setError("");
    setAudio("");
    try {
      const result = await request<{ audio: string }>("/voice-preview", {
        text: captions[0],
        provider,
      });
      setAudio(result.audio);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPreviewing(false);
    }
  }
  async function importReference() {
    if (busy) return;
    setSending(true);
    setError("");
    try {
      setJob(
        await request<Job>("/references", {
          url: referenceUrl,
          mode: referenceMode,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }
  function choose(key: StoryKey) {
    setStory(key);
    setCaptions([...STORIES[key].lines]);
    setStale(true);
    setAudio("");
  }
  return (
    <div className="story-studio">
      <header className="story-header">
        <a href="/" className="story-brand">
          <Clapperboard />
          short<span>story</span>
        </a>
        <span>ENGLISH STORY STUDIO</span>
      </header>
      <main className="story-grid">
        <section>
          <div className="story-eyebrow">
            <Sparkles size={14} />A LITTLE STORY. ROOM TO BREATHE.
          </div>
          <h1>
            Stories that
            <br />
            <em>move and speak.</em>
          </h1>
          <p className="story-lead">
            Two people. One meaningful moment. Create an animated
            Short with an English male narrator and pauses that follow the
            action.
          </p>
          <div className="story-tags">
            <span>Actual 3D</span>
            <span>English narration</span>
            <span>9:16</span>
            <span>Voice preview</span>
          </div>
          <div className="story-panel">
            <h2>
              01 <span>Video topic and story</span>
            </h2>
            <label className="story-select">
              VIDEO TOPIC · 2–3 SENTENCES
              <textarea aria-label="Video topic" maxLength={1000} rows={4}
                placeholder="Describe your idea, the central moment and how it should end."
                value={topic} disabled={busy} onChange={(e) => setTopic(e.target.value)} />
            </label>
            <button className="story-secondary" disabled={busy || !caps.ai || topic.trim().length < 5} onClick={writeScript}>
              {writing ? "Writing script…" : "Create English script from topic"}
            </button>
            <p className="story-note">AI adapts your topic to the available park scenes. Review the script below before rendering. This uses the configured OpenAI API and may incur charges.
              {!caps.ai && " An OpenAI API key is required on the server; manual narration remains available."}
            </p>
            <div className="story-options">
              {Object.entries(STORIES).map(([key, item]) => (
                <button
                  key={key}
                  disabled={busy}
                  className={story === key ? "selected" : ""}
                  onClick={() => choose(key as StoryKey)}
                >
                  <strong>{item.name}</strong>
                  <span>{item.detail}</span>
                </button>
              ))}
            </div>
            <p className="story-note">
              These starting stories use fixed choreography. Editing narration
              changes the voice and captions, not the character actions.
            </p>
          </div>
          <div className="story-panel">
            <h2>
              02 <span>Reference video</span>
            </h2>
            <p className="story-note">
              Share a public YouTube, TikTok or Instagram video to guide the
              approximate look. The next preview and export will use its
              supported visual settings.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void importReference();
              }}
            >
              <label className="story-select">
                VIDEO LINK
                <input
                  aria-label="Reference video URL"
                  type="url"
                  placeholder="https://www.youtube.com/shorts/…"
                  value={referenceUrl}
                  disabled={busy}
                  required
                  onChange={(e) => setReferenceUrl(e.target.value)}
                />
              </label>
              <label className="story-select">
                ANALYSIS
                <select
                  aria-label="Reference analysis"
                  value={referenceMode}
                  disabled={busy}
                  onChange={(e) =>
                    setReferenceMode(e.target.value as "basic" | "ai")
                  }
                >
                  <option value="basic">
                    Basic visual analysis · no paid API
                  </option>
                  <option value="ai" disabled={!caps.ai}>
                    AI visual analysis{!caps.ai ? " · API key required" : ""}
                  </option>
                </select>
              </label>
              <button
                className="story-secondary"
                type="submit"
                disabled={busy || !referenceUrl.trim()}
              >
                <Link size={16} />
                Import and analyze reference
              </button>
            </form>
            <p className="story-note">
              Basic analysis samples real frames for colors and lighting.
              Optional AI analysis also estimates camera distance. Neither mode
              copies the story, exact models, motion or narrator. AI mode uses
              the configured OpenAI account and may incur usage charges. Public
              download restrictions still apply. Up to 120 seconds / 60 MB.
            </p>
            {reference && (
              <div className="story-reference">
                <div className="story-reference-heading">
                  <strong>
                    {reference.mode === "ai"
                      ? "AI-analyzed reference"
                      : "Basic visual reference"}{" "}
                    · applied
                  </strong>
                  <button
                    aria-label="Remove reference"
                    disabled={busy}
                    onClick={() => {
                      setReference(null);
                      setStale(true);
                    }}
                  >
                    <X size={16} />
                  </button>
                </div>
                <div className="story-reference-frames">
                  {reference.frames.map((url, i) => (
                    <img
                      key={url}
                      src={url}
                      alt={`Actual reference frame ${i + 1}`}
                    />
                  ))}
                </div>
                <div className="story-reference-style">
                  <span
                    style={{ background: "#" + reference.style.coat_primary }}
                  />
                  <span
                    style={{ background: "#" + reference.style.coat_secondary }}
                  />
                  <small>
                    {reference.style.lighting} light · {reference.style.framing}{" "}
                    framing
                  </small>
                </div>
                <p>{reference.notes}</p>
                <a href={reference.url} target="_blank" rel="noreferrer">
                  Open original reference
                </a>
              </div>
            )}
          </div>
          <div className="story-panel">
            <h2>
              03 <span>English male narrator</span>
            </h2>
            <label className="story-voice-toggle">
              <input
                type="checkbox"
                checked={voice}
                disabled={busy}
                onChange={(e) => {
                  setVoice(e.target.checked);
                  setStale(true);
                }}
              />
              <Mic2 size={18} />
              Narrate the story
            </label>
            <label className="story-select">
              VOICE
              <select
                aria-label="Narrator voice"
                value={provider}
                disabled={busy || !voice}
                onChange={(e) => {
                  setProvider(e.target.value as Provider);
                  setStale(true);
                  setAudio("");
                }}
              >
                <option value="local" disabled={!caps.local}>
                  English male · basic synthetic voice
                </option>
                <option value="piper" disabled={!caps.piper}>
                  Ryan · local neural voice
                  {!caps.piper ? " (model not installed)" : ""}
                </option>
                <option value="openai" disabled={!caps.openai}>
                  Onyx · natural male voice
                  {!caps.openai ? " (API key required)" : ""}
                </option>
              </select>
            </label>
            <p className="story-note">
              {provider === "local"
                ? "The basic voice works offline and sounds robotic. Preview it before exporting. Natural voices require their configured model or provider."
                : provider === "piper"
                  ? "Ryan is an English male neural voice that runs offline after its model is installed."
                  : "Onyx uses the configured OpenAI API and may incur provider charges."}
            </p>
            <button
              className="story-secondary"
              disabled={busy || previewing || !voice || !caps[provider]}
              onClick={voicePreview}
            >
              {previewing ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <Volume2 size={16} />
              )}
              Preview male voice
            </button>
            {audio && (
              <div className="story-audio">
                <audio
                  controls
                  src={audio}
                  aria-label="Male narrator preview"
                />
                <a href={audio} download="male-narrator.wav">
                  Download voice preview
                </a>
              </div>
            )}
          </div>
          <div className="story-panel">
            <h2>
              04 <span>Duration and scene narration</span>
            </h2>
            <div className="story-length">
              <button disabled={busy} aria-pressed={duration === null}
                className={duration === null ? "selected" : ""}
                onClick={() => { setDuration(null); setStale(true); }}>Automatic · follow the story</button>
              <label>Optional duration (10–120 seconds)
                <input aria-label="Optional duration" type="number" min={10} max={120}
                  disabled={busy} value={duration ?? ""} placeholder="Automatic"
                  onChange={(e) => { setDuration(e.target.value ? Math.max(10, Math.min(120, Number(e.target.value))) : null); setStale(true); }} />
              </label>
            </div>
            <div className="story-beats">
              {captions.map((text, i) => {
                const cue = caps.beats[i];
                return (
                  <label key={i}>
                    <span>
                      {String(i + 1).padStart(2, "0")}
                      <small>
                        {cue && duration !== null
                          ? `${stamp(cue.start * duration)}–${stamp(cue.end * duration)}`
                          : `Scene ${i + 1}`}
                      </small>
                    </span>
                    <textarea
                      aria-label={`Scene ${i + 1} narration`}
                      maxLength={160}
                      value={text}
                      disabled={busy}
                      onChange={(e) => {
                        setCaptions((old) =>
                          old.map((v, j) => (j === i ? e.target.value : v)),
                        );
                        setStale(true);
                        setAudio("");
                      }}
                    />
                  </label>
                );
              })}
            </div>
            <p className="story-note">
              Narration follows arrival, discovery, the key action, the response
              and the ending. Automatic duration follows the actual voice and allows breathing room. Short pauses separate complete thoughts; the key
              action is spoken about as it happens. Overlong lines are rejected
              rather than cut off or rushed.
            </p>
          </div>
          <div className="story-actions">
            <button
              className="story-secondary"
              disabled={busy || !caps.blender}
              onClick={() => generate(true)}
            >
              <Eye size={17} />
              Preview the scene
            </button>
            <button
              className="story-primary"
              disabled={busy || !caps.blender || (voice && !caps[provider])}
              onClick={() => generate(false)}
            >
              {busy ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <Film size={17} />
              )}
              Generate Short{voice ? " with narration" : ""}
            </button>
          </div>
          <p className="story-note">
            Rendering takes several minutes and can be slower on free hosting.
            Output: MP4, 360 × 640, 12 fps. This version uses simple stylized 3D
            and prepared stories. Download finished videos: hosting restarts may
            remove them.
          </p>
          {error && (
            <div role="alert" className="story-error">
              {error}
            </div>
          )}
          {job && (
            <div role="status" className="story-status">
              <strong>{job.message}</strong>
              {busy && (
                <>
                  <progress max="100" value={job.progress} />
                  <span>
                    You can refresh the page to reconnect to a saved job. The
                    server must keep running.
                  </span>
                </>
              )}
            </div>
          )}
        </section>
        <aside className="story-preview">
          <div className="story-preview-label">
            <span>Your story preview</span>
            <span>9:16</span>
          </div>
          <button
            className="story-secondary story-example-button"
            disabled={busy}
            onClick={() => {
              setVideo(EXAMPLE_VIDEO);
              setImage(EXAMPLE_POSTER);
              setStale(false);
            }}
          >
            <Film size={16} />
            Play the English example
          </button>
          <div className="story-phone">
            {video ? (
              <video
                key={video}
                src={video}
                controls
                playsInline
                preload="metadata"
                poster={image || undefined}
              />
            ) : image ? (
              <img src={image} alt="Actual 3D scene preview" />
            ) : (
              <div className="story-empty">
                <div className="story-preview-icon">
                  <Clapperboard size={44} />
                </div>
                <h3>Watch. Listen. Create.</h3>
                <p>
                  Play the finished example, preview the voice or render a frame
                  before making your own Short.
                </p>
                <button
                  disabled={busy || !caps.blender}
                  onClick={() => generate(true)}
                >
                  <Eye size={16} />
                  Create a scene preview
                </button>
              </div>
            )}
          </div>
          <div className="story-preview-foot">
            <strong>
              {video
                ? video === EXAMPLE_VIDEO
                  ? "English example · 35 seconds · male narrator"
                  : "Your MP4 story · play with sound"
                : image
                  ? "An actual rendered frame"
                  : "Your story starts here"}
            </strong>
            <p>
              {stale && (image || video)
                ? "Settings changed. Render a new preview or film to see them."
                : "The preview and film share the same characters and visual settings."}
            </p>
            {video && (
              <a
                className="story-primary"
                href={video}
                download="english-story.mp4"
              >
                <Download size={16} />
                Download MP4
              </a>
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}
