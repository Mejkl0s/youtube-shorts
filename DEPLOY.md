# Zveřejnění Short Story Studia

Web obsahuje generátor 35/40/45sekundových 3D příběhů, českého mužského vypravěče, náhled scény, přehrání a stažení MP4. Tlačítko **Přehrát hotovou ukázku s hlasem** funguje ihned a nečeká na nový render. Ukázka je součástí webu, nikoli odkaz na soubor v cloudovém pracovním prostoru.

## Render

1. V Renderu vytvoř Blueprint z repozitáře `Mejkl0s/youtube-shorts`. Vyber větev s touto verzí aplikace (`codex/story-web-20261016`). Blueprint používá přiložený `render.yaml` a Dockerfile.
2. Služba `short-story-studio` je nastavena na bezplatný tarif. Heslo `STUDIO_PASSWORD` Render vygeneruje; najdeš ho v nastavení Environment dané služby. Uživatelské jméno je `owner`. Heslo neposílej do chatu ani neukládej do Gitu.
3. Po dokončení nasazení otevři **skutečnou URL služby uvedenou v Renderu** a přihlas se. Začni přehráním hotové ukázky, potom můžeš tvořit vlastní verze připravených příběhů.

Pro automatické nasazení z tohoto pracovního prostředí je potřeba bezpečně vložené `RENDER_API_KEY` a síťový přístup na `api.render.com`. Klíč patří do nastavení prostředí, ne do chatu nebo zdrojových souborů. Není součástí aplikace ani jejího Docker obrazu. Nastavení domén ani uložení návrhu samo web nenasadí.

## Provoz první verze

- Jeden webový proces poskytuje frontend, API i videa. `PORT` dodá hosting. Health check je `/api/health`.
- Základní mužský český hlas funguje lokálně bez placených API; přirozenější Piper/Jirka je volitelný a vyžaduje stažený model.
- Renderování používá CPU a na slabém bezplatném hostingu může trvat výrazně déle než na vývojovém stroji. Bezplatný tarif nepovažuj za garanci rychlosti 3D renderu. Aplikace zpracovává jeden příběh současně; úloha má časový limit 30 minut.
- Úložiště bezplatné služby je dočasné: vlastní hotová videa stahuj. Restart nebo nové nasazení může smazat uživatelská média a přerušit rozpracovaný render. Hotová přibalená ukázka zůstává součástí nové instalace.
- První verze používá tři připravené děje a jednoduché stylizované postavy. Úpravy komentáře mění titulky a vyprávění, nikoli choreografii. Další vzhled a funkce lze doplnit později.

Při sestavení za firemní proxy můžeš předat důvěryhodný CA bundle jako volitelný BuildKit secret `build_ca`. Dockerfile ho použije pouze při instalaci balíčků; certifikát neukládá do výsledného obrazu. Ověřování TLS zůstává zapnuté. Při běžném sestavení na Renderu tento parametr není potřeba.

## Anglická verze

Hlavní studio, výchozí komentáře i nová přibalená ukázka jsou anglicky. Nová verze používá společné časové značky pro pohyb, titulky a komentář, takže při klíčové akci není místo hlasu vložená pauza. Referenční video se přidává veřejným odkazem na konkrétní YouTube/TikTok/Instagram video. Základní analýza barev a světla nepotřebuje placený klíč; volitelná AI analýza vyžaduje `OPENAI_API_KEY` nastavený bezpečně na Renderu. AI ani modely, které nejsou dostupné, se v rozhraní nevydávají za zapnuté.

Přirozenější lokální anglický mužský hlas Ryan je volitelný: pro Docker build lze nastavit `INSTALL_STORY_NEURAL_VOICE=1`, čímž se stáhne a ověří oficiální model. Bez tohoto nastavení funguje základní syntetický mužský hlas. Onyx je další výslovně volitelná placená API varianta. U nové verze v již existující službě spusť **Manual Deploy → Deploy latest commit** ze stejné větve `codex/story-web-20261016`; její `autoDeploy` zůstává vypnuté.
