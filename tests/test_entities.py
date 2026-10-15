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
