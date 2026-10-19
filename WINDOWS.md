# Rank Studio na Windows

1. Stáhni [celý ZIP aplikace](https://github.com/Mejkl0s/youtube-shorts/archive/refs/heads/main.zip).
2. Klikni na ZIP pravým tlačítkem → **Extrahovat vše**. Otevři rozbalenou složku.
3. Dvakrát klikni na **SPUSTIT-WINDOWS.bat**. Soubor spouštěj z rozbalené složky, nikoli uvnitř ZIPu.
4. Při prvním spuštění se připraví potřebné nástroje a aplikace. Instalace může trvat několik minut a instalátor nástrojů může vyžadovat potvrzení Windows.
5. Studio se otevře v běžném prohlížeči. Poznáš ho podle textu **Běží na tvém PC**. Okno spouštěče nech otevřené; pro ukončení stiskni **Ctrl+C**.
6. Zadej **winter fails** a klikni **Najít klipy**. Dostupnost skutečných klipů musí ověřit tento pokus na tvém připojení; lokální spuštění ji samo nezaručuje.

Pro další použití stačí znovu otevřít `SPUSTIT-WINDOWS.bat`. Render teď pro lokální studio nepotřebuješ. Pokud se prohlížeč sám neotevře, spouštěč vypíše lokální adresu, kterou můžeš zadat ručně. Toto studio je přístupné jen na tvém počítači.

## Co se instaluje

Spouštěč je určen pro **Windows 10/11 x64** s Windows PowerShell 5.1 nebo novějším a `winget`. Chybějící nástroje instaluje přes oficiální katalog `winget`, který ověřuje balíčky. Nepoužívá vypnutí ověřování TLS ani neověřené instalátory.

- **Python 3.12 x64** (`Python.Python.3.12`). Závislosti studia se instalují do jeho vlastní složky `.venv`.
- **Node.js LTS**, alespoň verze 24 (`OpenJS.NodeJS.LTS`). Slouží k sestavení webu a podporovanému získávání YouTube videí.
- **FFmpeg a ffprobe** (`Gyan.FFmpeg`). Slouží k videu, zvuku a exportu.
- Volitelně **Tesseract OCR** (`UB-Mannheim.TesseractOCR`) pro bezplatné rozpoznání předlohy. Když jeho instalace selže, studio lze používat a vzhled nastavit ručně.

Pokud chybí `winget`, nainstaluj nebo aktualizuj [App Installer od Microsoftu](https://apps.microsoft.com/detail/9nblggh4nns1), zavři okno a spusť studio znovu. Při chybě instalace se spouštěč zastaví a nechá výsledek viditelný. Nástroje lze také nainstalovat předem ručně z jejich oficiálních distribucí; musí být dostupné v `PATH`.

Písma DejaVu a jejich licence jsou přibalené v `backend/fonts`, takže Windows a Render používají stejná písma. Export počítá s mezerami, diakritikou i běžnými speciálními znaky v cestách. Windows nepotřebuje linuxový `uvloop`; použije standardní smyčku Pythonu.

## Klipy, přihlášení a hlas

- Nahraná videa, relace a exporty zůstávají ve složce `.runtime` uvnitř rozbalené aplikace. Při běžném zavření programu se nemažou. Smazáním složky nebo spuštěním jiné rozbalené kopie se k těmto souborům nedostaneš.
- Projekty a relace z Renderu se automaticky nepřenesou. Pro import vlastní relace použij ve zdejším studiu **Přihlášení ke zdrojům → Nahrát cookies.txt**. Soubor ani heslo neposílej do chatu. Na Windows se ochrana uložených souborů řídí oprávněními tvé uživatelské složky.
- Aplikace sama nečte databázi cookies Edge/Chrome. Samotné přihlášení na síti v jiném panelu neposkytne studiu přístup k účtu.
- Free režim hledání nepotřebuje OpenAI ani ElevenLabs. Hlas **Andrew / Antonín · zdarma bez klíče** je online služba: přehrání i dostupnost je potřeba ověřit tlačítkem ukázky hlasu. Krátký komentář můžeš napsat ručně.
- Lokální IP může situaci zlepšit, ale TikTok, Instagram, YouTube i veřejné vyhledávače mohou dál odmítnout požadavek. Studio nepřekonává přihlašovací výzvy a nevymýšlí náhradní klipy. Když získá jen část videí, nechá je v editoru a další místa lze doplnit vlastními soubory.
- Volitelné API klíče lze nastavit do vlastní `.env` podle `.env.example`. Jsou potřeba jen pro zvolené placené AI funkce. Lokální spouštěč zachová případné `STUDIO_PASSWORD` pro přihlášení, ale nevystavuje studio veřejné síti.

## Když se něco nespustí

Spusť **OVERIT-WINDOWS.bat**. Připraví stejné závislosti a provede skutečný krátký test MP4, H.264/AAC, popisků, fontů a cest s diakritikou. Ohlásí také dostupnost Tesseractu a klienta bezplatného hlasu. Tento test neověřuje dostupnost sociálních sítí ani kvalitu online hlasu.

Pokud spouštěč hlásí obsazený port, zavři předchozí okno studia. Nezastavuje cizí procesy. Pokročile lze z příkazového řádku použít `.venv\Scripts\python.exe scripts\local_studio.py --port 8766`.

Soubory `.env`, `.runtime` a `.venv` nepřidávej do veřejného ZIPu ani do GitHubu. Pro aktualizaci používej novou kopii aplikace; případný přenos vlastních projektů, médií a relací dělej pouze lokálně.

## Rozsah ověření

Cloudové kontroly mohou ověřit společný Python spouštěč, skutečné vytvoření MP4 a webový editor na Linuxu. Nejsou potvrzením běhu instalátoru `winget` nebo přístupu k TikToku na tvém Windows PC. Tyto dva kroky se ověří až spuštěním u tebe. Spouštěč rozlišuje úspěšné sestavení aplikace od skutečné dostupnosti klipů.
