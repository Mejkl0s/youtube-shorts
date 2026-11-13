# Ověření desktopové verze

Záznam aktualizovaný 13. 11. 2026; první ověření proběhlo 2. 11. 2026. Architektura je v [DESKTOP.md](DESKTOP.md), použití,
Windows build a podpisy v [DESKTOP-WINDOWS.md](DESKTOP-WINDOWS.md).

## Verze 2.0.9 — širší TikTok a Instagram hledání, 13. 11. 2026

[Postup a dostupnost](desktop/SOCIAL-SEARCH.md). Každá síť dostává souběžný
dotaz se zachováním kontextu úlohy, zrušení a časového limitu. Dva veřejné
vyhledávače střídají další dotazy, video cesty a až tři stránky. Opakovaná
nebo prázdná stránka se dále nestránkuje. Chyba konkrétního dotazu zůstává
omezená na zdroj; skutečné blokování/rate limit zastavuje daný vyhledávač.
Instagram `/reel/`, `/reels/` a `/p/` se slučují podle ID. Prázdná síť
neomezuje dostupnou síť na jednu třetinu výběru. Dětské téma má příbuzné
výrazy při zachování kontroly tématu i akce. Dosavadní vizuální kontroly,
časové limity střihů, efekty a malé blur masky zůstávají zachované.

Lokálně prošlo 389 regresních testů, frontend build, pět Node kontrol
a browser scénář s viditelným výsledkem prázdného instagramového indexu,
požadavkem TikToku na relaci a otevřením správy relací. Osm nových kontrol
ověřuje skutečné RSS/HTML parsování přes HTTP transport fixtures, parametry
stránkování, souběh, kontext úlohy, historii a alternativní cesty.
Veřejné vyhledávače z tohoto vývojového prostředí vrací přes proxy HTTP 403;
živá úspěšnost TikTok/Instagram vyhledávání a stahování zde nebyla ověřena.
Nejde o záruku pěti dostupných videí ani obcházení přihlášení či CAPTCHA.

Windows běh [43434796783](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43434796783)
skončil úspěšně: kompletní regrese finálního zdroje, PyInstaller/NSIS,
přibalené OCR, skutečná desktopová aplikace, instalace, reinstalace a
odinstalace se zachováním dat. Modelové odpovědi v nativním scénáři jsou fixtures.
[Instalační ZIP 2.0.9](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43434796783/artifacts/14044007975) má 422 MB; GitHub vyžaduje přihlášení.
SHA-256 ZIPu: `81648399569bb05625d99c911dab05762bc17d9fe13ff0943cfa9bc26ff69d11`. Sestava zůstává nepodepsaná.

## Verze 2.0.8 — efekty podle konkrétního děje, 12. 11. 2026

[Popis režimu](desktop/SOUND-DIRECTOR.md). Vybraný obrazový model navrhuje
události s odpovídajícími typy zvuku a ověřuje je v detailních snímcích,
po nejvýše dvou kandidátech v požadavku. Typ a dějová role musí souhlasit,
čas musí být v ověřeném výřezu a nejisté události se odmítnou. Více než dva
různé efekty je možné při zachování pauz, omezení opakování a souběhu.
Příprava může vyústit do důrazu stejného okamžiku. Mix respektuje řeč i
výrazný původní zvuk; nulová hlasitost nevyvolává obrazové plánování.

U každého návrhu je typ, čas a konkrétní pozorování. Převod na vlastní plán
umožní změnu jednotlivých zvuků a jejich uložení. Ověřená mezipaměť rozlišuje
zdroj, výřez a poskytovatele/model; neobsahuje API klíč. Výpadek modelu vede
ke konzervativní variantě bez přepnutí poskytovatele a neblokuje export.

Lokálně prošlo 380 regresních kontrol před poslední kontrolou souběžné přípravy,
osm následných cílených kontrol, frontend build, pět Node testů a osm testů
aktualizace. Testy používají skutečné snímky, zvuk a MP4; modelové odpovědi
jsou protokolové fixtures, nikoli důkaz kvality konkrétního modelu. Nativní
scénář ověřil plán čtyř různých efektů, export a úpravu typu zachovanou v archivu
i po restartu. Původní browser scénář malých masek a časovaného audio exportu
nadále prošel. Úzké masky nebyly rozšiřovány.

