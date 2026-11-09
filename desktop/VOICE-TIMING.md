# Náhled s hlasem u krátkých klipů — 2.0.5

Oprava chyby „Voiceover klipu #4 je příliš dlouhý“ při tvorbě zvukového náhledu.
Předchozí výpočet používal celou délku souboru od TTS včetně případného ticha
na začátku/konci a pevnou rezervu. Krátké uvedení pořadí se tak mohlo odmítnout,
přestože se samotná řeč do střihu vešla.

Nové časování:

1. Změří skutečnou zvukovou stopu a odstraní pouze okrajové ticho. Ponechá
   ochranné okraje 80/100 ms a všechny pauzy uvnitř věty.
2. Zmenší úvodní odklad, aby se celá věta pokud možno vešla přirozeným tempem.
   Až potom může použít `atempo`, nejvýše 1,25×, se zachováním výšky hlasu.
3. V režimu **Uvedení pořadí zdarma** může použít kratší ekvivalent: například
   „Four.“ místo „Number four.“, nebo „Čtvrté.“ místo „Čtvrté místo.“. Pozici
   určuje aktuální pořadí klipu a použitou variantu oznámí pod úlohou. Oprava
   funguje i u starších uložených standardních uvedení pořadí bez příznaku režimu.
4. Celý hlas se smíchá s původním zvukem a zapnutými efekty. Obraz ani délka
   jednotlivých střihů či celého videa se kvůli voiceoveru neprodlužují.

Uložené texty a uvedení pořadí se nepřepisují kvůli konkrétnímu exportu; při
přeskládání nebo změně jazyka stále vycházejí z aktuálního pořadí. Příliš dlouhý
vlastní komentář se automaticky nenahrazuje obecným textem ani neusekává.
Pokud se nevejde ani po úpravě časování, zpráva uvede délku řeči i klipu a
nabídne zkrácení textu nebo uvedení pořadí. Původní výslovně povolené zkrácení
komentáře asistenta nadále zachovává původní smysl a podmínky poskytovatele.

Vlastní model obrazu není pro bezplatné uvedení pořadí potřeba. Andrew / Antonín
stále potřebuje internet pro syntézu Microsoft Edge; k jinému ani placenému
poskytovateli se aplikace automaticky nepřepíná. Ticho nebo neplatná odpověď
hlasové služby se vrátí jako srozumitelná chyba, ne jako němý „úspěšný“ export.

## Ověření

Python kontroluje skutečné audio s dlouhými okrajovými pauzami, zachování
vnitřních pauz a všech vzorků řeči, časování kolem 1/2 s, anglické i české
uvedení pořadí, kombinaci s efekty a neměnnou délku výsledného MP4.
Samostatný scénář ověřuje, že vlastní dlouhá věta není useknutá ani přepsaná.
Prošly také dosavadní testy bezplatného hlasu a povoleného zkrácení asistenta.

`scripts/speech-fit-browser-test.mjs` skutečně klikne na **Vytvořit náhled se
zvukem**, vygeneruje MP4 pro pět klipů včetně jednosekundové #4, ověří
přítomnost hlasu i efektu, oznámení krátké varianty a původní délku 10,3 s.
Odpověď hlasové služby je protokolová fixture; nejde o ověření dostupnosti
Microsoftu na počítači uživatele ani měření kvality skutečného hlasu.
