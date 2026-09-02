from carrier_kb.domain import Audience, Corpus, Principal


def test_carrier_can_only_search_public_corpus():
    principal = Principal(subject="carrier-session", audience=Audience.CARRIER)
    assert principal.searchable_corpora == (Corpus.PUBLIC,)


def test_internal_can_search_both_corpora():
    principal = Principal(subject="employee", audience=Audience.INTERNAL)
    assert principal.searchable_corpora == (Corpus.PUBLIC, Corpus.INTERNAL)
