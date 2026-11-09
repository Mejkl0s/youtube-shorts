# Klipy, zvuk a poznámky — 2.0.4

## Zvuk na konci jednotlivého klipu

Každý klip má volbu **Zvuk na konci**:

- **Automaticky zjemnit hlasitý konec**: porovná RMS zvuku v posledních 1,5 s.
  Potlačí prudký hlasitý nástup omezený na poslední půlsekundu, pokud překročí
  absolutní práh i okolní zvuk přibližně o 10 dB. Souvislý hlasitý děj zachová.
  Posledních 12 ms jemně stáhne kvůli lupnutí na střihu.
- **Ponechat důležitý zvuk**: zachová původní koncový zvuk. Použij například pro
  náraz, výkřik nebo reakci, která patří k hlavnímu momentu.
- **Ztlumit posledních 0,5 s**: stáhne pouze konec původní zvukové stopy.

Obraz ani délka klipu se nemění. Volba nemění syntetický voiceover či přidané
SFX; zpracovává původní zdroj před jejich smícháním. Automatika měří amplitudu,
nepoznává význam zvuku. Náhlý důležitý zvuk lze výslovně ponechat.
Výsledek uslyšíš ve **Vytvořit náhled se zvukem** a v exportu; malý přehrávač
originálu přehrává původní zvuk. Nastavení je uložené s klipem v projektu.

## Barvy a šířka editoru

Ve **Finální doladění → Čísla a poznámky** vyber medailové barvy, barvu aktuální
pozice nebo barvu každého čísla zvlášť. Pět dostupných barevných polí přepne
vzhled do individuální palety. Náhled, export, uložený projekt a export projektu
používají stejné nastavení. Čísla nadále sledují pořadí; poznámky sledují klipy.
Editor využívá dostupnou šířku okna; na širokých monitorech už nemá středový
limit 1550 px. Menší okna a mobilní rozložení zůstávají responzivní.

## Poznámky podle konkrétního výřezu

Nové vizuálně vybrané momenty používají poznámku z obrazového posouzení děje.
Technický výběr a nové ruční nahrání nedoplňují náhodné reakce. Existující
ručně napsané nebo dříve uložené texty se automaticky nepřepisují.

Tlačítko **Poznámky podle klipů** pošle časově označené snímky skutečných
aktuálních výřezů uloženému vizuálnímu modelu, po jednom klipu. Cloud používá
výslovně vybraného poskytovatele a jeho účtování; bezplatný náhradní či jiný
placený poskytovatel se automaticky nevolí. Běžící úloha drží původní snapshot.
Krátké poznámky mají nejvýše čtyři slova a lze je ručně upravit. Nejasné nebo
obecné odpovědi se odmítnou a původní poznámky zůstanou zachované.

Poznámka se objeví až při začátku vlastního klipu: po 120 ms krátce najede
zleva a během 240 ms zesílí do plné viditelnosti. Ve sloupci zůstane do konce
videa; budoucí poznámky se předem neprozrazují. Ve zobrazení jediného čísla
zůstává poznámka po dobu příslušného klipu. Animaci lze vypnout. Náhled během
pauzy ukazuje usazený text; během přehrávání a v MP4 probíhá nástup.

Změna výřezu zneplatní jeho automatickou poznámku, aby nezůstal popis jiného
momentu. Ručně napsané poznámky zůstávají. Vizuální AI posuzuje vzorky obrazu;
popis i střih je stále potřeba zkontrolovat.

## Ověření

Testy dekódují skutečné MP4 a zvuk: kontrolují nástup/přetrvání poznámek,
individuální barvu čísla, zjemnění prudkého konce, zachování důležitého zvuku,
ztlumení a neměnnou délku obrazu. Browser ověřuje sedm šířek 390–2560 px,
uložení barev a zvuku, poznámky ze skutečných výřezů a jejich zneplatnění po
změně střihu. Nativní Electron ověřuje poznámky po jednom klipu, barvy,
export MP4, archiv projektu a zachování změn po restartu. AI a síťové zdroje
v těchto scénářích jsou protokolové fixtures, nikoli měření kvality modelu.
