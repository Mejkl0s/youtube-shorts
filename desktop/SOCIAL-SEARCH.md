# TikTok a Instagram v hledání — 2.0.9

Obě sítě se hledají automaticky při každém „Najít klipy“. Každé kolo dává
TikToku i Instagramu souběžný požadavek; pomalá síť nespotřebuje první pokus
druhé sítě. Veřejné vyhledávače Bing a DuckDuckGo zkoušejí další dotazy,
formáty odkazů a až tři stránky jednoho dotazu v časovém limitu hledání.
TikTok používá odkazy na konkrétní video, Instagram také `/reels/` a `/p/`.
Profily se nepoužívají; obrázkový příspěvek musí následně projít stahovačem
a kontrolou skutečného videa. Různé instagramové cesty stejného ID se slučují.

Prázdný nebo nerozpoznaný výsledek jednoho dotazu nevyřadí druhou síť.
Skutečné odmítnutí, CAPTCHA nebo omezení počtu požadavků další pokusy
daného vyhledávače v aktuální úloze zastaví. Ochrany sítí se neobcházejí.
Při nedostatku odkazů z jedné sítě lze využít větší výběr z druhé;
konečný seznam se prokládá podle sítí a vynechává dříve použité odkazy.

Dotazy na dětské faily hledají také children, toddler, baby a bloopers.
Stále se vyžaduje zároveň téma a nepovedená akce; samotná dětská píseň
nebo sportovní fail bez odpovídajícího tématu neprojde. Vizuální kontrola
děje, délky střihů, zvukové plánování a malé blur masky zůstávají zachované.

## Přehled po hledání

**Výsledky jednotlivých zdrojů** ukazují zvlášť TikTok, Instagram a YouTube:
nalezené odkazy, načtená videa a obsahově přijaté momenty. Bez odkazů je uveden
výsledek veřejného indexu; neznamená to, že na síti žádná taková videa nejsou.
Pokud síť odmítla stažení nebo vyžaduje relaci, důvod se zobrazuje přímo na kartě.
Tlačítko **Přihlášení ke zdrojům** otevře existující import vlastní relace.
Samotné přihlášení v prohlížeči relaci do aplikace nepřenese.

Vyhledání veřejného odkazu a stažení videa jsou odlišné kroky. Instagram
a TikTok nemají v aplikaci dostupné univerzální veřejné vyhledávací API;
jejich obsah se objevuje prostřednictvím veřejného indexu. Ani nahrané cookies
nezaručují přístup. Nejsou použité cizí proxy, neoficiální placený scraping
ani automatické přepnutí na cloudovou AI. YouTube zůstává volitelný doplněk.

## Ověření

Kontroly používají skutečné parsování RSS/HTML přes HTTP transport fixtures,
parametry stránkování, souběžné požadavky s kontextem úlohy, druhé formáty
instagramových cest, vyloučení historie a doplnění většího výběru z jedné sítě.
Ověřují, že vadný TikTok dotaz nevyřadí Instagram a že důvody chyb neobsahují
syrová přihlašovací data. Browser kontroluje viditelné důvody a otevření relací.
V tomto vývojovém prostředí proxy vrací vyhledávačům HTTP 403; úspěšnost
živého hledání a stažení konkrétních sociálních videí zde nebyla ověřena.
