# Ultra Noir — vizuální identita 2.0.2

Téma je implementované ve stávajícím editoru, nativním nastavení, průvodci,
dialozích střihu/čištění, výběru písem, přihlášení ke zdrojům, importu/exportu,
upozorněních a spouštěcí obrazovce. Současné komponenty, jejich události,
API, projektový formát a zpracování videa zůstávají zachované.

## Společné proměnné

Jediným zdrojem barev rozhraní je [desktop/theme.css](theme.css).
Vite tento soubor zahrne do editoru; nativní spouštěcí obrazovka načítá tentýž
soubor z instalačního balíčku. Není potřeba internet ani externí webové písmo.

| Token | Hodnota | Použití |
|---|---|---|
| `--noir-black` | `#060607` | Pozadí, sidebar a inputy |
| `--noir-panel` | `#0E0D0C` | Karty a dialogy |
| `--noir-bronze` | `#473B2F` | Okraje a oddělovače |
| `--noir-gold` | `#927C5F` | Primární akce, aktivní prvky a ikony |

Text má světlé neutrální odstíny. Hover a výběr používají průhledné varianty
stejné zlaté; nevznikají další barevné akcenty. Video, uživatelské barevné
vzorníky a grafika výsledného Shortu zachovávají vlastní barvy projektu.
Nejsou přebarvené do tématu editoru a export se vizuálním redesignem nemění.

## Provedení

- Tmavý sidebar s jemnou zlatou značkou aktivní sekce, nový vektorový znak
  a odpovídající PNG/ICO pro Windows.
- Téměř černé karty, bronzové vlasové okraje, tlumená zlatá pro hlavní akce.
- Společné rozměry rohů, jemné slidery, přepínače, dropdowny a focus ring.
- Přechody ovládacích prvků 180 ms; příchod dialogu 200 ms.
  Režim omezeného pohybu zůstává respektovaný i na spouštěcí obrazovce.
- Žádné neonové výplně ani dekorativní glow; stíny jsou tmavé a střídmé.
- Původní rozložení a přizpůsobování oknu zůstává zachované.

## Ověření

Produkční sestavení frontendu a bezpečnostní Node testy prošly. Skutečně
spuštěný Electron ověřil nastavení, průvodce, modely, ukládání, restart,
archivy, systémovou lištu a skutečný MP4 export. Prošel také stávající browser
scénář důkladného hledání se skutečnými zdroji/FFmpeg výřezy a protokolovými
fixtures pro síť a AI; nejde o nové měření přesnosti modelu.

Prázdný editor při 1440 × 1000 px měl **přibližně 95 % velmi tmavých pixelů**
(maximální RGB složka nejvýše 32). Kontrast zlaté vůči panelu je **4,87 : 1**,
tmavého textu na zlatém tlačítku **5,08 : 1** a tlumeného textu vůči panelu
**7,78 : 1**. Editor nepřetékal na 1440, 1100, 900, 720 a 390 px.
Stejná paleta se ověřila i na samostatné spouštěcí obrazovce.

Starší obecný browser skript předpokládá nadpis a testovací konfiguraci z
původního editoru. Není uváděný jako úspěšné ověření této verze; použitý
udržovaný scénář je `scripts/highlights-browser-test.mjs` a nativní
`scripts/desktop-electron-test.mjs`.
