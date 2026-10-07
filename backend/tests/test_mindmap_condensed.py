"""The mind map when the material does not fit: structure from summaries, depth from search."""

import pytest

from src.features.ai_assistant.tasks.studio import _mindmap_condensed as mc


def _src(sid, label, summary, chunks=1):
    return {"id": sid, "label": label, "summary": summary,
            "chunks": [{"page_number": 1, "content": "x" * 100}] * chunks}


# --- summary_context --------------------------------------------------------

def test_every_source_becomes_one_labelled_block():
    text = mc.summary_context([_src(1, "a.pdf", "Über Alpha."), _src(2, "b.pdf", "Über Beta.")])
    assert "a.pdf" in text and "Über Alpha." in text
    assert "b.pdf" in text and "Über Beta." in text


def test_a_source_without_a_summary_is_left_out():
    text = mc.summary_context([_src(1, "a.pdf", "Über Alpha."), _src(2, "b.pdf", "")])
    assert "b.pdf" not in text


def test_without_any_summary_there_is_no_context():
    assert mc.summary_context([_src(1, "a.pdf", ""), _src(2, "b.pdf", None)]) == ""


# --- usable -----------------------------------------------------------------

def test_the_condensed_way_needs_a_summary_for_most_sources():
    assert mc.usable([_src(1, "a.pdf", "A"), _src(2, "b.pdf", "B")]) is True
    assert mc.usable([_src(1, "a.pdf", "A"), _src(2, "b.pdf", "")]) is False
    assert mc.usable([]) is False


# --- node_topics ------------------------------------------------------------

_SKELETON = {
    "topic": "Wurzel",
    "children": [
        {"topic": "Ast A", "children": [
            {"topic": "Zweig A1"},
            {"topic": "Zweig A2"},
        ]},
        {"topic": "Ast B", "children": []},
    ],
}


def test_the_root_is_no_search_topic():
    assert "Wurzel" not in mc.node_topics(_SKELETON)


def test_every_branch_and_twig_is_a_search_topic():
    assert mc.node_topics(_SKELETON) == ["Ast A", "Zweig A1", "Zweig A2", "Ast B"]


def test_the_number_of_search_topics_is_capped():
    assert len(mc.node_topics(_SKELETON, max_topics=2)) == 2


def test_a_skeleton_without_children_has_no_search_topic():
    assert mc.node_topics({"topic": "Allein"}) == []


# --- evidence_context -------------------------------------------------------

def test_a_passage_carries_its_file_and_page():
    text = mc.evidence_context({"Ast A": [{"source_label": "a.pdf", "page_number": 7,
                                           "content": "Der Satz."}]})
    assert "[a.pdf, S. 7]" in text and "Der Satz." in text


def test_a_media_passage_carries_its_timestamp():
    text = mc.evidence_context({"Ast A": [{"source_label": "v.webm", "start_time": 95,
                                           "page_number": 2, "content": "Gesagt."}]})
    assert "[v.webm, 1:35]" in text


def test_the_same_passage_under_two_topics_is_sent_once():
    treffer = {"Ast A": [{"source_label": "a.pdf", "page_number": 7, "content": "Der Satz."}],
               "Ast B": [{"source_label": "a.pdf", "page_number": 7, "content": "Der Satz."}]}
    assert mc.evidence_context(treffer).count("Der Satz.") == 1


def test_no_hits_make_no_context():
    assert mc.evidence_context({}) == ""


# --- search_evidence --------------------------------------------------------

def _chunk(label, page=1):
    return {"source_label": label, "page_number": page, "content": f"Text aus {label}"}


def test_every_topic_is_searched_once():
    gefragt = []
    mc.search_evidence(["Ast A", "Ast B"],
                       embed=lambda t: [0.1],
                       search=lambda q, vec, limit: gefragt.append(q) or [_chunk("a.pdf")])
    assert gefragt == ["Ast A", "Ast B"]


def test_the_hits_come_back_under_their_topic():
    out = mc.search_evidence(["Ast A"], embed=lambda t: [0.1],
                             search=lambda q, vec, limit: [_chunk("a.pdf", 3)])
    assert out["Ast A"][0]["page_number"] == 3


def test_a_failing_search_costs_only_its_own_topic():
    def suche(q, vec, limit):
        if q == "Ast A":
            raise RuntimeError("Index weg")
        return [_chunk("b.pdf")]

    out = mc.search_evidence(["Ast A", "Ast B"], embed=lambda t: [0.1], search=suche)
    assert "Ast A" not in out and out["Ast B"]


