# -*- coding: utf-8 -*-
"""Erkennung, ob eine Ortsangabe ausserhalb Europas liegt.

Grundsatz (bewusst vorsichtig): Es wird NUR ausgeschlossen, wenn ein Land
positiv als aussereuropaeisch erkannt wird. Alles Unklare bleibt drin - lieber
ein Fehltreffer zu viel als eine echte Maschine verloren.
"""
import re

# ISO-Kuerzel, die Mascus verwendet - nur eindeutig aussereuropaeische
NICHT_EU_ISO = {
    "CN", "US", "CA", "MX", "BR", "CL", "AR", "PE", "CO", "VE", "EC", "BO", "UY", "PY",
    "IN", "JP", "KR", "TH", "VN", "ID", "MY", "SG", "PH", "TW", "HK", "PK", "BD", "LK",
    "AU", "NZ", "ZA", "EG", "MA", "DZ", "TN", "LY", "NG", "KE", "GH", "ET", "TZ", "UG",
    "AE", "SA", "QA", "KW", "OM", "BH", "JO", "LB", "IL", "IQ", "IR", "SY", "YE", "AF",
    "KZ", "UZ", "TM", "KG", "TJ", "MN", "NP", "MM", "KH", "LA", "BN", "CU", "DO", "GT",
    "HN", "NI", "CR", "PA", "JM", "TT", "SV", "BZ",
}

# Deutsche Landesnamen, wie Machineryline/Machinerypark/Maschinensucher sie schreiben
NICHT_EU_NAMEN = {
    "china", "usa", "vereinigte staaten", "kanada", "mexiko", "brasilien", "chile",
    "argentinien", "peru", "kolumbien", "venezuela", "ecuador", "bolivien", "uruguay",
    "paraguay", "indien", "japan", "korea", "suedkorea", "südkorea", "thailand",
    "vietnam", "indonesien", "malaysia", "singapur", "philippinen", "taiwan",
    "hongkong", "pakistan", "bangladesch", "sri lanka", "australien", "neuseeland",
    "suedafrika", "südafrika", "aegypten", "ägypten", "marokko", "algerien",
    "tunesien", "libyen", "nigeria", "kenia", "ghana", "aethiopien", "äthiopien",
    "tansania", "uganda", "vereinigte arabische emirate", "saudi-arabien", "katar",
    "kuwait", "oman", "bahrain", "jordanien", "libanon", "israel", "irak", "iran",
    "syrien", "jemen", "afghanistan", "kasachstan", "usbekistan", "turkmenistan",
    "kirgisistan", "tadschikistan", "mongolei", "nepal", "myanmar", "kambodscha",
    "laos", "kuba", "guatemala", "honduras", "nicaragua", "costa rica", "panama",
    "jamaika",
    # Nachtrag 12.09.2026: "Papua-Neuguinea, Bank" war durchgerutscht - Liste um die
    # restlichen Staaten Ozeaniens, Asiens, Afrikas und Amerikas ergaenzt.
    "papua-neuguinea", "papua neuguinea", "fidschi", "samoa", "tonga", "vanuatu",
    "salomonen", "neukaledonien", "franzoesisch-polynesien", "französisch-polynesien",
    "guam", "mikronesien", "palau", "kiribati", "nauru", "tuvalu", "marshallinseln",
    "china", "volksrepublik china", "suriname", "guyana", "franzoesisch-guayana",
    "französisch-guayana", "haiti", "bahamas", "barbados", "grenada", "st. lucia",
    "dominica", "antigua und barbuda", "puerto rico", "aruba", "curacao", "curaçao",
    "bermuda", "groenland", "grönland", "island der jungferninseln",
    "angola", "kamerun", "senegal", "mali", "niger", "tschad", "sudan", "suedsudan",
    "südsudan", "somalia", "eritrea", "dschibuti", "ruanda", "burundi", "sambia",
    "simbabwe", "mosambik", "botswana", "namibia", "lesotho", "eswatini", "malawi",
    "madagaskar", "mauritius", "seychellen", "gabun", "kongo", "elfenbeinkueste",
    "elfenbeinküste", "burkina faso", "benin", "togo", "guinea", "sierra leone",
    "liberia", "gambia", "mauretanien", "kap verde",
    # Georgien/Armenien/Aserbaidschan bewusst NICHT gesperrt - transkontinental wie
    # Tuerkei und Russland, die ebenfalls als Europa gelten (Europarat/UEFA).
    "bhutan", "malediven", "osttimor",
    "brunei", "macau", "nordkorea",
}


def ist_ausserhalb_europas(ort: str) -> bool:
    """True nur, wenn die Ortsangabe eindeutig ein aussereuropaeisches Land nennt."""
    if not ort:
        return False
    text = ort.strip()

    # Mascus-Format "CN, Shanghai" bzw. "CN, -"
    kopf = re.match(r"^([A-Z]{2})\s*,", text)
    if kopf and kopf.group(1) in NICHT_EU_ISO:
        return True
    # Mascus ohne Stadt, z.B. nur "CN"
    if len(text) == 2 and text.isupper() and text in NICHT_EU_ISO:
        return True

    # Landesnamen: Machineryline "China, Shanghai" (vorn),
    # Machinerypark "6166 Hasle, Schweiz" (hinten), Maschinensucher "Spanien" (allein)
    teile = [t.strip().lower() for t in text.split(",")]
    for t in (teile[0], teile[-1]):
        if t in NICHT_EU_NAMEN:
            return True
    return False
