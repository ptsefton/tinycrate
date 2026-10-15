from pytest_httpserver import HTTPServer

from tinycrate.tinycrate import TinyCrate, minimal_crate


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