def test_no_topics_mean_no_search():
    assert mc.search_evidence([], embed=lambda t: pytest.fail("no embedding without a topic"),
                              search=lambda *a: None) == {}


# --- build ------------------------------------------------------------------

_GERIPPE = {"topic": "Wurzel", "children": [{"topic": "Ast A"}]}
_FERTIG = {"topic": "Wurzel", "children": [
    {"topic": "Ast A", "source_label": "a.pdf", "page_number": 3}]}


def _bauen(antworten, sucher=None, **over):
    """Runs build with a scripted ask, returns the map and what was asked."""
    calls = []

    def ask(messages):
        calls.append(messages)
        return antworten[len(calls) - 1]

    args = dict(sources=[_src(1, "a.pdf", "Über Alpha.")], language="Deutsch",
                adaptive_suffix="", ask=ask,
                embed=lambda t: [0.1],
                search=sucher or (lambda q, vec, limit: [_chunk("a.pdf", 3)]))
    args.update(over)
    return mc.build(**args), calls


def test_the_first_call_carries_the_summaries():
    _map, calls = _bauen([_GERIPPE, _FERTIG])
    assert "Über Alpha." in calls[0][1]["content"]


def test_the_second_call_carries_the_skeleton_and_the_passages():
    _map, calls = _bauen([_GERIPPE, _FERTIG])
    zweiter = calls[1][1]["content"]
    assert "Ast A" in zweiter and "[a.pdf, S. 3]" in zweiter


def test_the_second_call_also_carries_the_summaries():
    """The detail says WHAT, the passage only says WHERE, so both must travel."""
    _map, calls = _bauen([_GERIPPE, _FERTIG])
    assert "Über Alpha." in calls[1][1]["content"]


def test_the_finished_map_comes_back():
    karte, _calls = _bauen([_GERIPPE, _FERTIG])
    assert karte == _FERTIG


def test_without_a_skeleton_there_is_no_second_call():
    karte, calls = _bauen([None])
    assert karte is None and len(calls) == 1


def test_without_any_passage_the_skeleton_stays():
    karte, calls = _bauen([_GERIPPE], sucher=lambda q, vec, limit: [])
    assert karte == _GERIPPE and len(calls) == 1


def test_a_failed_deepening_keeps_the_skeleton():
    karte, _calls = _bauen([_GERIPPE, None])
    assert karte == _GERIPPE


# --- strip_unbacked ---------------------------------------------------------

def _knoten(topic, **felder):
    return {"topic": topic, **felder}


def test_a_node_whose_keyword_stands_on_the_claimed_page_keeps_it():
    karte = _knoten("A", source_label="a.pdf", page_number=3, keyword="Alpha")
    mc.strip_unbacked(karte, lambda label, page: "Text mit Alpha darin")
    assert karte["source_label"] == "a.pdf" and karte["page_number"] == 3


def test_a_node_whose_keyword_is_not_there_loses_its_attribution():
    karte = _knoten("A", source_label="a.pdf", page_number=3, keyword="Alpha")
    mc.strip_unbacked(karte, lambda label, page: "Ein ganz anderer Text")
    assert "source_label" not in karte and "page_number" not in karte \
        and "keyword" not in karte and karte["topic"] == "A"


def test_a_page_that_does_not_exist_loses_its_attribution():
    karte = _knoten("A", source_label="a.pdf", page_number=999, keyword="Alpha")
    mc.strip_unbacked(karte, lambda label, page: "")
    assert "source_label" not in karte


def test_the_check_ignores_case():
    karte = _knoten("A", source_label="a.pdf", page_number=3, keyword="ALPHA")
    mc.strip_unbacked(karte, lambda label, page: "text mit alpha")
    assert karte["source_label"] == "a.pdf"


def test_children_are_checked_too():
    karte = _knoten("Wurzel", children=[
        _knoten("gut", source_label="a.pdf", page_number=1, keyword="Alpha"),
        _knoten("schlecht", source_label="b.pdf", page_number=1, keyword="Beta"),
    ])
    mc.strip_unbacked(karte, lambda label, page: "Alpha" if label == "a.pdf" else "nichts")
    assert karte["children"][0]["source_label"] == "a.pdf"
    assert "source_label" not in karte["children"][1]


def test_a_node_without_any_attribution_is_left_alone():
    karte = _knoten("A")
    mc.strip_unbacked(karte, lambda label, page: "egal")
    assert karte == {"topic": "A"}


