"""Ingrediensbanken for Oppgave-automaten.

Automaten trekker tilfeldige ingredienser herfra og gir dem til modellen som
inspirasjon. Uten dette lager språkmodeller nesten alltid den samme oppgaven
("lag en podkast om AI"). Kombinatorikken tvinger fram variasjon:
medium × tema × vri × AI-grep gir titusenvis av utgangspunkt.

Legg gjerne til flere linjer. Alt er på norsk fordi oppgavene er på norsk.
"""

from __future__ import annotations

import random

KATEGORIER: dict[str, dict[str, str]] = {
    "lyd": {"navn": "Lyd & musikk", "hint": "musikk, lydkunst, podkast, hørespill, stemme, rytme"},
    "bilde": {"navn": "Bilde & film", "hint": "foto, tegning, animasjon, kortfilm, plakat, tegneserie"},
    "ord": {"navn": "Ord & historier", "hint": "tekst, dikt, manus, teater, rap, taler, nyheter"},
    "spill": {"navn": "Spill & kode", "hint": "små apper, nettsider, spill, roboter, automatisering"},
    "hamar": {"navn": "Hamar & verden", "hint": "Mjøsa, Hamar, lokalhistorie, byen, naboene, framtida"},
    "kropp": {"navn": "Scene & kropp", "hint": "dans, teater, performance, bevegelse, kostyme, show"},
    "overrask": {"navn": "Overrask meg", "hint": "hva som helst"},
}

NIVAER: dict[str, str] = {
    "nybegynner": "Har kanskje bare brukt ChatGPT til å stille spørsmål. Trenger trygge, konkrete steg og ett verktøy om gangen.",
    "vant": "Bruker AI jevnlig, har prøvd bildegeneratorer eller vibe-koding. Tåler åpne oppgaver og flere verktøy.",
    "nerd": "Bygger ting selv, kan prompte godt. Trenger friksjon, rare begrensninger og ekte problemer, ikke oppskrifter.",
}

MEDIER: dict[str, list[str]] = {
    "lyd": [
        "en sang på 90 sekunder", "en jingle for en butikk i Hamar", "et hørespill med to stemmer",
        "en podkast-intro", "en lydcollage av byen", "en rap-battle mellom to historiske personer",
        "en vuggevise for en robot", "et lydspor til en stumfilm", "en radioreklame fra 1950",
        "en nasjonalsang for en oppdiktet øy i Mjøsa", "en lydguide til ett rom",
    ],
    "bilde": [
        "en plakat", "en tegneserie på fire ruter", "en 20-sekunders animasjon", "en fotoserie på fem bilder",
        "et bokomslag", "en stumfilm på ett minutt", "et kart over et sted som ikke finnes",
        "en filmtrailer for en film som aldri blir laget", "en meme-serie", "en utstilling i en skoeske",
        "et portrett i tre helt ulike stiler", "en storyboard for en musikkvideo",
    ],
    "ord": [
        "et dikt", "en tale", "et manus til en scene på to minutter", "en nyhetsartikkel fra 2041",
        "en dialog der bare den ene lyver", "en bruksanvisning for noe som ikke kan brukes",
        "en fortelling på nøyaktig 100 ord", "et leksikonoppslag om noe oppdiktet", "en rap-tekst",
        "en kjærlighetserklæring til et sted", "en klagebrev fra en gjenstand", "et intervju med en du aldri kan møte",
    ],
    "spill": [
        "et tekstbasert spill", "en nettside med ett formål", "en quiz som lærer deg noe", "en enkel app for én person",
        "en bot som svarer på én type spørsmål", "et brettspill med regler på én side", "en simulering av noe i naturen",
        "en generator som lager noe tilfeldig", "et lite verktøy som løser et irritasjonsmoment", "en interaktiv historie",
        "et spill du kan spille med noen på telefon", "en tidslinje du kan klikke i",
    ],
    "hamar": [
        "en turistguide til et sted turister aldri går", "en oppdiktet legende om Mjøsa", "en plan for Hamar i 2050",
        "et portrett av en gate", "en byvandring på fem stopp", "en avis fra Hamar i 1899",
        "et forslag til kommunestyret", "en reklame for Løten, Stange eller Ringsaker", "en samtale mellom Skibladner og Mjøsa",
        "en minnesamling fra en besteforelder", "en sammenlikning mellom Hamar og en by i Estland", "et nytt navn og logo for et sted du liker",
    ],
    "kropp": [
        "en dans på 30 sekunder", "en scene uten ord", "et show med én rekvisitt", "en koreografi til en lyd AI har laget",
        "et kostyme laget av det som finnes i rommet", "en talkshow-sketsj", "en teaterscene der AI er en av rollene",
        "en bevegelsessekvens som forklarer noe vanskelig", "et lite sirkusnummer", "en gjenskapning av et maleri",
        "en stumfilm framført live", "en ballade om en hverdagshelt",
    ],
}

