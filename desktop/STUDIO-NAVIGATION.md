# Přehledné studio — 2.0.10

Levé menu rozděluje práci do šesti záložek. Na ploše se zobrazuje obsah
jedné záložky, náhled a export zůstávají vpravo.

| Záložka | Co v ní najdeš |
|---|---|
| Hledání | Téma, Najít klipy, výsledky jednotlivých sítí a přihlášení ke zdrojům. |
| Klipy | Pořadí, střih, poznámky, rozmazání a časování efektů každého klipu. |
| Vzhled | Nadpis, písmo, barvy čísel, animace poznámek a vlastní předloha. |
| Zvuk | Hlas, zapnutí efektů, hlasitosti a rozbalovací tempo/projev hlasu. |
| Projekt | Uložení, import a export archivu projektu. |
| AI | Uložený výběr modelu a textový pomocník; ve webové verzi lokální AI. |

**Nastavení hledání** rozbalí režim, rozsah, počet kandidátů, zdroje a
přepínače automatických úprav. **Jak hledání funguje** obsahuje delší
vysvětlení. Informace o použití placeného cloudu zůstává přímo u hledání,
pokud je cloud vybraný. Stav úlohy a chyby jsou viditelné napříč záložkami.
Další hromadné úpravy klipů jsou pod **Další úpravy klipů**.

Přepnutí záložky nemaže rozepsané hodnoty, nepřerušuje hledání/export ani
nemění model. Panely zůstávají připojené, neaktivní jsou skryté. Uložení,
archiv a obnovení po restartu používají dosavadní stav projektu. Po otevření
aplikace se zobrazuje Hledání. Horní volba modelu i úvodní průvodce zůstávají
dostupné; „Najít klipy“ kvůli změně rozložení neotevírá Nastavení.

Menu lze ovládat šipkami, Home a End. Neaktivní panely nejsou v běžném
tabulátorovém pořadí. V menším okně se levé menu zúží na ikony s popisky;
na velmi úzké obrazovce jsou krátké záložky nahoře. Rozložení zachovává
Ultra Noir paletu a respektuje omezení animací v systému.

Browser scénář ověřuje každou záložku při šířkách 400, 600, 900, 1100 a
1440 px, zachování hodnot, klávesnici, skutečný MP4 export při přepínání
a obnovení uloženého projektu. Nativní Electron scénář používá stejné
menu pro modely, klipy, barvy, efekty a přenos projektu přes archiv.
Vyhledávací API a střihová/zvuková logika nebyly změněné.
