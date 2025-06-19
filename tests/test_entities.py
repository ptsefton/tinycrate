from pathlib import Path
import json
import sys
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
    """Create a single entity"""
    crate = minimal_crate()
    props = {"name": "A dataset", "description": "The description of the dataset"}
    crate.add("Dataset", "#mydata", props)
    entity = crate.get("#mydata")
    # This hangs
    for val in entity:
        print("Here", file=sys.stderr)
    # as does this
    if "name" in entity:
        pass

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
    """Adding an entity with an existing @id replaces it, not duplicates it"""
    crate = minimal_crate()
    n = len(crate.graph)
    crate.add("Person", "#alice", {"name": "Alice"})
    crate.add("Person", "#alice", {"name": "Alice Smith"})
    assert len(crate.graph) == n + 1
    assert crate.get("#alice")["name"] == "Alice Smith"
    assert len([e for e in crate.all() if e.id == "#alice"]) == 1
    # entities fetched after the replacement still write through to the graph
    alice = crate.get("#alice")
    alice["name"] = "A. Smith"
    reloaded = TinyCrate(json.loads(crate.json()))
    assert reloaded.get("#alice")["name"] == "A. Smith"
