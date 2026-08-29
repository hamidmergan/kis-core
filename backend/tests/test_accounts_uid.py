from src.features.accounts.uid import name_to_uid, slugify_uid, unique_uid


def test_slugify_keeps_a_plain_local_part():
    assert slugify_uid("max.mustermann") == "max.mustermann"


def test_slugify_lowers_case_and_replaces_umlauts():
    assert slugify_uid("Jörg.Müller") == "joerg.mueller"


def test_slugify_drops_characters_ldap_does_not_accept():
    assert slugify_uid("anna+test") == "annatest"


def test_slugify_returns_none_when_nothing_usable_is_left():
    assert slugify_uid("!!!") is None
    assert slugify_uid("a") is None


def test_name_to_uid_joins_given_name_and_surname():
    assert name_to_uid("Max", "Mustermann") == "max.mustermann"


def test_name_to_uid_handles_spaces_in_the_name():
    assert name_to_uid("Anna Lena", "von Bergen") == "anna-lena.von-bergen"


def test_name_to_uid_returns_none_without_a_surname():
    assert name_to_uid("Max", "  ") is None


def test_unique_uid_returns_the_base_when_it_is_free():
    assert unique_uid("max.mustermann", lambda _: False) == "max.mustermann"


def test_unique_uid_appends_the_smallest_free_number():
    belegt = {"max.mustermann", "max.mustermann2"}
    assert unique_uid("max.mustermann", lambda u: u in belegt) == "max.mustermann3"


def test_unique_uid_shortens_the_base_so_the_number_still_fits():
    lang = "a" * 32
    ergebnis = unique_uid(lang, lambda u: u == lang)
    assert len(ergebnis) <= 32
    assert ergebnis.endswith("2")