def test_a_timestamp_node_is_checked_against_its_spot():
    karte = _knoten("A", source_label="v.mp4", page_number="1:30", keyword="Alpha")
    mc.strip_unbacked(karte, lambda label, page: "Alpha steht hier")
    assert karte["source_label"] == "v.mp4"


def test_the_number_of_stripped_nodes_comes_back():
    karte = _knoten("Wurzel", children=[
        _knoten("a", source_label="a.pdf", page_number=1, keyword="X"),
        _knoten("b", source_label="b.pdf", page_number=1, keyword="Y"),
    ])
    assert mc.strip_unbacked(karte, lambda label, page: "nichts davon") == 2


# --- die strenge Belegregel --------------------------------------------------

def test_a_spot_our_own_search_returned_is_not_enough_on_its_own():
    """Measured on 30 statutes: the model then pins a leaf on any page of the right file."""
    karte = {"topic": "W", "children": [
        {"topic": "Ast", "source_label": "famfg.pdf", "page_number": 69, "keyword": "Nachlassgericht"}]}
    mc.strip_unbacked(karte, lambda label, page: "§ 408 Beschwerde")
    assert "page_number" not in karte["children"][0]


# --- pageless_leaves / locate -----------------------------------------------

def test_a_leaf_with_a_file_but_no_page_is_a_candidate():
    karte = {"topic": "W", "children": [{"topic": "Blatt", "source_label": "a.pdf"}]}
    assert [n["topic"] for n in mc.pageless_leaves(karte)] == ["Blatt"]


def test_a_branch_is_no_candidate_even_without_a_page():
    karte = {"topic": "W", "children": [
        {"topic": "Zweig", "source_label": "a.pdf", "children": [
            {"topic": "Blatt", "source_label": "a.pdf", "page_number": 3}]}]}
    assert mc.pageless_leaves(karte) == []


def test_a_leaf_that_already_has_its_page_is_no_candidate():
    karte = {"topic": "W", "children": [
        {"topic": "Blatt", "source_label": "a.pdf", "page_number": 3}]}
    assert mc.pageless_leaves(karte) == []


def test_a_leaf_without_any_file_is_no_candidate():
    karte = {"topic": "W", "children": [{"topic": "Blatt"}]}
    assert mc.pageless_leaves(karte) == []


def test_the_question_numbers_every_passage_once():
    blatt = {"topic": "Stammkapital", "source_label": "a.pdf"}
    text = mc.locate_context([(blatt, [_chunk("a.pdf", 6), _chunk("a.pdf", 7)])])
    assert "[1]" in text and "[2]" in text and "Stammkapital" in text


def test_a_passage_travels_whole_so_the_answer_is_not_hidden_behind_a_cut():
    """Measured: the key sentence sat at char 470 of a 995 char passage and was cut away."""
    lang = "Vorspann. " * 45 + "fuenfundzwanzigtausend Euro"
    blatt = {"topic": "Stammkapital", "source_label": "a.pdf"}
    text = mc.locate_context([(blatt, [{"source_label": "a.pdf", "page_number": 6,
                                        "content": lang}])])
    assert "fuenfundzwanzigtausend Euro" in text


def test_a_chosen_passage_gives_the_leaf_its_page():
    blatt = {"topic": "B", "source_label": "a.pdf"}
    paare = [(blatt, [_chunk("a.pdf", 6), _chunk("a.pdf", 7)])]
    mc.apply_located(paare, {"1": 2})
    assert blatt["page_number"] == 7 and blatt["source_label"] == "a.pdf"


def test_no_choice_leaves_the_leaf_alone():
    blatt = {"topic": "B", "source_label": "a.pdf"}
    mc.apply_located([(blatt, [_chunk("a.pdf", 6)])], {"1": None})
    assert "page_number" not in blatt


def test_a_number_outside_the_list_is_ignored():
    blatt = {"topic": "B", "source_label": "a.pdf"}
    mc.apply_located([(blatt, [_chunk("a.pdf", 6)])], {"1": 99})
    assert "page_number" not in blatt


def test_a_located_leaf_drops_its_stale_keyword():
    """The old keyword is from another passage, the PDF would highlight the wrong spot."""
    blatt = {"topic": "B", "source_label": "a.pdf", "keyword": "altes Wort"}
    mc.apply_located([(blatt, [_chunk("a.pdf", 6)])], {"N1": 1})
    assert "keyword" not in blatt and blatt["page_number"] == 6


