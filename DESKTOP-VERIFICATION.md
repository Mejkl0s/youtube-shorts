# Ověření desktopové verze

Záznam z 2. 11. 2026. Architektura je v [DESKTOP.md](DESKTOP.md), použití,
Windows build a podpisy v [DESKTOP-WINDOWS.md](DESKTOP-WINDOWS.md).

## Verze 2.0.1 — 7. 11. 2026

Nový postup a jeho limity jsou v [HIGHLIGHTS.md](HIGHLIGHTS.md). Lokálně prošla
celá tehdejší sada **330 Python testů**; po doplnění hraničních scénářů prošlo
**22 cílených testů nového výběru**, včetně skutečného MP4 s audiem. Samostatná
sada 132 testů ověřila související veřejné hledání a původní lokální/vizuální
postup. Frontend production build a pět bezpečnostních Node testů prošly.

Skutečně spuštěný Electron prošel průvodcem, přepínáním modelů, zrušením úlohy,
offline ovládáním, exportem MP4 do nového limitu, archivem, chybou ukládání,
obnovením projektu i systémovou lištou. Nový browser scénář prošel osmi
obsahově posouzenými zdroji ze všech tří sítí, skutečnými dvousekundovými
výřezy s audiem, uložením/obnovou limitu 25 s a rozsahu 100 odkazů. Na pěti
šířkách (1440, 1100, 900, 720, 390 px) nebylo horizontální přetékání.
Původní browser test vizuálního výběru také prošel. AI i sociální síť v těchto
scénářích jsou protokolové fixtures; přesnost živého modelu tím není měřena.

Nový Windows instalátor ověřuje následný CI běh; níže uvedený předchozí
Windows artefakt 2.0.0 sám neobsahuje změny 2.0.1.

## Implementované části

| Oblast | Implementace |
|---|---|
| Windows aplikace | Electron, NSIS, ikony, vlastní okno, přibalený PyInstaller backend a FFmpeg/Node; bez Vite/Renderu. |
| První spuštění | Pět kroků, lokální/cloudový/kombinovaný režim, více poskytovatelů, opakovatelné předvyplněné nastavení. |
| Přepínání | Společná konfigurace horní lišty a Nastavení, trvalá volba, vlastní snapshot pro běžící úlohu. |
| Cloud | OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter a vlastní kompatibilní endpoint; samostatné formáty přenosu. |
| Lokální AI | Ollama, LM Studio, llama.cpp a vlastní loopback API, skutečné modely z discovery, kontrola obrazové schopnosti. |
| Přístupové údaje | Windows DPAPI, samostatné úložiště podle poskytovatele a originu serveru, žádný plaintext fallback. |
| Offline práce | Lokální editor, projekty, média, export, instalované modely/Piper; označené síťové závislosti. |
| Modely a hardware | Oficiální Ollama pull/delete a Piper manifest, průběh, stop/resume, místo, potvrzení mazání, RAM/CPU/disk a dostupné údaje NVIDIA. |
| Systémová integrace | Tray, volitelný start po přihlášení, chování zavření, uložení poslední změny, ukončení vlastních procesů. |
| Data a aktualizace | SQLite, kopie projektů, bezpečný archiv s médii, nedestruktivní migrace; podpisový updater připravený, bez feedu vypnutý. |

Původní střih, vzhled, předlohy, klipy, zvuk, rozmazání/odstranění překryvů
a omezení finálního videa na nejvýše 40 sekund jsou zachované.

## Automatizované ověření

Základní příkazy z kořene projektu:

```bash
.venv/bin/python -m pytest -q
npm run build
npm --prefix desktop test
node scripts/visual-selection-browser-test.mjs
node scripts/compilation-browser-test.mjs
```

Poslední příkaz potřebuje testovací backend na `127.0.0.1:8000`.
Na Windows použij místo `.venv/bin/python` cestu `.venv\Scripts\python.exe`.

- Python na Linuxu: **313 testů prošlo** (242,93 s), s jedním upozorněním
  knihovny Starlette na testovací HTTP klient. Původní regresní sada a desktopové testy adaptérů, klíčů, hranic
  endpointů, streamů, autentizace, snapshotů, SQLite, archivů a modelů.
  Po úpravě Windows testovacího prostředí a kontroly původních ZIP názvů
  prošlo také všech 70 souvisejících cílených kontrol.
  Prošel i nový samostatný test opakované přípravy již připravených nástrojů.
- Node: 5 úspěšných kontrol IPC origin/frame, omezeného rozhraní, externích
  odkazů a přímého privátního HTTP/multipart transportu. Konfigurace balení
  prošla také validací schématu electron-builderu.
- Frontend: TypeScript a produkční Vite build prošly. Fonty z `/api/fonts/`
  se úmyslně načítají až z místního backendu.
- Vizuální browser test prošel se skutečným dekódováním a extrakcí snímků,
  proměnlivými střihy, zvukem, důkazy děje a kontrolou nezměněného projektu
  při odmítnutí výsledku. AI, hledání a stahování používají lokální fixtures.
- Kompilační browser test prošel se skutečným uploadem, OCR, pěti scénami,
  ruční maskou, odstraněním překryvu, uložením, obnovením, MP4 exportem,
  dávkovým čištěním a mobilním dialogem.

## Skutečný desktop a balení v Linuxovém prostředí

