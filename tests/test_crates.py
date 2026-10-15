from pathlib import Path
from fuzz import random_text, random_property
import json
import datetime

from pytest_httpserver import HTTPServer

from tinycrate.tinycrate import (
    TinyCrate,
    minimal_crate,
    LICENSE_ID,
    LICENSE_NAME,
    LICENSE_DESCRIPTION,
    LICENSE_IDENTIFIER,
)


def test_minimal_crate():
    """Test for the date bug in a minimal crate"""
    isodate = datetime.datetime.now().isoformat()[:10]
    # create a crate with a known date
    crate = minimal_crate(date_published=isodate)
    r = crate.root()
    assert r["datePublished"] == isodate
    # create a crate which will supply its own date
    crate2 = minimal_crate()
    assert crate2 is not None
    r2 = crate.root()
    isodate2 = datetime.datetime.fromisoformat(r2["datePublished"])
    assert isodate2 is not None


def test_crate(tmp_path):
    """Build and save and reload a crate"""
    jcrate = minimal_crate()
    for i in range(1000):
        props = {"name": random_text(4), "description": random_text(11)}
        for j in range(30):
            prop, val = random_property()
            props[prop] = val
        jcrate.add("Dataset", f"#ds{i:05d}", props)
    jcrate.write_json(Path(tmp_path))
    jcrate2 = TinyCrate(source=tmp_path)
    for i in range(1000):
        eid = f"#ds{i:05d}"
        ea = jcrate.get(eid)
        eb = jcrate2.get(eid)
        assert ea.props == eb.props


def load_json(json_file):
    with open(json_file, "r") as fh:
        contents = fh.read()
    return json.loads(contents)


def test_load_file(crates):
    "Load from a JSON-LD file"
    cratedir = crates["textfiles"]
    jsonld_file = Path(cratedir) / "ro-crate-metadata.json"
    crate = TinyCrate(jsonld_file)
    tfile = crate.get("doc001/textfile.txt")
    contents = tfile.fetch()
    with open(Path(cratedir) / "doc001" / "textfile.txt", "r") as tfh:
        contents2 = tfh.read()
        assert contents == contents2
    assert crate.directory.samefile(cratedir)
    jsonld = load_json(jsonld_file)
    for json_ent in jsonld["@graph"]:
        entity = crate.get(json_ent["@id"])
        assert entity is not None
        for prop, val in entity.items():
            assert json_ent[prop] == val


def test_load_dir(crates):
    "Load from a directory containing a JSON-LD file"
    cratedir = crates["textfiles"]
    crate = TinyCrate(Path(cratedir))
    tfile = crate.get("doc001/textfile.txt")
    contents = tfile.fetch()
    with open(Path(cratedir) / "doc001" / "textfile.txt", "r") as tfh:
        contents2 = tfh.read()
        assert contents == contents2
    assert crate.directory.samefile(cratedir)
    jsonld_file = Path(cratedir) / "ro-crate-metadata.json"
    jsonld = load_json(jsonld_file)
    for json_ent in jsonld["@graph"]:
        entity = crate.get(json_ent["@id"])
        assert entity is not None
        for prop, val in entity.items():
            assert json_ent[prop] == val


def test_load_url(crates, httpserver: HTTPServer):
    "Load from a JSON-LD file on a URL"
    cratedir = crates["textfiles"]
    with open(Path(cratedir) / "ro-crate-metadata.json", "r") as fh:
        contents = fh.read()
    httpserver.expect_request("/ro-crate-metadata.json").respond_with_data(
        contents, content_type="application/json"
    )
    url = httpserver.url_for("/ro-crate-metadata.json")
    crate = TinyCrate(url)
    jsonld = json.loads(contents)
    for json_ent in jsonld["@graph"]:
        entity = crate.get(json_ent["@id"])
        assert entity is not None
        for prop, val in entity.items():
            assert json_ent[prop] == val


def test_load_utf8(crates):
    """Reads a textfile known to have utf-8 characters which cause
    encoding bugs on a Jupyter notebook on Windows"""
    cratedir = crates["utf8"]
    crate = TinyCrate(source=cratedir)
    tfile = crate.get("data/2-035-plain.txt")
    contents = tfile.fetch()
    # note: have to also explicitly set the encoding on this read so that
    # it doesn't also break the tests
    with open(
        Path(cratedir) / "data" / "2-035-plain.txt", "r", encoding="utf-8"
    ) as tfh:
        contents2 = tfh.read()
        assert contents == contents2


def test_minimal_crate_license():
    """The license entity should carry the real name, description and
    identifier, not placeholder strings"""
    crate = minimal_crate()
    license = crate.deref(crate.root(), "license")
    assert license is not None
    assert license.id == LICENSE_ID
    assert license["name"] == LICENSE_NAME
    assert license["description"] == LICENSE_DESCRIPTION
    assert license["identifier"] == LICENSE_IDENTIFIER


def test_legacy_jsonld_descriptor():
    """RO-Crate 1.0 crates used ro-crate-metadata.jsonld as the descriptor id"""
    jsonld = {
        "@context": "https://w3id.org/ro/crate/1.0/context",
        "@graph": [
            {
                "@id": "ro-crate-metadata.jsonld",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.0"},
            },
            {"@id": "./", "@type": "Dataset", "name": "Legacy crate"},
        ],
    }
    crate = TinyCrate(jsonld)
    assert crate.root()["name"] == "Legacy crate"


def test_utf8_metadata_roundtrip(tmp_path):
    """Non-ASCII metadata is written as UTF-8, unescaped, and reads back"""
    name = "Ngā mihi — 你好"
    crate = minimal_crate(name=name)
    crate.write_json(tmp_path)
    raw = (tmp_path / "ro-crate-metadata.json").read_bytes().decode("utf-8")
    assert name in raw
    assert name in crate.json()
    assert TinyCrate(tmp_path).root()["name"] == name


def test_utf8_metadata_over_http(httpserver: HTTPServer):
    name = "Ngā mihi — 你好"
    crate = minimal_crate(name=name)
    httpserver.expect_request("/ro-crate-metadata.json").respond_with_data(
        crate.json().encode("utf-8"), content_type="application/json"
    )
    crate2 = TinyCrate(httpserver.url_for("/ro-crate-metadata.json"))
    assert crate2.root()["name"] == name
