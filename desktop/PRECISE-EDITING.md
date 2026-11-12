# Přesné masky a časované efekty — 2.0.7

## Rozmazání pouze kolem textu

Původní slučování dovolovalo spojit překrývající se OCR oblasti do velkých
pruhů; limit 35 % obrazu byl příliš velký pro čištění nápisů. Nová detekce
rozděluje chybně spojené OCR řádky podle skutečné výšky a základní linie slov.
Slučuje pouze podobně vysoké řádky na stejném místě. Emoji dostávají vlastní
malé oblasti, místo aby zvyšovaly nebo prodlužovaly textový pruh.

Automatická maska má nejvýše 7,5 % výšky, 90 % šířky a 4 % plochy rámu;
celkový limit je 8,5 % rámu a osm oblastí. Používají se malé okraje pro obrys
písmen. Velké černé bloky/pozadí se automaticky nemaskují. Nejasný velký nález
se vynechá; detektor nevyplňuje rozpočet libovolnými oblastmi.

Stejná pravidla filtrují náhled i export včetně starších uložených masek.
Editor upozorní na vynechané oblasti a nabízí **Odebrat přerostlé masky** nebo
**Přepočítat malé masky**. Vlastní široká ruční maska je možná jen po zaškrtnutí
**Výslovně povolit velkou ruční oblast** u příslušné oblasti. Zdrojová videa ani
uložené oblasti se bez uživatelského kroku nemažou.

## Zvuk podle momentu

Efekty už nevznikají automaticky v čase nula každého klipu. Každý střih má
samostatný plán s nejvýše dvěma krátkými zvuky:

- **Podle hlavního momentu:** přednost má čas akce z dostupného obrazového
  posouzení, přepočítaný z původního zdroje do aktuálního výřezu. Bez něj se
  hledá pouze výrazná lokální změna pohybu. Celoplošné záblesky, změny většiny
  obrazu a souvislý pohyb nejsou důvodem k automatickému úderu.
- **Vlastní čas momentu:** nastav sekundy nebo použij aktuální čas malého
  náhledu. Volba se ukládá s klipem a projektem.
- **Bez přidaných efektů:** vypne efekty jen u daného klipu. Celkový přepínač
  Zvukové efekty má nadále přednost pro celý projekt.

Obrazově posouzený nebo ručně určený moment může dostat jemný důraz a krátký
přechod těsně před akcí. Samotný pohybový odhad dostane pouze jemný přechod.
U #1 může při oddělené viditelné pointě zaznít krátký závěrečný tón. Nejde o
odhad konkrétního zvuku z obrázku: automatika nevymýšlí dialog ani smích.

Výrazný původní zvuk dostává přednost před dalším úderem; rozhodnutí respektuje
i zvolenou hlasitost původní stopy. Efekty se hladce ztiší pod voiceoverem.
Zvuky mají krátké náběhy a dozvuky, vejdou se do střihu a nepřidávají náraz na
jeho konec. Při chybějícím jasném momentu může zůstat pouze původní zvuk.
Hlasitosti a celková délka videa se kvůli plánu automaticky nezvyšují.

Po vytvoření výsledného náhledu otevři **Časování efektů**. Ukazuje skutečně
použité časy, typy a důvod volby pro každý klip. Malý zdrojový přehrávač nadále
hraje původní zvuk; nový mix je v hotovém náhledu a MP4.

Pohyb je technický odhad, nikoli porozumění pointě. Pro důležitou scénu je
nejpřesnější obrazové posouzení nebo ruční potvrzení času. Žádný střihový plán
nezaručuje sledovanost; jde o odstranění rušivých náhodných efektů a jasné
zvýraznění relevantních momentů.

## Ověření

Regrese používá uložené velké pruhy, vadné OCR baselines a příliš velké
odpovědi AI: nesmějí přejít do náhledu ani exportu. Skutečné OCR/MP4 musí
zachovat malé masky nápisu a emoji, čitelné vlastní nadpisy a okolní obraz.

Zvukové testy ověřují pozdní akci, původní zdrojové posuny, odmítnutí
celoplošného záblesku, ruční čas, ztišení při řeči a zachování původního úderu.
Skutečný MP4 má ticho před zvoleným efektem a slyšitelný zvuk u momentu.
Browser ověřuje vynechání starého pruhu, odstranění neplatné masky, ruční SFX
čas a skutečný zvukový export. Nativní aplikace navíc kontroluje uložení času
v archivu projektu a po restartu. Syntéza/obrazové AI fixtures nejsou měřením
kvality skutečného modelu ani zapojení publika.
