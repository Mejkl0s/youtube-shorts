# Uložený výběr AI (2.0.3)

Při prvním spuštění se režim **Lokální / Cloudový / Kombinovaný**, poskytovatel
a model vybírají v úvodním průvodci. Dokončení uloží konfiguraci a nastaví
vizuální hledání. Textový model bez podpory obrázků je vysvětlený už v průvodci;
neoznačí se za připravený pro výběr momentů. Pro práci bez vizuálního modelu
je k dispozici výslovné **Pokračovat bez obrazové AI**: projekt přejde na rychlý
technický výběr a tato volba se zachová i po restartu.

V editoru je hned nad pracovním postupem karta **Uložená volba pro hledání**.
Ukazuje režim a model, umožňuje rozbalit jejich výběr a nabízí tlačítko
**Nastavení AI**. Změny režimu/modelu se ukládají průběžně; stejné ovládání je
nadále v Nastavení → AI modely. Přechod do kombinovaného režimu zachovává
aktuální model, pokud zůstává platný. Režim se nemění při každém hledání.

**Najít klipy** přímo použije uloženého poskytovatele a model. Desktop už
neotevírá Nastavení na základě dříve načteného stavu dostupnosti. Aktuální
uložená konfigurace se ověří na backendu při zahájení úlohy. Chybějící klíč,
nepodporovaný obrazový model či nedostupná služba se oznámí přímo v editoru.
Nastavení se otevírá záměrně jeho tlačítkem, nikoli opakovaně před hledáním.
Stejně se chová opětovné vizuální posouzení originálů.

Cloud má nadále vlastní klíče a účtování; neprobíhá automatický placený
fallback ani automatické přepnutí k jinému poskytovateli. Běžící úloha používá
svůj původní snapshot modelu. Uložené projekty a vzhled Ultra Noir zůstávají.

## Ověření

- Python ověřuje přijetí hledání s uloženým vizuálním modelem pro lokální,
  cloudový i kombinovaný režim a srozumitelné odmítnutí textového modelu.
- Skutečný Electron ověřuje úvodní kontrolu podpory obrázků, zachování modelu
  při volbě kombinovaného režimu a opakované hledání bez otevření Nastavení.
  Záměrně používá neaktuální klientský stav `/health`; volba přesto zůstává
  uložená. Kontrola se opakuje po restartu aplikace.
- Další nativní scénář uloží práci bez obrazové AI, restartuje aplikaci a ověří
  opakované technické hledání bez průvodce či Nastavení.
- Původní průchod skutečným střihem a browserem nadále prochází. AI a síťové
  zdroje v automatizovaných scénářích jsou protokolové fixtures, nikoli nové
  měření obsahové přesnosti modelu.
