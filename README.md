# tinycrate

A minimal RO-Crate library in Python with an emphasis on working transparently
with crates on disk and crates over the network.

## Usage

    from tinycrate.tinycrate import TinyCrate

    tc_from_json = TinyCrate(jsonld)
    tc_from_url = TinyCrate(url)
    tc_from_disk = TinyCrate(crate_path)

    r = tc_from_url.root()

    for entity in tc_from_url.all():
        for prop, value in entity.items():
            print(f"{prop}: {value}")
        if entity.has_type("File"):
            contents = entity.fetch()
            print(contents)

`url` can be the URL of the `ro-crate-metadata.json` or of the crate root
(ending in `/`). Relative `@id`s are fetched from the crate's directory or URL.

Any property can have a single value or a list. `entity.types` and
`entity.get_list(prop)` always return lists, and `crate.deref_all(entity, prop)`
follows every `{"@id": ...}` reference in a property:

    for author in tc_from_url.deref_all(r, "author"):
        print(author["name"])

Use `entity.fetch_bytes()` for binary files.

## Development

Install the package and its dev dependencies with [uv](https://docs.astral.sh/uv/),
which creates a `.venv` from `pyproject.toml` and `uv.lock`:

```
uv sync
```

Run the tests and checks:

```
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

Or install the pre-commit hooks to run ruff and mypy on each commit:

```
uv run pre-commit install
```
