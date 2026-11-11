# Celé názvy a emoji — 2.0.6

## Co se změnilo

- OCR kombinuje dva režimy čtení. K dobře rozpoznanému slovu ponechá i slabší
  sousední slova a interpunkci, místo aby maskovalo jen nejčitelnější část.
- Geometricky spojuje části stejného řádku a přidá okraje pro konturu a stín.
- U textu hledá také přilehlé světlé nebo barevné symboly opakující se na stejném místě.
  Může tak rozšířit masku přes navazující emoji, které OCR nepřečte jako slovo.
- Vizuální AI umí samostatný typ `emoji` a dostává pokyn zakrýt celé názvy,
  přidružené emoji i samostatné vložené emoji/stickery. Posuzuje až šest snímků
  a může přijmout jasný krátkodobý překryv viditelný v jednom z nich.
- Detektor používá hustší časové vzorky, nejvýše třináct na jeden výřez.
- Rozmazání má sílu odpovídající výšce oblasti; velká písmena nezůstávají jen
  lehce změkčená. Zdroj se čistí před vykreslením vlastního nadpisu a pořadí.
- V dialogu **Rozmazání** je volba **Zvětšit okraje** pro každou oblast.

Masky zůstávají omezené na aktivní obraz, nejvýše osm oblastí, jednotlivě 20 %
a dohromady 35 % rámu. Ruční oblasti a jejich způsob úpravy se při opakovaném
hledání zachovávají. Celé video a původní střihy se kvůli čištění nepřepisují.

## Použití

Nové hledání používá zatržítko **Automaticky upravit celé nápisy, emoji, loga a
černé bloky**. U již uložených klipů klikni na **Vyčistit všechny klipy**, aby se
staré automatické masky přepočítaly. Jednotlivý klip otevři přes **Rozmazání →
Najít celé nápisy, emoji, loga a bloky**, případně oblast zvětši nebo nakresli.
Zkontroluj různé snímky a hotové MP4.

OCR a rozšíření řádků fungují lokálně bez AI klíče. Pro obsahové rozpoznání
samostatných emoji/stickerů slouží vybraný vizuální model v AI hledání nebo
výslovně spuštěném hromadném čištění. Lokální model lze použít i pro jednotlivý
klip. Samostatné OCR volání automaticky nečerpá cloudový klíč. Ke změně modelu
ani k placenému náhradnímu poskytovateli nedochází.

Rozpoznání používá vzorky snímků; nepředstavuje záruku nalezení každého
pohyblivého nebo velmi krátkého překryvu. Obrazový doprovod u textu je geometrický
odhad. Nejasné oblasti lze upravit ručně. Doplnění okolím stále není rekonstrukce
původního obrazu skrytého pod nápisem.

## OCR v instalátoru

Windows balíček nyní obsahuje Tesseract 5.4.0, jeho knihovny a anglická jazyková
data, konfigurace, dostupné licenční soubory a manifest SHA-256. Čtení textu
nevyžaduje vlastní systémovou instalaci Tesseract. Backend nastaví přednostně
přibalený nástroj i vlastní adresář jazykových dat.

CI používá distribuci z kontrolním součtem ověřeného instalátoru UB Mannheim
5.4.0.20240606. Krok instalace předá `RANK_OCR_SOURCE` přímo do sestavení. Při
ručním Windows buildu musí tato proměnná ukazovat na adresář stejné ověřené
distribuce s `tesseract.exe`, DLL a `tessdata/eng.traineddata`; build při chybějící
nebo nesprávné verzi skončí chybou. Není přidáno stahování při prvním spuštění.

## Ověření

Python testy kontrolují slabší slova, oba OCR režimy, dva přilehlé emoji, odmítnutí
vzdáleného pohybujícího se objektu, samostatné krátkodobé emoji z obrazové AI a
platné souřadnice. Skutečné OCR a export MP4 ověřují zakrytí celého názvu a
emoji, omezení rozmazání na vybrané oblasti a ostré vlastní nadpisy.

Browser ověřuje rozpoznání, zvětšení masky, náhled, uložení a skutečné MP4 bez
AI poskytovatele. Nativní scénář vytváří titulkový klip a provádí skutečné OCR;
Windows běh vyžaduje přibalené OCR a záměrně zadává neplatný vnější adresář
jazyků, aby ověřil nezávislost balíčku na uživatelské konfiguraci.