Windows běh [43303319588](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43303319588)
skončil úspěšně: kompletní regrese finálního zdroje, PyInstaller/NSIS, přibalené
OCR a nativní aplikace, instalace, reinstalace a odinstalace se zachováním dat.
[Instalační ZIP 2.0.8](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43303319588/artifacts/13983342487) má 422 MB; GitHub vyžaduje přihlášení.
SHA-256 ZIPu: `cc0d27e381e9e4da03de117be57953c1237747d72bedb5bd14a145edf5535551`. Sestava zůstává nepodepsaná.

## Verze 2.0.7 — přesné masky a časované efekty, 12. 11. 2026

[Pravidla a použití](desktop/PRECISE-EDITING.md). OCR odděluje základní linie
slov, emoji má samostatné malé oblasti a slučování nesmí vytvářet vysoké pásy.
Automatická maska má nejvýše 4 % plochy a 7,5 % výšky, celkem 8,5 % rámu.
Stejný filtr vyřazuje velké staré masky v náhledu i exportu. Velká ruční oblast
vyžaduje výslovné nastavení; staré zdrojové soubory ani masky se samy nemažou.

Efekty mají nejvýše dva krátké zvuky na klip, přednostně u akce z obrazového
posouzení s přepočtem původních časů. Samotný pohybový odhad dovolí jen jemný
přechod. Výrazný původní zvuk a voiceover mají přednost. Ruční čas a vypnutí
jsou uložené u klipu. Hotový náhled obsahuje skutečný přehled použitých časů.
Při nejasném ději může zůstat jen původní zvuk; není slibována sledovanost.

Lokálně prošla celá sada 373 kontrol, 14 následných cílených kontrol masek a
efektů, frontend build, pět Node bezpečnostních testů a osm testů aktualizace.
Skutečné MP4 ověřuje pozdní SFX, ticho před událostí, ztišení pod hlasem,
zachování délky i vynechání širokých starých masek. Browser ověřil starý pruh,
malé OCR masky, ruční čas, přehled efektů a skutečný audio export. Nativní
aplikace ověřila OCR, MP4, archiv a uložený čas po restartu. Obrazová AI/TTS
v odpovídajících scénářích jsou fixtures, nikoli měření kvality skutečného modelu.

Windows běh [43286082948](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43286082948)
skončil úspěšně: kompletní regrese finálního zdroje, PyInstaller/NSIS, přibalené
OCR a nativní aplikace, instalace, reinstalace a odinstalace se zachováním dat.
[Instalační ZIP 2.0.7](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43286082948/artifacts/13976256832) má 422 MB; GitHub vyžaduje přihlášení.
SHA-256 ZIPu: `bb04746ccef4c4bb31d75d7c94b0a2605d46173aecd5a7e1e976cb60daffc39f`. Sestava zůstává nepodepsaná.

## Verze 2.0.6 — celé názvy a emoji, 11. 11. 2026

[Podrobnosti čištění](desktop/COMPLETE-BLUR.md). OCR kombinuje oba režimy,
ponechává slabší slova a interpunkci ve spolehlivě ukotveném řádku, spojuje jeho
části a přidává okraje pro stíny/kontury. Navazující světlé/barevné emoji se
rozšiřují podle geometrie a časové stálosti. Vizuální AI podporuje samostatný
typ emoji a krátkodobé překryvy. Silnější rozmazání je omezené na vybrané
oblasti; vlastní nadpis a pořadí se vykreslují až poté. Ruční okraje lze zvětšit.

Windows balíček obsahuje Tesseract 5.4.0 s DLL, jazykovými daty, dostupnými
licenčními soubory a manifestem. Zdroj pochází z checksumem ověřeného OCR
instalátoru. Backend nastaví vlastní program i jazyky před systémovým OCR.

