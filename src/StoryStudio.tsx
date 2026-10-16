import { useEffect, useRef, useState } from "react";
import {
  Clapperboard,
  Download,
  Eye,
  Film,
  LoaderCircle,
  Mic2,
  Sparkles,
  Volume2,
} from "lucide-react";
import "./story.css";

const EXAMPLE_VIDEO = "/examples/story-narrated.mp4";
const EXAMPLE_POSTER = "/examples/story-poster.png";

const STORIES = {
  parcel: {
    name: "Ztracený balíček",
    detail: "Malá pomoc, velká radost.",
    lines: [
      "Alex se procházel parkem. Netušil, že dnes někomu změní den.",
      "Na cestě uviděl malý balíček. Jeho majitel už byl daleko.",
      "Místo aby šel dál, zastavil se a balíček zvedl.",
      "Patřil Samovi. Když mu ho Alex vrátil, oběma se rozzářil den.",
      "Někdy stačí malá laskavost. Z obyčejného dne se stane příběh.",
    ],
  },
  kindness: {
    name: "Nečekaná laskavost",
    detail: "Dárek pro někoho, kdo ho nečekal.",
    lines: [
      "Alex šel parkem. Přemýšlel, jak někomu udělat radost.",
      "U lavičky čekal Sam. Ten den se cítil trochu sám.",
      "Alex zvedl malý dárek, který pro něj připravil.",
      "Podal ho Samovi. Někdy potěší hlavně to, že si někdo vzpomene.",
      "Teď už šli společně. Malé gesto dokáže změnit celý den.",
    ],
  },
  reunion: {
    name: "Znovu spolu",
    detail: "Setkání dvou starých přátel.",
    lines: [
      "Alex se vracel parkem, který znal už od dětství.",
      "U staré lavičky zahlédl známou tvář. Mohl to být Sam?",
      "Zastavil se. Svého kamaráda neviděl už několik let.",
      "Sam ho poznal a zamával. Tolik si toho potřebovali říct.",
      "Domů už pokračovali společně. Některá přátelství prostě nezmizí.",
    ],
  },
};
type StoryKey = keyof typeof STORIES;
type Provider = "local" | "piper";
type Job = {
  id: string;
  status: string;
  progress: number;
  message: string;
  image?: string;
  video?: string;
  duration?: number;
  voice?: boolean;
};
type Saved = {
  story?: StoryKey;
  duration?: number;
  captions?: string[];
  provider?: Provider;
  voice?: boolean;
  job?: Job;
  image?: string;
  video?: string;
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
        : "Požadavek se nepodařil.",
    );
  return result;
}
function load(): Saved {
  try {
    const saved = JSON.parse(
      localStorage.getItem("short-story-project") || "{}",
    );
    if (
      !Object.hasOwn(STORIES, saved.story) ||
      ![35, 40, 45].includes(saved.duration) ||
      !Array.isArray(saved.captions) ||
      saved.captions.length !== 5 ||
      saved.captions.some(
        (line: unknown) => typeof line !== "string" || line.length > 160,
      )
    )
      return {};
    return saved;
  } catch {
    return {};
  }
}
export default function StoryStudio() {
  const [saved] = useState(load);
  const [story, setStory] = useState<StoryKey>(saved.story || "parcel");
  const [duration, setDuration] = useState(saved.duration || 40);
  const [captions, setCaptions] = useState(
    saved.captions || STORIES.parcel.lines,
  );
  const [provider, setProvider] = useState<Provider>(
    saved.provider === "piper" ? "piper" : "local",
  );
  const [voice, setVoice] = useState(saved.voice ?? true);
  const [caps, setCaps] = useState({
    local: false,
    piper: false,
    blender: false,
  });
  const [job, setJob] = useState<Job | null>(saved.job || null);
  const [image, setImage] = useState(saved.image || "");
  const [video, setVideo] = useState(saved.video || "");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [audio, setAudio] = useState("");
  const [stale, setStale] = useState(false);
  const audioElement = useRef<HTMLAudioElement>(null);
  const busy = sending || (!!job && !["done", "failed"].includes(job.status));
  useEffect(() => {
    request<typeof caps>("/capabilities")
      .then(setCaps)
      .catch(() => setError("Server není dostupný."));
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(
        "short-story-project",
        JSON.stringify({
          story,
          duration,
          captions,
          provider,
          voice,
          job,
          image,
          video,
        }),
      );
    } catch {}
  }, [story, duration, captions, provider, voice, job, image, video]);
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
          if (next.image) {
            setImage(next.image);
            setVideo("");
          }
          if (next.video) setVideo(next.video);
          setStale(false);
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
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
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
  function playExample() {
    setVideo(EXAMPLE_VIDEO);
    setImage(EXAMPLE_POSTER);
    setStale(false);
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
        <span>3D PŘÍBĚHY S VYPRAVĚČEM</span>
      </header>
      <main className="story-grid">
        <section>
          <div className="story-eyebrow">
            <Sparkles size={14} /> MALÝ PŘÍBĚH. VLASTNÍ HLAS.
          </div>
          <h1>
            Příběhy, které
            <br />
            <em>ožijí a promluví.</em>
          </h1>
          <p className="story-lead">
            Dva lidé, krátký příběh a mužský hlas, který tě provede dějem. Tvůj
            animovaný Short dlouhý 35–45 sekund.
          </p>
          <div className="story-tags">
            <span>Skutečné 3D</span>
            <span>Český vypravěč</span>
            <span>9:16</span>
            <span>Bez API klíče</span>
          </div>
          <div className="story-panel">
            <h2>
              01 <span>Vyber příběh</span>
            </h2>
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
              Tři připravené děje se stejnými postavami. Úprava komentáře mění
              hlas a titulky, ne choreografii animace.
            </p>
          </div>
          <div className="story-panel">
            <h2>
              02 <span>Mužský vypravěč</span>
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
              Komentář, který vysvětluje děj
            </label>
            <label className="story-select">
              HLAS
              <select
                aria-label="Mužský hlas příběhu"
                value={provider}
                disabled={busy || !voice}
                onChange={(e) => {
                  setProvider(e.target.value as Provider);
                  setStale(true);
                  setAudio("");
                }}
              >
                <option value="local" disabled={!caps.local}>
                  Český mužský · základní syntetický
                </option>
                <option value="piper" disabled={!caps.piper}>
                  Jirka · přirozenější lokální hlas
                  {!caps.piper ? " (model není stažený)" : ""}
                </option>
              </select>
            </label>
            <p className="story-note">
              {provider === "local"
                ? "Základní hlas funguje zdarma a offline. Zní roboticky; přehraj si ukázku před exportem."
                : "Český mužský hlas Piper / Jirka. Po stažení modelu funguje offline."}
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
              Poslechnout mužský hlas
            </button>
            {audio && (
              <div className="story-audio">
                <audio
                  ref={audioElement}
                  controls
                  src={audio}
                  aria-label="Ukázka mužského vypravěče"
                />
                <a href={audio} download="muzsky-hlas.wav">
                  Stáhnout hlasovou ukázku
                </a>
              </div>
            )}
          </div>
          <div className="story-panel">
            <h2>
              03 <span>Délka a komentář scén</span>
            </h2>
            <div className="story-length">
              {[35, 40, 45].map((n) => (
                <button
                  key={n}
                  disabled={busy}
                  aria-pressed={duration === n}
                  className={duration === n ? "selected" : ""}
                  onClick={() => {
                    setDuration(n);
                    setStale(true);
                  }}
                >
                  {n} sekund
                </button>
              ))}
            </div>
            <div className="story-beats">
              {captions.map((text, i) => (
                <label key={i}>
                  <span>
                    {String(i + 1).padStart(2, "0")}
                    <small>
                      {(i * duration) / 5}–{((i + 1) * duration) / 5} s
                    </small>
                  </span>
                  <textarea
                    aria-label={`Komentář scény ${i + 1}`}
                    maxLength={160}
                    value={text}
                    disabled={busy}
                    onChange={(e) => {
                      setCaptions((old) =>
                        old.map((v, index) =>
                          index === i ? e.target.value : v,
                        ),
                      );
                      setStale(true);
                      setAudio("");
                    }}
                  />
                </label>
              ))}
            </div>
            <p className="story-note">
              Vypravěč přečte tyto věty ve správných scénách. Dlouhé věty zkrať;
              slova na konci neusekáváme.
            </p>
          </div>
          <div className="story-actions">
            <button
              className="story-secondary"
              disabled={busy || !caps.blender}
              onClick={() => generate(true)}
            >
              <Eye size={17} />
              Ukázat vzhled
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
              Vygenerovat Short{voice ? " s hlasem" : ""}
            </button>
          </div>
          <p className="story-note">
            Skutečný lokální render trvá několik minut. Jednoduché stylizované
            3D, MP4 360 × 640, 12 snímků/s. Zatím nejde o polorealistický film
            ani generování libovolného děje z textu.
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
                    Stránku můžeš obnovit; uloženou úlohu znovu načteme. Server
                    musí během renderu běžet.
                  </span>
                </>
              )}
            </div>
          )}
        </section>
        <aside className="story-preview">
          <div className="story-preview-label">
            <span>Náhled tvého příběhu</span>
            <span>9:16</span>
          </div>
          <button
            className="story-secondary story-example-button"
            disabled={busy}
            onClick={playExample}
          >
            <Film size={16} />
            Přehrát hotovou ukázku s hlasem
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
              <img src={image} alt="Skutečný 3D náhled lidí v parku" />
            ) : (
              <div className="story-empty">
                <div className="story-preview-icon">
                  <Clapperboard size={44} />
                </div>
                <h3>Podívej se. Poslechni si.</h3>
                <p>
                  Nejdřív si poslechni hlas a vytvoř rychlý obrázkový náhled.
                  Potom vygeneruj celý příběh.
                </p>
                <button
                  disabled={busy || !caps.blender}
                  onClick={() => generate(true)}
                >
                  <Eye size={16} />
                  Vytvořit náhled
                </button>
              </div>
            )}
          </div>
          <div className="story-preview-foot">
            <strong>
              {video
                ? video === EXAMPLE_VIDEO
                  ? "Ukázkový příběh · 35 sekund · mužský hlas"
                  : "Hotový MP4 příběh · přehraj se zvukem"
                : image
                  ? "Skutečně vyrenderovaný snímek"
                  : "Tvůj příběh začíná tady"}
            </strong>
            <p>
              {stale && (image || video)
                ? "Nastavení se změnilo. Vytvoř nový náhled nebo film."
                : "Náhled i film používají stejnou scénu a postavy."}
            </p>
            {video && (
              <a
                className="story-primary"
                href={video}
                download="pribeh-s-vypravecem.mp4"
              >
                <Download size={16} />
                Stáhnout MP4
              </a>
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}
