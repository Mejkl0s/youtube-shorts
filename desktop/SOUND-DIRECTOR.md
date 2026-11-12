# Zvuky podle děje — 2.0.8

## Výběr typu a správného okamžiku

Automatický plán používá uložený vizuální model. Nejprve prohlédne časově
značené snímky aktuálního výřezu a navrhne konkrétní dějové body. Potom je
ověří na hustších snímcích okolo navržených časů, po nejvýše dvou kandidátech
na jeden požadavek kvůli paměti lokálních modelů. Nepotvrzené nebo nejasné
návrhy se vynechají, místo aby se doplnily libovolným zvukem.

Dějové body mají omezené vhodné typy efektů:

| Co je vidět | Vhodný typ |
|---|---|
| Příprava na událost | Krátké stupňování napětí |
| Výrazný pohyb | Jemný přechod |
| Kontakt nebo náraz | Krátký úder |
| Překvapení, odhalení nebo reakce | Pop |
| Náhlé zastavení | Krátká komická brzda |
| Jasná pointa či dokončení | Jemný závěrečný tón |

AI nesmí vymýšlet dialog ani tvrdit, že slyšela konkrétní zvuk. Časování je
v sekundách aktuálního výřezu, nikoli původní kompilace. Typ musí odpovídat
popsané viditelné události. Vítězné pořadí samo o sobě není důvod k oslavnému
zvuku; jasně doložené dokončení ano.

Pevný limit dvou efektů je odstraněný. Počet určuje počet různých potvrzených
událostí a délka klipu. Plán může obsahovat více než dva zvuky, ale může být
i prázdný. Ochranné limity jsou nejvýše 12 krátkých zvuků, odstup mezi různými
událostmi, omezení opakování stejného zvuku, nejvýše dva souběžné zvuky a
celková délka efektů nejvýše 45 % klipu / 4 sekundy. Přípravný zvuk může
vyústit přesně do jednoho úderu nebo překvapení; nejde o mechanické přidělení
stanoveného počtu efektů každému klipu.

## Mix a úpravy

Výrazný původní úder má přednost před dalším přidaným úderem. Efekty jsou
tišší pod voiceoverem i hlasitým původním zvukem. Rozhodnutí respektuje
nastavenou hlasitost původní stopy. Každý zvuk se musí celý vejít do střihu.
Používají se vlastní syntetické zvuky, ne kopie zvukové stopy jiného videa.

V hotovém náhledu otevři **Časování efektů**: každý použitý zvuk má typ, čas
a konkrétní popis. **Upravit plán klipu** jej převede na **Vlastní plán efektů**.
Tam lze každý zvuk přidat/odebrat, změnit jeho typ, čas a sílu. Upravený plán
se ukládá s projektem, exportuje do archivu a zůstává po restartu. Vlastní plán
už nevyvolává další obrazové AI posouzení. Výsledek ověř novým náhledem se zvukem.

Dřívější **Vlastní čas momentu** zůstává pro jednoduché zvýraznění jednoho
okamžiku. **Bez přidaných efektů** a globální vypnutí nadále zcela vypínají
plánování efektů. Nulová hlasitost efektů také nespouští obrazové posouzení.
Změna střihu zneplatní vlastní plán; čas je potřeba znovu určit pro nový výřez.

## Model a opakovaný náhled

V desktopu se použije uložený lokální, cloudový nebo kombinovaný výběr modelu
s podporou obrázků. Snímky jdou pouze tomuto poskytovateli. Cloud čerpá jeho
vlastní klíč a účtování; nedochází k přepnutí na jinou placenou službu.
Lokální obrazový model může pracovat bez placeného API.

Bez připraveného vizuálního modelu zůstává konzervativní časování podle
existujícího posouzení či pohybového odhadu, případně původní zvuk. Tento odhad
není porozumění konkrétnímu ději. Chyba AI neblokuje export; zobrazí se zpráva
a zůstane konzervativní varianta. Nastavení se samo neotevírá.

Ověřený obrazový plán se ukládá soukromě pro daný zdroj, výřez a model, aby
změna hlasitosti nevyvolávala stejné obrazové požadavky znovu. Změna modelu,
zdroje nebo střihu tento plán zneplatní. V této mezipaměti nejsou API klíče.
Vhodnost efektů stále závisí na kvalitě obrazu/modelu a je potřeba ji poslechem
zkontrolovat; počet zvuků není měřítkem dobrého střihu.

## Ověření

Testy ověřují volbu typu podle události, zamítnutí neplatného či nedoloženého
návrhu, více než dva různé efekty, pauzy a omezení překryvu, dvojici příprava/
kontakt, detailní ověření nad skutečnými snímky, mezipaměť podle modelu/výřezu,
neukládání klíče, všechny zvukové typy a vlastní plán. Automatizované odpovědi
AI jsou protokolové fixtures, nikoli měření skutečné kvality modelu nebo
sledovanosti. Nativní scénář ověřuje více efektů v MP4 a úpravu typu zachovanou
v archivu i po restartu. Úzké masky rozmazání z verze 2.0.7 zůstávají zachované.