TEMAER: list[str] = [
    "Mjøsa", "framtidas Hamar", "vennskap", "det som er pinlig", "et rykte", "å være ny et sted", "en hemmelighet",
    "noe bestemoren din vet som du ikke vet", "vær og vind", "skolen om 20 år", "en ting du samler på", "søvn",
    "penger", "det som er urettferdig", "et dyr som lever i Innlandet", "mat", "en oppfinnelse som mislyktes",
    "å kjede seg", "reiser", "musikk du ikke tør si at du liker", "en helt vanlig tirsdag", "roboter som er redde",
    "et sted som er borte", "lys og mørke", "et ord som ikke finnes på norsk", "1899", "2041", "frykt for å mislykkes",
    "det beste med å være 15", "en misforståelse", "vinter", "noe alle tror er sant men som er feil",
]

VRIER: list[str] = [
    "det må kunne forstås av en 6-åring", "det må lure en voksen til å tro det er ekte", "bare spørsmål er lov",
    "det skal handle om noe i rommet dere sitter i", "publikum må delta", "det skal være litt for dramatisk",
    "det skal være laget for én bestemt person", "det må inneholde en feil med vilje", "helt uten voksne ord",
    "alt må rime", "det må være mulig å gjøre på 30 sekunder", "det skal se ut som det er fra 1900",
    "det må ha en tvist på slutten", "det skal være i Hamar-dialekt", "to versjoner: én ekte, én falsk",
    "det skal være så dårlig som mulig, med vilje – og så bedre", "AI får bare hjelpe til én gang",
    "ingen får bruke ordet «AI»", "alt skal være svart-hvitt", "det må ta hensyn til noen som ikke kan se",
    "det må kunne henges opp på en vegg", "det skal være laget for noen som ikke kan norsk", "det skal vare nøyaktig ett minutt",
]

AI_GREP: list[str] = [
    "Få AI til å intervjue DEG først, og bruk svarene som råstoff.",
    "Lag det dårlig med vilje, be AI forklare hvorfor det er dårlig, fiks det selv.",
    "Be to ulike AI-er lage hver sin versjon og velg det beste fra begge.",
    "Gi AI en rolle (redaktør, kritisk bestemor, 6-åring) og la den vurdere det du laget.",
    "Skriv prompten som om det var et brev til en ekte person, ikke en kommando.",
    "Start uten AI i fem minutter. Bruk AI kun til det du står fast på.",
    "Be AI om ti ideer, kast alle, og be om ti som er det motsatte.",
    "Bruk AI til å oversette mellom kunstformer: fra bilde til lyd, fra lyd til tekst.",
    "Reverse-engineer: finn en prompt som gjenskaper noe som allerede finnes.",
    "La AI lage reglene, og du bryter dem.",
    "Be AI stille deg spørsmål til du vet hva du egentlig vil lage.",
    "Lag noe med AI, lag det samme uten AI, og sammenlikn foran gruppa.",
    "Be AI om å argumentere mot ideen din, og svar på kritikken.",
    "Bruk AI til å finne ut hva du IKKE trenger å lage.",
    "Gi AI en falsk fakta og se hvor lenge det tar før den merker det.",
    "Be AI lage tre helt ulike stiler, og velg den som er mest deg.",
    "Skriv første halvdel selv, la AI foreslå tre slutter, velg – eller lag din egen.",
    "Bruk AI som verktøy for å forstå noe, ikke lage noe: spør til du kan forklare det til en annen.",
    "Få AI til å lage et manus, og du framfører det uten å lese.",
    "Ta et bilde av noe i rommet og bruk det som utgangspunkt for alt.",
]

VERKTOY_HINT: list[str] = [
    "ChatGPT / Claude / Gemini (tekst og samtale)", "Suno eller Udio (musikk)", "ElevenLabs (stemmer)",
    "Lovable, Claude eller Bolt (vibe-koding av nettsider og apper)", "Midjourney, ChatGPT-bilder eller Ideogram (bilder)",
    "Runway, Pika eller Veo (video)", "CapCut (klipping)", "Canva (plakater, layout)", "penn og papir",
    "mobilkamera", "stemmen din", "Google Docs / Notes", "Scratch (spill uten kode)",
]

VIS_FRAM: list[str] = [
    "30 sekunder foran gruppa: vis, ikke forklar.",
    "Heng det på veggen med en lapp om prompten du brukte.",
    "Spill det av, og la de andre gjette hva som er AI og hva som er deg.",
    "Vis prosessen: det første forsøket ved siden av det siste.",
    "La en annen prøve det du laget, uten instruksjoner.",
    "Fortell én ting som overrasket deg.",
]


def trekk(kategori: str, rng: random.Random | None = None) -> dict[str, object]:
    """Trekk et sett ingredienser for én oppgave."""
    r = rng or random.Random()
    if kategori not in KATEGORIER or kategori == "overrask":
        kategori = r.choice([k for k in MEDIER])
    medier = MEDIER[kategori]
    return {
        "kategori": kategori,
        "kategori_navn": KATEGORIER[kategori]["navn"],
        "medium": r.choice(medier),
        "tema": r.sample(TEMAER, 2),
        "vri": r.choice(VRIER),
        "ai_grep": r.sample(AI_GREP, 2),
        "vis_fram": r.choice(VIS_FRAM),
    }
