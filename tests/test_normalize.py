from memory_cards.normalize import apply_plural, parse_noun, parse_verb, split_regional, umlaut
from memory_cards.tts import speakable


def test_umlaut():
    assert umlaut("Apfel") == "Äpfel"
    assert umlaut("Haus") == "Häus"
    assert umlaut("Bruder") == "Brüder"


def test_plural_notations():
    assert apply_plural("Tisch", "-e") == ["Tische"]
    assert apply_plural("Ausflug", "¨-e") == ["Ausflüge"]
    assert apply_plural("Arzt", "-ä, e") == ["Ärzte"]
    assert apply_plural("Apfel", "-Ä") == ["Äpfel"]
    assert apply_plural("Lehrer", "-") == ["Lehrer"]
    assert apply_plural("Abonnement", "-s/-e") == ["Abonnements", "Abonnemente"]
    assert apply_plural("Datum", "-en") == ["Daten"]
    assert apply_plural("Risiko", "Risiken") == ["Risiken"]


def test_parse_noun():
    n = parse_noun("das Abitur (D)→A, CH: Matura")
    assert (n["article"], n["word"], n["regional"]) == ("das", "Abitur", "(D) → A, CH: Matura")
    n = parse_noun("die Eltern (Pl.)")
    assert n["pl_only"] and n["plural"] == ["Eltern"]
    n = parse_noun("der Nachbar, -n, die Nachbarin, -nen")
    assert n["plural"] == ["Nachbarn"] and n["feminine"].startswith("die Nachbarin")


def test_parse_verb():
    v = parse_verb("abfahren, fährt ab, fuhr ab, ist abgefahren")
    assert (v["er"], v["praeteritum"], v["aux"], v["partizip2"]) == ("fährt ab", "fuhr ab", "ist", "abgefahren")
    v = parse_verb("ärgern (sich), ärgert, hat geärgert")
    assert v["reflexive"] == "(sich)" and v["infinitive"] == "ärgern" and v["praeteritum"] == ""
    v = parse_verb("regnen, es regnet, es regnete, es hat geregnet")
    assert v["er"] == "regnet" and v["partizip2"] == "geregnet"
    v = parse_verb("abhängen, hängt ab, hing ab, hat abgehangen (von)")
    assert v["prep"] == "von"


def test_split_regional():
    assert split_regional("die Tomate, -n → A: Paradeiser") == ("die Tomate, -n", "→ A: Paradeiser")


def test_speakable():
    assert speakable("Ich habe mir Musik (he)runtergeladen.") == "Ich habe mir Musik heruntergeladen."
    assert speakable("Darf ich Ihnen/dir helfen?") == "Darf ich Ihnen oder dir helfen?"