Lokálně prošlo 364 regresních kontrol před posledním rozšířením světlých
symbolů, šest následných cílených kontrol, frontend build, pět Node testů a
osm testů aktualizace. Skutečné OCR a MP4 ověřují celý titul i dvě emoji,
lokální rozmazání a ostré vlastní nadpisy. Browser ověřil detekci, zvětšení
masky, uložení a export bez AI. Nativní aplikace ověřila stejné reálné OCR,
uložení projektu a MP4. Obsahový model emoji je v jednotkové kontrole fixture;
nejde o záruku rozpoznání každého překryvu ve všech snímcích.

Windows běh [43039110590](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43039110590)
skončil úspěšně: kompletní regrese finálního zdroje, přibalení a spuštění OCR,
PyInstaller/NSIS, nativní aplikace a instalační/reinstalační scénář se zachováním
dat. Nativní test úmyslně nastavil neplatné vnější TESSDATA_PREFIX a provedl
skutečné OCR celého názvu i emoji přibaleným nástrojem.
[Instalační ZIP 2.0.6](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43039110590/artifacts/13863974742) má 422 MB; GitHub vyžaduje přihlášení.
SHA-256 ZIPu: `2e4825552f8e1d360437d17b029cff028922070e68e560bdccd34a87dc87b1de`. Sestava zůstává nepodepsaná.

## Verze 2.0.5 — hlas u krátkých klipů, 10. 11. 2026

[Podrobnosti časování](desktop/VOICE-TIMING.md). Výpočet používá řeč po odstranění
okrajového ticha, zachová vnitřní pauzy a zmenší úvodní odklad před případným
zrychlením nejvýše 1,25×. Krátký střih může použít jednoznačný kratší ekvivalent
uvedení pořadí, včetně staršího uloženého standardního textu bez příznaku režimu.
Použitou krátkou variantu oznámí u hotové úlohy. Vlastní komentář se bez původního
výslovného povolení k úpravě nepřepisuje. Obraz a délky střihů zůstávají stejné.

Lokálně prošlo 19 cílených Python kontrol hlasu a dosavadního zkrácení asistenta,
dvě následné kontroly staršího uloženého uvedení pořadí v angličtině/češtině,
frontend build, pět Node bezpečnostních testů a osm testů lokální aktualizace.
Browser skutečně vytvořil zvukový náhled MP4 s pěti klipy včetně jednosekundové
#4, slyšitelným hlasem i efekty a původní délkou 10,3 s. Bylo ověřeno i oznámení
kratšího uvedení pořadí. Zdroj syntézy v těchto scénářích je protokolová fixture,
ne ověření dostupnosti Microsoft Edge u uživatele nebo kvality skutečného hlasu.