def test_the_number_of_located_leaves_comes_back():
    b1 = {"topic": "B1", "source_label": "a.pdf"}
    b2 = {"topic": "B2", "source_label": "a.pdf"}
    paare = [(b1, [_chunk("a.pdf", 6)]), (b2, [_chunk("a.pdf", 8)])]
    assert mc.apply_located(paare, {"1": 1, "2": 2}) == 2


# --- skeleton_sources / fill_sources ----------------------------------------

def test_the_skeleton_names_the_file_behind_a_node():
    gerippe = {"topic": "W", "children": [{"topic": "Ast", "source_label": "a.pdf"}]}
    assert mc.skeleton_sources(gerippe, {"a.pdf"}) == {"Ast": "a.pdf"}


def test_a_file_that_was_not_selected_is_dropped():
    gerippe = {"topic": "W", "children": [{"topic": "Ast", "source_label": "erfunden.pdf"}]}
    assert mc.skeleton_sources(gerippe, {"a.pdf"}) == {}


def test_the_root_is_no_source_of_its_own():
    gerippe = {"topic": "W", "source_label": "a.pdf", "children": []}
    assert mc.skeleton_sources(gerippe, {"a.pdf"}) == {}


def test_a_node_without_a_file_gets_the_one_from_the_skeleton():
    karte = {"topic": "W", "children": [{"topic": "Ast", "children": [{"topic": "Zweig"}]}]}
    mc.fill_sources(karte, {"Zweig": "a.pdf"})
    assert karte["children"][0]["children"][0]["source_label"] == "a.pdf"


def test_a_main_branch_carries_no_file_of_its_own():
    """A main branch spans several laws, one chip on it would be arbitrary."""
    karte = {"topic": "W", "children": [{"topic": "Ast", "source_label": "a.pdf"}]}
    mc.fill_sources(karte, {})
    assert "source_label" not in karte["children"][0]


def test_below_the_main_branch_the_file_is_kept():
    karte = {"topic": "W", "children": [
        {"topic": "Ast", "children": [{"topic": "Zweig", "source_label": "a.pdf"}]}]}
    mc.fill_sources(karte, {})
    assert karte["children"][0]["children"][0]["source_label"] == "a.pdf"


def test_a_leaf_without_a_file_inherits_it_from_its_branch():
    karte = {"topic": "W", "children": [{"topic": "Ast", "children": [
        {"topic": "Zweig", "children": [{"topic": "Blatt"}]}]}]}
    mc.fill_sources(karte, {"Zweig": "a.pdf"})
    assert karte["children"][0]["children"][0]["children"][0]["source_label"] == "a.pdf"


def test_a_verified_spot_beats_the_inherited_file():
    karte = {"topic": "W", "children": [
        {"topic": "Ast", "children": [
            {"topic": "Blatt", "source_label": "b.pdf", "page_number": 7}]}]}
    mc.fill_sources(karte, {"Ast": "a.pdf"})
    blatt = karte["children"][0]["children"][0]
    assert blatt["source_label"] == "b.pdf" and blatt["page_number"] == 7


def test_the_root_stays_without_a_file():
    karte = {"topic": "W", "children": [{"topic": "Ast"}]}
    mc.fill_sources(karte, {"W": "a.pdf", "Ast": "b.pdf"})
    assert "source_label" not in karte


def test_an_inherited_file_carries_no_page():
    karte = {"topic": "W", "children": [{"topic": "Ast"}]}
    mc.fill_sources(karte, {"Ast": "a.pdf"})
    assert "page_number" not in karte["children"][0]


def test_the_number_of_filled_nodes_comes_back():
    karte = {"topic": "W", "children": [{"topic": "Ast", "children": [
        {"topic": "Zweig", "children": [{"topic": "B1"}, {"topic": "B2"}]}]}]}
    assert mc.fill_sources(karte, {"Zweig": "a.pdf"}) == 3


# --- should_condense --------------------------------------------------------

_MIT = [_src(1, "a.pdf", "A"), _src(2, "b.pdf", "B")]
_OHNE = [_src(1, "a.pdf", "A"), _src(2, "b.pdf", "")]


def test_material_that_fits_is_read_in_full():
    # A summary throws away detail that is there, so it is the worse way here.
    assert mc.should_condense(90_000, 100_000, _MIT) is False


def test_material_that_does_not_fit_goes_through_the_summaries():
    assert mc.should_condense(110_000, 100_000, _MIT) is True