Sestaven byl skutečný PyInstaller sidecar a Electron Linux balíček, nikoli
Windows instalátor. Jejich velikosti jsou přibližně 651 MB a 927 MB včetně
rozbalených závislostí; nejsou to odhady velikosti Windows instalátoru.

`scripts/desktop-electron-test.mjs` prošel se skutečným Electronem a přibaleným
backendem. Ověřil izolovaný preload, autentizaci, průvodce, hybridní konfiguraci,
synchronizaci modelu, zachování rozpracovaného požadavku, zrušení, simulovaný
offline stav s funkčním loopbackem, skutečný MP4 se zvukem do 40 sekund,
nativní export/import projektu, SQLite a obnovení po restartu. Vynucená chyba
zápisu při importu zachovala původní projekt i následné automatické ukládání.
Modelové odpovědi pocházely z lokálního protokolového testovacího serveru.

Samostatně prošel start zabaleného produkčního programu s novým uživatelským
adresářem: ASAR main/preload, vlastní sidecar a vykreslený editor zapsaly stav
do SQLite. Po násilném ukončení rodiče skončil také jeho vlastní backend.
Obsah ASAR byl porovnán se zdroji a politika aktualizací uvnitř byla vypnutá.
Přibalený yt-dlp se spustil přes skutečný frozen CLI dispatch.

Linuxové GUI testy vyžadují virtuální X server. Používají testovací příznak
`--no-sandbox`, protože v tomto prostředí není dostupný systémový Chromium
sandbox. Tím se neprokazuje jeho ochrana na úrovni OS. Produkční nastavení
okna ponechává `sandbox`, `contextIsolation` a `webSecurity` zapnuté a Node
v rendereru vypnutý; Windows test tento příznak nepřidává.

## Windows CI

[Běh Windows desktop](https://github.com/Mejkl0s/youtube-shorts/actions/runs/41534137780)
používá Windows Server 2022 x64, Python 3.12 a Node.js 24.19.0. Přístup k REST API
je zde blokovaný, stav kroků je dostupný přes veřejnou stránku běhu.

| Kontrola | Doložený stav |
|---|---|
| Frontend a bezpečnostní Node testy | Prošly na Windows. |
| Celá Python regresní sada | Prošla na Windows; POSIX procesová kontrola je na Windows výslovně vynechaná. |
| PyInstaller backend a NSIS `.exe` | Sestaveny na Windows. |
| Celý Electron scénář s přibaleným Windows backendem | Prošel na Windows, včetně kompaktního okna, MP4 exportu, archivů, simulované chyby uložení, restartu a chování systémové lišty. |
| Instalace, spuštění, reinstalace, zachování dat, odinstalace | Prošly; ověřen Start menu zástupce, skutečné spuštění a SQLite stav, normální ukončení, zachování databáze i dalšího uživatelského souboru po reinstalaci a odinstalaci. |
| Zveřejnění instalačního artefaktu | Úspěšně nahrán `Rank-Studio-Windows-x64`, 341 MB. |

Celý běh skončil úspěšně pro zdrojový commit
`c78e8cd0368602d066c29d539c3cdba03f3f6a0c`. Úspěšná reinstalace stejné verze
není vydávána za test aktualizace ze skutečného podepsaného feedu.

[Instalační ZIP](https://github.com/Mejkl0s/youtube-shorts/actions/runs/41534137780/artifacts/13183257915)
vyžaduje přihlášení ke GitHubu. Uvnitř jsou instalátor a `SHA256SUMS.json`.
GitHubem zveřejněný SHA-256 **ZIP artefaktu**, nikoli samotného `.exe`, je
`e6328343bc5863cb7bcd63fcba3f1391619fc1542b8c40f1bb22cbba520d53df`.

Windows testy ověřují skutečné DPAPI se zkušebním klíčem. Lokální export prochází
i cestami s diakritikou. Testovací Python prostředí je `.venv`, stejně jako
v reprodukovatelném návodu. OCR závislost pro testy se stahuje z oficiálního
zdroje s kontrolou SHA-256. Windows se pro přístup k souborům řídí ACL; Linuxové
testy bitů `0600/0700` nejsou vydávané za kontrolu Windows ACL.

## Co zde ověřeno nebylo

- Fyzický Windows 10/11 počítač uživatele, restart Windows, start po přihlášení,
  různé monitory/DPI a oddělení souborů mezi dvěma reálnými Windows účty.
  Automatický běh Windows Server 2022 tyto ruční kontroly nenahrazuje.
- Živé cloudové volání včetně DeepSeek s platným soukromým klíčem.
  Testy protokolu nenahrazují ověření účtu, kreditu, konkrétního modelu a jeho
  výstupní kvality. Žádný placený požadavek nebyl kvůli ověření automaticky spuštěn.
- Stažení skutečných Ollama/Piper vah a rychlost/kvalita 7B na uživatelově GPU.
  Modelové registry/Hugging Face jsou zde blokované proxy. Kontrolní součty,
  TLS ani ochrana před neúplným stažením se kvůli tomu nevypínají.
- Produkční aktualizace: není dodaný certifikát ani podepsaný distribuční feed.
  Mechanismus vyžaduje SHA-512 a Windows Authenticode očekávaného vydavatele;
  do jejich nastavení zůstává neaktivní.

Reprodukovatelný Windows postup a potřebné produkční vstupy jsou popsány
v návodu. Tento záznam nepovažuje Linuxový balíček za důkaz ověřené distribuce
pro Windows.