Windows běh [42719087748](https://github.com/Mejkl0s/youtube-shorts/actions/runs/42719087748)
skončil úspěšně: kompletní regrese finálního zdroje, PyInstaller/NSIS, skutečná
přibalená aplikace, instalace, spuštění, reinstalace a odinstalace se zachováním dat.
[Instalační ZIP 2.0.5](https://github.com/Mejkl0s/youtube-shorts/actions/runs/42719087748/artifacts/13719748204) má 341 MB; GitHub vyžaduje přihlášení.
SHA-256 ZIPu: `f9e3cee5968eb23b8980ac930c56b6eab355a738ff3e07cc5389e48b43b4bf4b`. Sestava zůstává nepodepsaná.

## Verze 2.0.4 — zvuk klipů, barvy a poznámky, 9. 11. 2026

[Postup a přesná omezení](desktop/EDITOR-POLISH.md). Editor využívá šířku okna,
každé pořadové číslo může mít vlastní barvu a poznámky přicházejí při začátku
svého klipu a zůstávají ve sloupci. Náhodné fráze se již nedoplňují. Výslovná
úloha poznámek kontroluje snímky aktuálních výřezů uloženým vizuálním modelem;
nejasná nebo obecná odpověď zachová původní text. Změna střihu zneplatní jeho
automatickou poznámku. Přiřazení běžící odpovědi kontroluje také časy výřezu.

Koncový zvuk lze automaticky zjemnit, ponechat nebo poslední půlsekundu
ztlumit. Automatika rozpoznává prudký skok amplitudy, nikoli význam zvuku;
souvislý hlasitý děj ponechá. Obraz, délka klipu a jiné zvukové stopy se nemění.

Lokálně prošla kompletní sada 348 kontrol před posledním doplněním a všech
10 následných cílených kontrol poznámek/zvuku, frontend build a pět Node
bezpečnostních testů. Skutečné MP4 ověřuje odkrývání/animaci/přetrvání poznámek,
individuální barvu a všechny tři volby zvuku bez zkrácení obrazu. Browser
prošel sedm šířek 390–2560 px, skutečné krátké výřezy, nový job poznámek,
uložení nastavení a zneplatnění poznámky po změně střihu. Nativní Electron
ověřil poznámky každého klipu, barvy, MP4/archiv projektu a restart. Síť a AI
v automatizovaných scénářích jsou protokolové fixtures, nikoli hodnocení
přesnosti modelu nebo živých veřejných zdrojů.

Windows běh [42710179673](https://github.com/Mejkl0s/youtube-shorts/actions/runs/42710179673)
skončil úspěšně: kompletní regrese finálního zdroje, PyInstaller/NSIS, skutečná
přibalená aplikace, instalace, spuštění, reinstalace a odinstalace se zachováním dat.
[Instalační ZIP 2.0.4](https://github.com/Mejkl0s/youtube-shorts/actions/runs/42710179673/artifacts/13715793915) má 341 MB; GitHub vyžaduje přihlášení.
SHA-256 ZIPu: `20963b0997d8b66ed4b38ed8d5fb20a7ab54618a751bfc40982e56b3a467ae58`. Sestava zůstává nepodepsaná.

## Verze 2.0.3 — uložené nastavení AI, 8. 11. 2026

[Popis postupu](desktop/AI-SETUP.md). Uložený režim/model je v kartě před
hledáním a zůstává měnitelný v Nastavení. Hledání neotevírá dialog kvůli
starému klientskému `/health`; backend ověří aktuální uloženou volbu.
Kombinovaný režim zachová platný vybraný model. Průvodce kontroluje podporu
obrázků před dokončením, nebo výslovně uloží technický výběr bez obrazové AI.

Lokálně prošlo 60 Python kontrol desktopu, pět bezpečnostních Node testů,
frontend build a browser scénář skutečného střihu. Skutečný Electron ověřil
opakované hledání při záměrně neaktuálním `/health`, uloženou volbu po restartu,
chybový stav bez přesměrování do Nastavení, počáteční kontrolu textového modelu
a uložené přeskočení obrazové AI. Prošel i původní MP4/export/archive/tray scénář.
Síť/AI jsou v automatizovaných scénářích protokolové fixtures.

Windows běh [42483492682](https://github.com/Mejkl0s/youtube-shorts/actions/runs/42483492682)
skončil úspěšně: kompletní regrese, PyInstaller/NSIS, přibalená aplikace,
instalace, spuštění, reinstalace a odinstalace se zachováním dat.
[Instalační ZIP 2.0.3](https://github.com/Mejkl0s/youtube-shorts/actions/runs/42483492682/artifacts/13619141185) má 341 MB; GitHub vyžaduje přihlášení.
SHA-256 ZIPu: `415e1cab7152f4175bbc33f8f9c881eb970c9a1c98d8e955ef5b5beff0094192`. Sestava zůstává nepodepsaná.

## Verze 2.0.2 Ultra Noir — 8. 11. 2026

Vizuální implementace a centrální tokeny jsou popsané v
[desktop/ULTRA-NOIR.md](desktop/ULTRA-NOIR.md). Backend, API, projektový formát
ani algoritmy hledání, střihu a exportu se proti 2.0.1 nezměnily.

Prošel frontend production build, pět Node bezpečnostních kontrol, udržovaný
browser scénář hledání/střihu a skutečný Electron včetně průvodce, modelů,
nových checkboxů, klávesnice, MP4 exportu, uložení, archivů a restartu.
Rozhraní nepřetékalo na pěti šířkách; prázdný editor měl přibližně 95 % velmi
tmavých ploch. Barvy projektu ve videu zůstávají zachované.

Windows běh [42434685221](https://github.com/Mejkl0s/youtube-shorts/actions/runs/42434685221)
skončil úspěšně: regresní sada, PyInstaller/NSIS, přibalená Windows aplikace,
instalace, spuštění, reinstalace a odinstalace se zachováním dat.
[Instalační ZIP 2.0.2](https://github.com/Mejkl0s/youtube-shorts/actions/runs/42434685221/artifacts/13598817445) má 341 MB; GitHub vyžaduje přihlášení.
SHA-256 ZIPu: `8700ffd35570554e111d3d456c2902cf7d12502d919e7c55d05ccb1ec572ca87`. Sestava je nepodepsaná; automatický podepsaný feed
zůstává neaktivní.

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

Samostatná kontrola skutečného Electronu navíc obnovila původní projekt
bez nových polí: všech pět šestisekundových klipů a původní limit 40 s
zůstaly zachované, export nebyl zablokovaný. Nové hledání používalo důkladný
rozsah a 100 odkazů. Při živém veřejném hledání dne 7. 11. 2026 vrátily
Bing, DuckDuckGo i YouTube v tomto prostředí HTTP 403; nebyl nalezen žádný
odkaz. Tato kontrola tedy nepotvrzuje dostupnost sítí z uživatelova PC.
Aplikace odděleně hlásí chybějící odkazy, neúspěšné stahování a nedostatek
obsahově přijatých momentů.

Finální Windows běh [42324120976](https://github.com/Mejkl0s/youtube-shorts/actions/runs/42324120976)
skončil úspěšně. Prošla celá regresní sada, sestavení PyInstaller/NSIS,
spuštění přibalené aplikace i instalační/reinstalační/odinstalační kontroly.
V repozitáři je 338 Python scénářů; POSIX kontrola práv se na Windows vynechává.
Další skutečný export dosáhl přesně **25,0 s včetně audia**, bez překročení
limitu; desetisekundový výběr se nenatahoval. Kontrola z klávesnice ověřila
přirozené zadání 40 a 25 sekund. Nativní okno nemělo horizontální přetékání
na 900/1100/1440 px a náhled zůstával pod skutečnou výškou horní lišty.

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

## Původní balení 2.0.0 v Linuxovém prostředí

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

[Běh Windows desktop](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43434796783)
používá Windows Server 2022 x64, Python 3.12 a Node.js 24.19.0. Přístup k REST API
je zde blokovaný, stav kroků je dostupný přes veřejnou stránku běhu.

| Kontrola | Doložený stav |
|---|---|
| Frontend a bezpečnostní Node testy | Prošly na Windows. |
| Celá Python regresní sada | Prošla na Windows; POSIX procesová kontrola je na Windows výslovně vynechaná. |
| PyInstaller backend a NSIS `.exe` | Sestaveny na Windows. |
| Celý Electron scénář s přibaleným Windows backendem | Prošel na Windows, včetně kompaktního okna, MP4 exportu, archivů, simulované chyby uložení, restartu a chování systémové lišty. |
| Instalace, spuštění, reinstalace, zachování dat, odinstalace | Prošly; ověřen Start menu zástupce, skutečné spuštění a SQLite stav, normální ukončení, zachování databáze i dalšího uživatelského souboru po reinstalaci a odinstalaci. |
| Zveřejnění instalačního artefaktu | Úspěšně nahrán `Rank-Studio-Windows-x64`, 422 MB. |

Celý běh skončil úspěšně pro zdrojový commit
`7ad91e1736e783275a5be6a9a0849414a229d370`. Úspěšná reinstalace stejné verze
není vydávána za test aktualizace ze skutečného podepsaného feedu.

[Instalační ZIP](https://github.com/Mejkl0s/youtube-shorts/actions/runs/43434796783/artifacts/14044007975)
vyžaduje přihlášení ke GitHubu. Uvnitř jsou instalátor a `SHA256SUMS.json`.
GitHubem zveřejněný SHA-256 **ZIP artefaktu**, nikoli samotného `.exe`, je
`81648399569bb05625d99c911dab05762bc17d9fe13ff0943cfa9bc26ff69d11`.

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