def test_without_summaries_the_raw_way_stays_even_when_it_does_not_fit():
    assert mc.should_condense(110_000, 100_000, _OHNE) is False


# --- build_small: a small model takes one deepening call per main branch -------

_DREI_AESTE = {"topic": "Wurzel", "children": [
    {"topic": "Ast A", "source_label": "a.pdf"},
    {"topic": "Ast B", "source_label": "b.pdf"},
    {"topic": "Ast C", "source_label": "a.pdf"}]}


def _ast(topic):
    return {"topic": "Wurzel", "children": [{"topic": topic, "children": [{"topic": topic + " 1"}]}]}


def _klein(antworten, stand=None, limit=100000, **over):
    calls = []

    def ask(messages):
        calls.append(messages)
        return antworten[len(calls) - 1] if len(calls) <= len(antworten) else None

    def suche(q, vec, limit):
        datei = "b.pdf" if "B" in q else "a.pdf"
        return [_chunk(datei, 7 if datei == "b.pdf" else 3)]

    args = dict(sources=[_src(1, "a.pdf", "Über Alpha."), _src(2, "b.pdf", "Über Beta.")],
                language="Deutsch", adaptive_suffix="", ask=ask, embed=lambda t: [0.1],
                search=suche, limit_chars=limit, stand={} if stand is None else stand)
    args.update(over)
    return mc.build_small(**args), calls


def test_klein_jeder_hauptast_bekommt_einen_eigenen_aufruf():
    karte, calls = _klein([_DREI_AESTE, _ast("Ast A"), _ast("Ast B"), _ast("Ast C")])
    assert len(calls) == 4
    assert [k["topic"] for k in karte["children"]] == ["Ast A", "Ast B", "Ast C"]
    assert karte["children"][1]["children"][0]["topic"] == "Ast B 1"


def test_klein_ein_ast_sieht_nur_seine_eigenen_belege():
    _karte, calls = _klein([_DREI_AESTE, _ast("Ast A"), _ast("Ast B"), _ast("Ast C")])
    ast_b = calls[2][1]["content"]
    assert "[b.pdf, S. 7]" in ast_b and "[a.pdf, S. 3]" not in ast_b
    assert "Über Beta." in ast_b and "Über Alpha." not in ast_b


def test_klein_ein_kaputter_ast_bleibt_wie_im_gerippe():
    karte, _calls = _klein([_DREI_AESTE, _ast("Ast A"), None, _ast("Ast C")])
    assert karte["children"][1]["topic"] == "Ast B"
    assert "children" not in karte["children"][1]


def test_klein_ein_neuer_lauf_macht_beim_gemerkten_stand_weiter():
    """Ran out of time after branch A: the next run asks only for B and C."""
    stand = {"skelett": _DREI_AESTE, "ast0": _ast("Ast A")["children"][0]}
    karte, calls = _klein([_ast("Ast B"), _ast("Ast C")], stand=stand)
    assert len(calls) == 2
    assert "Ast B" in calls[0][1]["content"] and "Ast C" in calls[1][1]["content"]
    assert karte["children"][0]["children"][0]["topic"] == "Ast A 1"


def test_klein_jeder_schritt_wird_gemerkt():
    stand = {}
    _klein([_DREI_AESTE, _ast("Ast A"), _ast("Ast B"), _ast("Ast C")], stand=stand)
    assert set(stand) == {"skelett", "ast0", "ast1", "ast2"}


def test_klein_kein_aufruf_ist_groesser_als_die_grenze():
    viel = [_chunk("a.pdf", s) for s in range(1, 40)]
    for c in viel:
        c["content"] = "x" * 500
    _karte, calls = _klein([_DREI_AESTE, _ast("Ast A"), _ast("Ast B"), _ast("Ast C")],
                           limit=3000, search=lambda q, vec, limit: viel)
    assert all(len(c[1]["content"]) <= 3000 for c in calls[1:])


def test_ohne_gerippe_gibt_es_keine_karte():
    karte, calls = _klein([None])
    assert karte is None and len(calls) == 1


def test_seitensuche_wird_in_passende_gruppen_geteilt():
    blatt = lambda i: ({"topic": f"N{i}"}, [{"content": "y" * 400}])
    gruppen = mc.located_in_batches([blatt(i) for i in range(10)], 1000)
    assert len(gruppen) > 1 and sum(len(g) for g in gruppen) == 10
    assert all(len(mc.locate_context(g)) <= 1000 for g in gruppen)
