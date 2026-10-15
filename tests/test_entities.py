from pathlib import Path
import json
import pytest
from tinycrate.tinycrate import TinyCrate, TinyCrateException, minimal_crate


def test_basic_entity():
    """Create a single entity"""
    crate = minimal_crate()
    props = {"name": "A dataset", "description": "The description of the dataset"}
    crate.add("Dataset", "#mydata", props)
    entity = crate.get("#mydata")
    for prop, val in props.items():
        assert entity[prop] == val


def test_prop_interface():
    """Iterating over an entity and using 'in' used to hang (issue #17)"""
    crate = minimal_crate()
    props = {"name": "A dataset", "description": "The description of the dataset"}
    crate.add("Dataset", "#mydata", props)
    entity = crate.get("#mydata")
    assert list(entity) == ["name", "description", "@id", "@type"]
    assert "name" in entity
    assert "range" not in entity
    assert len(entity) == 4


def test_modify_entity(tmp_path):
    """Modify an entity and see if the change is written out to the crate"""
    crate = minimal_crate()
    props = {"name": "A dataset", "description": "The description of the dataset"}
    crate.add("Dataset", "#mydata", props)
    entity = crate.get("#mydata")
    new_name = "A dataset with a new name"
    entity["name"] = new_name
    jsonf = Path(tmp_path) / "ro-crate-metadata.json"
    crate.write_json(tmp_path)
    with open(jsonf, "r") as jfh:
        jsonld = json.load(jfh)
        crate2 = TinyCrate(jsonld)
        e2 = crate2.get("#mydata")
        assert e2 is not None
        assert e2["name"] == new_name
    entity3 = crate.get("#mydata")
    assert entity3["name"] == new_name


def test_multiple_types():
    """@type can be a list"""
    crate = minimal_crate()
    crate.add(["File", "SoundRecording"], "audio.wav", {"name": "A recording"})
    crate.add("File", "text.txt", {"name": "A text"})
    audio = crate.get("audio.wav")
    text = crate.get("text.txt")
    assert audio.types == ["File", "SoundRecording"]
    assert audio.has_type("File")
    assert audio.has_type("SoundRecording")
    assert not audio.has_type("Dataset")
    assert text.types == ["File"]
    assert text.has_type("File")


def test_missing_type():
    """An entity without an @type shouldn't crash the library"""
    crate = TinyCrate(
        {
            "@context": "https://w3id.org/ro/crate/1.3/context",
            "@graph": [{"@id": "#untyped", "name": "No type"}],
        }
    )
    entity = crate.get("#untyped")
    assert entity.type is None
    assert entity.types == []
    assert not entity.has_type("Thing")
    assert len(crate.all()) == 1


def test_missing_id():
    """An entity without an @id is an error"""
    with pytest.raises(TinyCrateException):
        TinyCrate(
            {
                "@context": "https://w3id.org/ro/crate/1.3/context",
                "@graph": [{"@type": "Thing", "name": "No id"}],
            }
        )


def test_deref_all():
    """Follow references from single and multi-valued properties"""
    crate = minimal_crate()
    crate.add("Person", "#alice", {"name": "Alice"})
    crate.add("Person", "#bob", {"name": "Bob"})
    crate.add(
        "Dataset",
        "#ds",
        {
            "author": [{"@id": "#alice"}, {"@id": "#bob"}, {"@id": "#nobody"}],
            "publisher": {"@id": "#alice"},
            "keywords": ["one", "two"],
        },
    )
    ds = crate.get("#ds")
    assert [e.id for e in crate.deref_all(ds, "author")] == ["#alice", "#bob"]
    assert [e.id for e in crate.deref_all(ds, "publisher")] == ["#alice"]
    assert crate.deref_all(ds, "keywords") == []
    assert crate.deref_all(ds, "missing") == []
    assert ds.get_list("publisher") == [{"@id": "#alice"}]
    assert ds.get_list("keywords") == ["one", "two"]
    assert ds.get_list("missing") == []


def test_add_existing_id():
    """Adding an entity with an existing @id raises unless replace=True, which
    replaces it in place rather than duplicating it"""
    crate = minimal_crate()
    n = len(crate.graph)
    crate.add("Person", "#alice", {"name": "Alice"})
    with pytest.raises(TinyCrateException):
        crate.add("Person", "#alice", {"name": "Alice Smith"})
    assert crate.get("#alice")["name"] == "Alice"
    crate.add("Person", "#alice", {"name": "Alice Smith"}, replace=True)
    assert len(crate.graph) == n + 1
    assert crate.get("#alice")["name"] == "Alice Smith"
    assert len([e for e in crate.all() if e.id == "#alice"]) == 1
    # entities fetched after the replacement still write through to the graph
    alice = crate.get("#alice")
    alice["name"] = "A. Smith"
    reloaded = TinyCrate(json.loads(crate.json()))
    assert reloaded.get("#alice")["name"] == "A. Smith"


