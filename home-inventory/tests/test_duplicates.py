"""Warning that something looks like it is already in the inventory.

The case this exists for is real: IKEA POÄNG is in the live database twice, entered once from
a photo as "POÄNG" and once from a link as "Ikea POÄNG". A plain substring search does not
find it — the model suggests "Poang armchair", which shares no substring with "POÄNG" once
the diaeresis is in the way.
"""

import json


def create(client, name, **fields):
    response = client.post("/api/items", data={"payload": json.dumps({"name": name, **fields})})
    assert response.status_code == 201, response.text
    return response.json()


def similar(client, name, brand=None):
    # brand is accepted by the callers below only to show it makes no difference; the
    # endpoint deliberately matches on words alone.
    return [i["name"] for i in client.get("/api/items/similar", params={"name": name}).json()]


def test_the_same_thing_spelled_without_its_accents_is_found(signed_in):
    create(signed_in, "POÄNG", brand="IKEA")

    assert similar(signed_in, "Poang armchair") == ["POÄNG"]


def test_a_longer_name_containing_the_existing_one_is_found(signed_in):
    create(signed_in, "Ikea POÄNG", brand="Ikea")

    assert similar(signed_in, "POÄNG armchair, oak and beige") == ["Ikea POÄNG"]


def test_unrelated_things_are_not_flagged(signed_in):
    create(signed_in, "Steam iron", brand="Braun")
    create(signed_in, "Computer monitor", brand="LG")

    assert similar(signed_in, "Bread knife", brand="Fiskars") == []


def test_common_words_alone_are_not_a_match(signed_in):
    """ "Chair" and "chair" would otherwise make every seat a duplicate of every other."""
    create(signed_in, "Office chair", brand="Herman Miller")

    assert similar(signed_in, "Ercol chair") == []


def test_the_brand_alone_is_not_enough(signed_in):
    """Owning two IKEA things is normal."""
    create(signed_in, "BILLY bookcase", brand="IKEA")

    assert similar(signed_in, "KALLAX shelf", brand="IKEA") == []


def test_nothing_to_compare_finds_nothing(signed_in):
    create(signed_in, "POÄNG")

    assert similar(signed_in, "   ") == []
