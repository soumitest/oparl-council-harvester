from harvester.filters import match_keywords


def test_german_compounds_match():
    assert match_keywords("Standort Rechenzentrumsgelände") == ["rechenzentrum"]
    assert "umspannwerk" in match_keywords("Erweiterung Umspannwerkes Nord")


def test_case_insensitive_and_multiple():
    assert match_keywords("NEUE 110-kV Hochspannung") == ["110-kv", "hochspannung"]


def test_no_match_and_none_inputs():
    assert match_keywords("Haushaltsplan 2027", None) == []
    assert match_keywords(None, None) == []


def test_ekom21_gebietsrechenzentrum_is_not_a_signal():
    title = "Wahl für die Verbandsversammlung der ekom21 – Kommunales Gebietsrechenzentrum Hessen"
    assert match_keywords(title) == []


def test_real_signal_next_to_excluded_phrase_still_matches():
    assert match_keywords("Gebietsrechenzentrum und Neubau Rechenzentrum Osthafen") == ["rechenzentrum"]
