# Důkladné hledání a krátké hlavní momenty (2.0.1)

Nový desktopový projekt používá **Důkladně · vizuální AI**, 100 kandidátních
odkazů a nejvýše **25 sekund** pro celý nový výběr. Kratší výsledek se
nenatahuje; jednotlivý moment má obvykle 2–5 sekund a nejvýše 8 sekund.
Delší událost se nepřeruší jen kvůli limitu: dostane přednost jiná celá událost.
Uložené projekty bez nového pole limitu zůstávají na 40 sekundách. Přepínač
**Rychle** zachovává původní postup; veřejné API má tento režim stále výchozí.

V editoru napiš téma, vyber vizuální model, ponech důkladný rozsah a klikni
na **Najít klipy**. Pod hledáním se průběžně ukazují skutečné počty odkazů,
načtených a posouzených videí zvlášť pro TikTok, Instagram a YouTube.
Nejvýše 100 odkazů neznamená 100 stažených videí. Cílem je nejvýše 24 dostupných
zdrojů, vyváženě napříč zapnutými sítěmi. Důkladná úloha má limit 30 minut
a tlačítko zastavení. Původní klipy lze vrátit samostatným tlačítkem.

## Jak funguje výběr

1. Současně běží hledání veřejných indexovaných stránek (Bing/DuckDuckGo)
   a přímé veřejné hledání YouTube přes yt-dlp. YouTube tedy nečeká na selhání
   prvních pěti sociálních klipů. Vypnutý YouTube se nevolá.
2. Odkazy se sjednotí podle kanonické identity a střídají mezi sítěmi. Zohlední
   se historie použitých odkazů a hash již použitých souborů. Nedostupný,
   soukromý či blokovaný zdroj se zaznamená. Po dvou omezeních jedné sítě
   se její další stahování v této úloze pozastaví; ostatní pokračují.
3. Každé načtené video dostane samostatné obsahové posouzení. Celý zdroj
   projde levným RGB/motion skenem (3 snímky/s, 96×54), který navrhuje
   aktivity podle lokalizované změny obrazu a barevného histogramu. Malý
   posun kamery se kompenzuje. Barevná změna ani pohyb nejsou důkazem pointy.
4. Vizuální model dostane chronologický přehled celého zdroje a snímky okolí
   několika různých špiček aktivity. Nominuje jediný hlavní moment, nebo žádný.
   Fyzické hranice záběrů se zachovají i v kompilaci s více než 24 scénami.
   Pro omezení kontextu se do promptu přidávají jen hranice viditelných záběrů.
5. Okolí nominované akce se čte hustěji (až přibližně 8 snímků/s), s ověřenými
   časovými značkami dekódovaných snímků. Přijetí vyžaduje téma, úplnost,
   jistotu alespoň 0,8, skóre alespoň 60/100 a konkrétní obrazový důkaz
   přípravy, akce a výsledku v tomto pořadí. Střih zůstává uvnitř záběru
   a vizuálně zkontrolovaného intervalu.
6. Až po posouzení celé načtené sady se vybírá pět celých událostí pod limitem.
   Srovnatelná kvalita upřednostní kratší moment; algoritmus nikdy neodřízne
   závěr události ani nevyplní zbývající čas čekáním.
7. Vybrané výřezy se skutečně vytvoří FFmpegem včetně původního audia.
   Další AI kontrola čte **tyto hotové soubory**, ověřuje viditelnou akci a
   výsledek a odmítnutý klip nahrazuje dalším kandidátem. Společné porovnání
   hotových výřezů navíc hledá opakované incidenty/reposty. Nejistá sada se
   neoznačí za úspěšný kompletní žebříček.
8. Zapnuté čištění překryvů použije existující nástroje; skutečný render znovu
   vynucuje limit uložený v projektu a kontroluje výslednou délku MP4.

## Co je potřeba a co nelze slíbit

Důkladný režim vyžaduje ověřený vizuální model z horní lišty/Nastavení.
Lokální model neposílá snímky do cloudu. Výslovně vybraný cloudový poskytovatel
obdrží snímky a může účtovat více požadavků než rychlý režim; během úlohy
se používá stejný snapshot připojení a modelu. Není žádný automatický placený
fallback. Technický režim bez modelu zůstává dostupný pod **Rychle**.

TikTok a Instagram neposkytují této aplikaci neomezené interní vyhledávání:
veřejný index může vrátit málo výsledků a síť může požadovat přihlášení nebo
omezit stahování. Volitelné uložené relace se spravují dosavadním způsobem;
captcha ani soukromí se neobchází.

AI posuzuje vzorkované obrázky, nikoli nepřerušované přehrávání ani původní
zvuk. Může přehlédnout rychlý detail nebo chybně posoudit událost/repost.
Analýza řeči/zvuku zde nepřibyla. Kratší limit ani více kandidátů nezaručují
bezchybný výběr. Hotové video před zveřejněním přehraj. Při nedostatku
ověřených momentů aplikace zachová dostupné zdroje a částečný výběr a uvede,
že úloha nebyla dokončena.

## Ověření

`tests/test_highlights.py` pokrývá souběžné hledání a přenos rozpočtu/zrušení,
vyvážení sítí, 24 načtených kandidátů bez předčasného konce, omezení jedné
sítě, zachování částečné práce, RGB/pohyb, pozdní událost ve skutečném videu,
hustší vzorky, neplatné odpovědi, náhrady odmítnutých a opakovaných výřezů,
starý limit 40 s, nový limit 25 s a skutečný krátký MP4 s audiem bez natahování.
`scripts/highlights-browser-test.mjs` ověřuje celé rozhraní nad skutečným
backendem, skutečnými soubory, uložením/obnovou limitu a pěti šířkami okna.
AI a síťové hledání v těchto scénářích používají protokolové fixtures;
nejde o benchmark přesnosti konkrétního modelu nebo živých sociálních sítí.
