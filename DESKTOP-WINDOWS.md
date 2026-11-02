# Rank Studio pro Windows

Desktop používá původní editor, barvy, předlohy, klipy, rozmazání/odstranění
překryvů, titulky, efekty, hlasy i export do nejvýše 40 sekund. Běží ve vlastním
okně a s přibaleným backendem; uživatel nespouští terminál, Python ani Render.
Technický návrh a hranice jsou v [DESKTOP.md](DESKTOP.md).

## Instalace a první nastavení

Ověřená sestava: [stáhnout Windows ZIP, 341 MB](https://github.com/Mejkl0s/youtube-shorts/actions/runs/41534137780/artifacts/13183257915).
GitHub pro stažení artefaktu vyžaduje přihlášení. ZIP rozbal a spusť
`Rank-Studio-2.0.0-Setup.exe`. Pokud se přímé stažení neotevře, na
[stránce úspěšného běhu](https://github.com/Mejkl0s/youtube-shorts/actions/runs/41534137780#artifacts)
dole vyber **Artifacts → Rank-Studio-Windows-x64**.

Výstup Windows buildu je `Rank-Studio-2.0.0-Setup.exe`. Instalátor přidá aplikaci
do nabídky Start a odinstalaci do Windows. Produkční vydání má mít platný podpis
vydavatele. Nepodepsaný CI build je vývojový artefakt, ne ověřené produkční vydání.
Windows instalátor se sestavuje na Windows runneru. Dokončené kontroly a stav
instalace jsou doložené v [záznamu ověření](DESKTOP-VERIFICATION.md); samotný
Linuxový sidecar není Windows instalátor.

1. Spusť nainstalovanou aplikaci **Rank Studio**.
2. V průvodci vyber **Lokální**, **Cloudový** nebo **Kombinovaný** režim.
3. Aktivuj poskytovatele. U lokálních lze vyhledat známé běžící služby a zadat
   loopback adresu ručně. U cloudu ulož vlastní klíč do jeho samostatného pole.
4. Klikni na **Ověřit a načíst modely**. Seznam vzniká z API, ne z vymyšlených ID.
   Model bez podpory obrázků může psát text; nebude vybírat děj z videa.
5. Vyber model a dokonči nastavení. Průvodce lze dokončit i bez dostupné AI,
   aby zůstal přístupný editor a ruční střih.

Průvodce se znovu otevírá přes **Nastavení → AI modely → Spustit průvodce
nastavením** a ponechá existující připojení, klíče a projekty. Horní lišta a
Nastavení sdílejí jednu konfiguraci. Nová volba platí pro další úlohy, rozpracovaná
úloha dokončí práci se svým původním poskytovatelem, modelem a klíčem.

Lokální režim je výchozí. Cloudová AI může účtovat požadavky podle poskytovatele;
aktivuje ji uživatel vlastním klíčem. Neexistuje automatický placený fallback ani
přeposílání snímků jiné službě po chybě. Klíč je navázaný na poskytovatele a
origin adresy: při změně vlastního serveru se původní klíč neposílá na jiný host.
Původní záznam zůstane chráněný, dokud ho výslovně nezměníš nebo neodstraníš.

## Poskytovatelé a schopnosti

| Poskytovatel | Připojení a omezení |
|---|---|
| Ollama | Nativní tags/show/chat/pull/delete API; cloudové aliasy jsou odmítnuté. |
| LM Studio, llama.cpp, vlastní lokální server | OpenAI kompatibilní API na loopbacku. Pokud metadata nedokládají obrazovou podporu, zobrazí se „Nelze zjistit“ a lze ji výslovně potvrdit podle dokumentace modelu. |
| OpenAI | Models + Chat Completions; Responses pro původní webový research. U reasoning modelů se používá odpovídající limit tokenů. |
| Anthropic Claude | Vlastní Messages a Models API, vlastní hlavičky a formát obrázků. |
| Google Gemini | Vlastní Models / generateContent API, inlineData a autentizace v hlavičce. |
| DeepSeek | Models a Chat Completions; známé textové modely se nepoužívají pro obraz. |
| OpenRouter | Modely, modality a dostupný ceník z jeho API. |
| Vlastní cloudový endpoint | HTTPS OpenAI kompatibilní API s odděleným klíčem. |

Poskytovatelé neprovádějí slepé opakování inference: případné opakování placeného
požadavku je na uživateli. Bezpečné GET načítání modelů má omezené opakování.
Společné rozhraní zahrnuje generování, streaming, zjišťování modelů, kontrolu
obrazové schopnosti a zrušení řízeného požadavku. Existující střih používá
strukturované odpovědi; textový pomocník má vlastní zobrazení a ukládanou historii. Poskytovatelem vrácené počty tokenů se zobrazí u odpovědi, pokud jsou dostupné.

Větší model není zárukou správného výběru. Vizuální střih stále hodnotí vzorkované
snímky, neslyší původní zvuk a může přehlédnout pointu. Ověření protokolu se
simulovanou odpovědí není testem kvality modelu.

## Lokální modely, hlasy a hardware

**Nastavení → Lokální modely** umožní spustit nainstalovanou Ollama, stáhnout Qwen
3B/7B přes její oficiální API, zobrazit skutečný průběh vrstvy, pozastavit stahování
a pokračovat podle podpory Ollama. Hotový model se hlásí až po úspěšném stažení
a ověření seznamu modelů. Odstranění vyžaduje potvrzení a je zablokované při
probíhající práci. Model právě používaný úlohou se během ní znovu nestahuje.

Přes stejnou sekci lze stáhnout český a anglický hlas Piper. Délky a publisher
digests se kontrolují podle existujícího připnutého manifestu, částečné soubory
nejsou vydávané za hotový hlas a obnovení používá HTTP Range, pokud ho zdroj
podporuje. Tato veřejná stažení neobsahují API klíč. Před stahováním se kontroluje
místo na příslušném disku. Katalog uvádí odhady velikosti, doporučenou RAM a
odkaz na zdroj/licenci; skutečné počty bajtů pocházejí z průběhu nebo instalace.

Úložiště lze změnit pro Ollama spuštěnou aplikací. Externí služba používá vlastní
`OLLAMA_MODELS`; aplikace její adresář neumí automaticky zjistit ani přestěhovat.
Kontrola místa u externí služby vychází z nakonfigurovaného adresáře, proto jeho
shodu ověř v nastavení té služby. Modely LM Studio a llama.cpp se spravují jejich
vlastními nástroji; aplikace používá jejich skutečně nabízené modely a neukončuje
cizí servery. Chybějící služby a volitelný Tesseract mají odkazy na oficiální zdroje.

**Hardware** zjistí OS, CPU, logické procesory, RAM a disk. `nvidia-smi`, pokud
je dostupné, dodá název, celkovou i volnou vlastní VRAM. Nezjištěné hodnoty jsou
„Nelze zjistit“; WMI čítač omezený na 32 bitů se nepoužívá jako důkaz velikosti
VRAM. Doporučení je orientační. Kontext, kvantizace a vision část potřebují
další paměť; 8 GB VRAM s 32 GB RAM umožňuje zkusit 7B s případným CPU offloadem.

## Offline práce a systémová lišta

Editor, soubory, projekty, import/export, FFmpeg a nainstalované místní modely
nevyžadují internet. Hledání klipů, první stažení modelů, cloudové požadavky,
Edge TTS a kontrola aktualizací internet potřebují. Pro offline zvuk vyber Piper
nebo vypni voiceover. Stav sítě neznamená, že je dostupná každá jednotlivá služba.

V Obecném nastavení lze zvolit ukončení nebo skrytí při zavření, skrytí při
minimalizaci a na nainstalovaných Windows volitelný start po přihlášení.
Systémová lišta nabízí otevření, vybraný model, zastavení úloh/pozastavení
stahování, nastavení a skutečné ukončení. Ukončení flushne poslední změny,
zruší řízené úlohy a ukončí jen vlastní backend a vlastní Ollama. Sidecar sleduje
rodičovský proces a při jeho pádu zruší práci. Externí Ollama se neukončuje.

## Data, projekty a přechod z původní aplikace

Data jsou ve `%APPDATA%\Rank Studio`, mimo instalační adresář. Uvnitř `runtime`
zůstávají původní formáty médií, exportů a hlasů. Aktivní projekt, historie a
rozepsané zadání se ukládají průběžně v SQLite s transakcemi a verzí schématu.
Ruční kopie projektů jsou dostupné v **Nastavení → Úložiště**. Přepnutí nebo
import uloží původní stav jako samostatnou kopii. Novější neznámé schéma se
nepřepisuje. SQLite přenosy a konfigurace neobsahují skutečné API klíče.

1. V aktualizované původní webové aplikaci použij **Export projektu**. Archiv
   `.rankstudio` obsahuje stav, související média, rodičovské zdroje a undo klipy.
   Samotná historie ID nebalí všechna videa, která byla kdy stažená.
2. V desktopu klikni **Import projektu**. Kontrolují se cesty, velikosti,
   kolize, kontrolní součty a Windows rezervované názvy. Archiv neobsahuje klíče,
   `.env` ani přihlašovací cookies. Limit přenosu je 8 GB; použit je ZIP64.
3. Alternativně **Převzít média ze starého studia** zkopíruje média, předlohy
   a hlasy z vybrané původní složky. Originály zůstávají zachované. Tato operace
   sama nepřečte localStorage z Edge/Chrome; projekt a historii přenes archivem.

Instalátor, aktualizace i odinstalace ponechávají uživatelský adresář. Neodstraňuj
ho ručně, pokud chceš zachovat projekty a DPAPI úložiště. Přístupové klíče jsou
chráněné uživatelským Windows DPAPI; kopie vaultu není přenositelná pod jiný
Windows účet. Mimo Windows se při vývoji klíče drží pouze v paměti, bez
nechráněného ukládání na disk. UI toto omezení zobrazuje.

## Reprodukovatelné sestavení Windows x64

Na Windows 10/11 x64 nainstaluj Python 3.12 x64 a Node.js 24. Potom v kořeni:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r desktop/requirements-build.txt
.\.venv\Scripts\python.exe scripts/build_desktop.py
```

Skript ověří SHA-256 připnutého oficiálního FFmpeg archivu podle winget manifestu,
přibere Node pro yt-dlp, sestaví frontend a PyInstaller sidecar a přes
electron-builder vytvoří NSIS `.exe`. Node/Python se na cílovém PC samostatně
neinstalují. Modely AI se do instalátoru nepřidávají automaticky.

Výstup je v `release/windows`, včetně integrity souborů `SHA256SUMS.json`.
Build nepublikuje vydání. `.github/workflows/windows-desktop.yml` připravuje
stejný build na Windows runneru, regresní testy, skutečný Electron s přibaleným
backendem a test instalace/odinstalace na jednorázovém profilu. Artefakt se
jmenuje **Rank-Studio-Windows-x64**. [Stav Windows workflow](https://github.com/Mejkl0s/youtube-shorts/actions/workflows/windows-desktop.yml)
a hranice skutečně dokončeného ověření jsou v záznamu testů. Samotná přítomnost
workflow nepotvrzuje, že byl vytvořen použitelný instalátor.
Artefakty mají retenční dobu podle GitHub Actions. Pro trvalou produkční
distribuci zveřejni podepsané vydání podle postupu níže.

Vývojové spuštění po vytvoření `.venv` a instalaci Python závislostí výše:

```powershell
npm ci
npm --prefix desktop ci
npm run build
npm --prefix desktop start
```

Používá sestavený frontend a místní `.venv`, žádný Vite server. Na Linuxu lze
ověřit sidecar pomocí `scripts/build_desktop.py --backend-only --skip-install`;
tento výstup není Windows aplikace ani Windows instalátor.

## Produkční podpis a aktualizace

Před podepsaným buildem nastav mimo zdrojový kód:

- `CSC_LINK` / `CSC_KEY_PASSWORD`: vlastní code-signing certifikát a jeho heslo
  v zabezpečeném CI úložišti podle dokumentace electron-builderu.
- `RANK_PUBLISHER`: přesný očekávaný název podepisujícího vydavatele.
- `RANK_UPDATE_URL`: produkční HTTPS adresář pro manifest a artefakty.

Pak spusť `.\.venv\Scripts\python.exe scripts/build_desktop.py --signed`. Bez certifikátu/publishera tento
režim selže. Ověř Authenticode podpis vytvořeného `.exe` ve Windows a zveřejni
spolu `latest.yml`, instalátor a případný `.blockmap`. Samotný build nic neodešle.
Certifikát není součástí projektu ani instalátoru.

Update klient kontroluje manifest, SHA-512 souboru a platný Authenticode podpis
očekávaného publishera. Chybějící publisher nesmí vypnout podpisovou kontrolu:
verifier je navázaný na build policy uvnitř ASAR. Produkční fuses zakazují
`ELECTRON_RUN_AS_NODE`, Node options/inspect a načítání app kódu mimo ASAR;
zapnutá je integrita ASAR. Renderer nemá Node a jeho IPC je omezené na hlavní
okno aplikace. Lokální tokeny nejdou do URL, ambientního ani systémového proxy.

Bez důvěryhodné podpisové/distribuční konfigurace UI otevřeně hlásí, že
aktualizace nejsou nakonfigurované, a instalaci neumožní. Neexistuje zde zatím
produkční podepsaný feed; nelze tvrdit, že end-to-end aktualizace byly ověřeny.

## Ověření a zbývající nativní kontrola

Výsledky a přesné hranice ověření shrnuje [DESKTOP-VERIFICATION.md](DESKTOP-VERIFICATION.md).

- Backend testy ověřují adaptéry, loopback hranice, autentizaci, žádný paid
  fallback, model snapshots, ukládání, bezpečné archivy, stahování/stop/resume.
- Node testy ověřují IPC origin/frame, seznam povolených native operací,
  externí odkazy a soukromý HTTP transport včetně multipart přenosu.
- `scripts/desktop-electron-test.mjs` používá skutečný Electron, preload,
  sidecar, SQLite, FFmpeg a nativní souborové operace. AI server je lokální
  protokolová fixture. Test zahrnuje průvodce/hybrid, synchronizaci modelu,
  zachování probíhajícího požadavku, zrušení, simulovaný offline stav s funkčním
  loopbackem, skutečný MP4, projektový archiv, okamžité zavření a restart.
- Windows instalaci/upgrade/odinstalaci, DPAPI na Windows, nabídku Start,
  přihlášení, DPI více monitorů a skutečné signed update vydání je potřeba
  ověřit na Windows. CI obsahuje odpovídající build a instalační smoke test.
- Živé cloudové požadavky nebyly spuštěny bez soukromých klíčů. Síť zde blokuje
  Ollama/Hugging Face modelové zdroje; kvalita a rychlost 7B ani skutečná Piper
  inference se simulovaným přenosem neprokazují. TLS/digest ověřování zůstává
  zapnuté a částečné soubory nejsou prezentované jako nainstalované modely.

Před vydáním ověř na čistých Windows také render s nainstalovaným Piper,
stahování reálného Ollama modelu, DeepSeek s vlastním platným klíčem, odmítnutí
cizího podpisu aktualizace a zachování skutečných projektů/klíčů při upgrade.