# A property can hold a plain value, a list of values, or a list of
# references to other entities. Each should survive every way of putting it
# into a crate and getting it back out.
PROP_VALUES = {
    "string": "A plain string",
    "list_of_strings": ["one", "two", "three"],
    "list_of_refs": [{"@id": "#alice"}, {"@id": "#bob"}, {"@id": "#carol"}],
}


def _crate_with_people():
    crate = minimal_crate()
    for name in ["alice", "bob", "carol"]:
        crate.add("Person", f"#{name}", {"name": name.title()})
    return crate


@pytest.mark.parametrize("kind", PROP_VALUES.keys())
@pytest.mark.parametrize("how", ["add", "setitem", "jsonld", "disk"])
def test_prop_value_range(kind, how, tmp_path):
    """Set a property via add(), entity[prop] =, a JSON-LD dict or a file on
    disk, and check the whole value comes back intact"""
    value = PROP_VALUES[kind]
    crate = _crate_with_people()
    if how == "setitem":
        crate.add("Dataset", "#ds", {})
        crate.get("#ds")["prop"] = value
    else:
        crate.add("Dataset", "#ds", {"prop": value})
    if how == "jsonld":
        crate = TinyCrate(json.loads(crate.json()))
    elif how == "disk":
        crate.write_json(tmp_path)
        crate = TinyCrate(tmp_path)

    ds = crate.get("#ds")
    assert ds["prop"] == value
    assert dict(ds.items())["prop"] == value
    assert [e for e in crate.all() if e.id == "#ds"][0]["prop"] == value
    expected_list = value if isinstance(value, list) else [value]
    assert ds.get_list("prop") == expected_list
    if kind == "list_of_refs":
        assert [e.id for e in crate.deref_all(ds, "prop")] == [
            "#alice",
            "#bob",
            "#carol",
        ]
        assert [e["name"] for e in crate.deref_all(ds, "prop")] == [
            "Alice",
            "Bob",
            "Carol",
        ]


def test_add_same_id_on_minimal_crate():
    """Adding entities with the same @id to a minimal crate: a second add()
    raises and leaves the crate unchanged; with replace=True the new entity
    replaces the old one entirely, so properties only on the old one are lost"""
    crate = minimal_crate()
    n = len(crate.graph)
    crate.add("Person", "#alice", {"name": "Alice", "email": "a@example.org"})
    before = crate.json()
    with pytest.raises(TinyCrateException):
        crate.add("Person", "#alice", {"name": "Alice Smith"})
    assert crate.json() == before
    crate.add("Person", "#alice", {"name": "Alice Smith"}, replace=True)
    crate.add(["Person", "Author"], "#alice", {"name": "A. Smith"}, replace=True)
    assert len(crate.graph) == n + 1
    assert [e.id for e in crate.all()].count("#alice") == 1
    alice = crate.get("#alice")
    assert alice.types == ["Person", "Author"]
    assert alice["name"] == "A. Smith"
    assert "email" not in alice
    # the minimal crate's own entities are protected too
    with pytest.raises(TinyCrateException):
        crate.add("Dataset", "./", {"name": "Another root"})


def _crate_with_duplicate_bob():
    jsonld = json.loads(minimal_crate().json())
    jsonld["@graph"] += [
        {"@id": "#bob", "@type": "Person", "name": "Bob", "email": "b@example.org"},
        {"@id": "#bob", "@type": "Person", "affiliation": {"@id": "#uni"}},
    ]
    return TinyCrate(jsonld)


def test_loaded_duplicate_ids_keep_first(caplog):
    """A loaded graph with a repeated @id isn't flattened JSON-LD. Keep the
    first occurrence and drop later ones, as ro-crate-js does, with a warning"""
    crate = _crate_with_duplicate_bob()
    bob = crate.get("#bob")
    assert bob["name"] == "Bob"
    assert bob["email"] == "b@example.org"
    assert "affiliation" not in bob
    assert [e.id for e in crate.all()].count("#bob") == 1
    assert [e["@id"] for e in crate.graph].count("#bob") == 1
    assert "#bob" in caplog.text


def test_loaded_duplicate_ids_edit(tmp_path):
    """Editing an entity that appeared twice leaves one consistent copy"""
    crate = _crate_with_duplicate_bob()
    crate.get("#bob")["name"] = "Robert"
    crate.write_json(tmp_path)
    reloaded = TinyCrate(tmp_path)
    names = [e.get("name") for e in reloaded.graph if e["@id"] == "#bob"]
    assert names == ["Robert"]
