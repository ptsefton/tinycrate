from pytest_httpserver import HTTPServer

import pytest
from tinycrate.tinycrate import TinyCrate, TinyCrateException, minimal_crate


def test_fetch_from_url(crates, httpserver: HTTPServer):
    # test http endpoint with some content
    contents = """
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
"""
    httpserver.expect_request("/textfileonurl.txt").respond_with_data(
        contents, content_type="text/plain"
    )

    cratedir = crates["textfiles"]
    crate = TinyCrate(cratedir)
    # add an entity to the crate with the endpoint URL as the id
    urlid = httpserver.url_for("/textfileonurl.txt")
    crate.add("File", urlid, {"name": "textfileonurl.txt"})
    # get the entity and try to fetch
    efile = crate.get(urlid)
    contents2 = efile.fetch()
    assert contents == contents2


def test_fetch_percent_encoded_id(tmp_path):
    """File @ids are URI references, so spaces etc are percent-encoded"""
    datadir = tmp_path / "data"
    datadir.mkdir()
    (datadir / "my file.txt").write_text("spaces in the name", encoding="utf-8")
    (datadir / "plain.txt").write_text("dot slash prefix", encoding="utf-8")
    crate = minimal_crate()
    crate.add("File", "data/my%20file.txt", {"name": "my file.txt"})
    crate.add("File", "./data/plain.txt", {"name": "plain.txt"})
    crate.write_json(tmp_path)
    crate2 = TinyCrate(tmp_path)
    assert crate2.get("data/my%20file.txt").fetch() == "spaces in the name"
    assert crate2.get("./data/plain.txt").fetch() == "dot slash prefix"


def test_fetch_relative_from_url_crate(httpserver: HTTPServer):
    """Relative @ids in a crate loaded over http resolve against its URL"""
    crate = minimal_crate()
    crate.add("File", "data/my%20file.txt", {"name": "my file.txt"})
    httpserver.expect_request("/crate/ro-crate-metadata.json").respond_with_data(
        crate.json(), content_type="application/json"
    )
    httpserver.expect_request("/crate/data/my file.txt").respond_with_data(
        "remote contents", content_type="text/plain"
    )
    for url in [
        httpserver.url_for("/crate/ro-crate-metadata.json"),
        httpserver.url_for("/crate/"),
    ]:
        crate2 = TinyCrate(url)
        assert crate2.base_url == httpserver.url_for("/crate/ro-crate-metadata.json")
        assert crate2.get("data/my%20file.txt").fetch() == "remote contents"


BINARY = bytes(range(256))


def test_fetch_bytes_file(tmp_path):
    """Binary files can be fetched with fetch_bytes"""
    (tmp_path / "image.bin").write_bytes(BINARY)
    crate = minimal_crate()
    crate.add("File", "image.bin", {"name": "binary"})
    crate.write_json(tmp_path)
    crate2 = TinyCrate(tmp_path)
    assert crate2.get("image.bin").fetch_bytes() == BINARY


def test_fetch_bytes_http(httpserver: HTTPServer):
    httpserver.expect_request("/image.bin").respond_with_data(
        BINARY, content_type="application/octet-stream"
    )
    crate = minimal_crate()
    url = httpserver.url_for("/image.bin")
    crate.add("File", url, {"name": "binary"})
    assert crate.get(url).fetch_bytes() == BINARY


def test_fetch_utf8_http(httpserver: HTTPServer):
    """text/plain with no charset should be read as UTF-8, not ISO-8859-1"""
    text = "Ngā mihi — 你好 — Ünïcödé"
    httpserver.expect_request("/nocharset.txt").respond_with_data(
        text.encode("utf-8"), content_type="text/plain"
    )
    httpserver.expect_request("/latin1.txt").respond_with_data(
        "Ünïcödé".encode("iso-8859-1"), content_type="text/plain; charset=ISO-8859-1"
    )
    crate = minimal_crate()
    for path in ["/nocharset.txt", "/latin1.txt"]:
        crate.add("File", httpserver.url_for(path), {})
    assert crate.get(httpserver.url_for("/nocharset.txt")).fetch() == text
    assert crate.get(httpserver.url_for("/latin1.txt")).fetch() == "Ünïcödé"


def test_fetch_non_http_iri(tmp_path):
    """Absolute IRIs with other schemes can't be fetched, and relative paths
    that happen to start with 'http' are still files"""
    (tmp_path / "httpdocs").mkdir()
    (tmp_path / "httpdocs" / "page.txt").write_text("local", encoding="utf-8")
    crate = minimal_crate()
    crate.add("File", "httpdocs/page.txt", {})
    crate.add("File", "arcp://name,corpus/data/file.txt", {})
    crate.write_json(tmp_path)
    crate2 = TinyCrate(tmp_path)
    assert crate2.get("httpdocs/page.txt").fetch() == "local"
    with pytest.raises(TinyCrateException):
        crate2.get("arcp://name,corpus/data/file.txt").fetch()
