from __future__ import annotations
from pathlib import Path, PurePath
import json
import requests
import datetime
from urllib.parse import unquote, urljoin
from typing import Any, Optional, Union, Tuple, Dict, Generator

from tinycrate.jsonld_context import JSONLDContextResolver

RO_CRATE_PROFILE = "https://w3id.org/ro/crate/1.3"
RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.3/context"

LICENSE_ID = "https://creativecommons.org/licenses/by-nc-sa/3.0/au/"
LICENSE_DESCRIPTION = (
    "This work is licensed under the Creative Commons "
    "Attribution-NonCommercial-ShareAlike 3.0 Australia License. "
    "To view a copy of this license, visit "
    "http://creativecommons.org/licenses/by-nc-sa/3.0/au/ or send a letter to "
    "Creative Commons, PO Box 1866, Mountain View, CA 94042, USA."
)
LICENSE_IDENTIFIER = "https://creativecommons.org/licenses/by-nc-sa/3.0/au/"
LICENSE_NAME = "Attribution-NonCommercial-ShareAlike 3.0 Australia (CC BY-NC-SA 3.0 AU)"


class TinyCrateException(Exception):
    pass


# todo: make a type alias for an entity property - this should be
# - a str
# - a list
# - a dict


class TinyEntity:
    def __init__(self, crate: TinyCrate, ejsonld: dict[str, Any]) -> None:
        self.crate = crate
        # @type may be a single string or a list of strings; use .types or
        # has_type() to handle both
        self.type = ejsonld.get("@type")
        self.id = ejsonld["@id"]
        self.props = dict(ejsonld)
        # Store index in parent crate's graph for later updates
        self._graph_index = None
        if self.id in self.crate._id_index:
            self._graph_index = self.crate._id_index[self.id][0]

    def __getitem__(self, prop: str) -> Union[str, Dict, None]:
        return self.props.get(prop, None)

    def __setitem__(self, prop: str, val: Union[str, Dict]) -> None:
        self.props[prop] = val
        # Update the corresponding entity in the parent crate's graph
        if self._graph_index is not None:
            self.crate.graph[self._graph_index][prop] = val

    @property
    def types(self) -> list[str]:
        """This entity's @type values as a list"""
        if self.type is None:
            return []
        if isinstance(self.type, list):
            return self.type
        return [self.type]

    def has_type(self, t: str) -> bool:
        """True if t is one of this entity's @type values"""
        return t in self.types

    def get_dict(self, prop: str) -> Optional[Dict]:
        """get a property on this entity but only return it if it's a Dict"""
        val = self[prop]
        if type(val) is dict:
            return val
        return None

    def get_list(self, prop: str) -> list[Any]:
        """get a property on this entity as a list, whether it has a single
        value or a list of values. Returns [] if the property isn't set"""
        val = self[prop]
        if val is None:
            return []
        if isinstance(val, list):
            return val
        return [val]

    def items(self) -> Generator[Tuple[str, Union[str, Dict]]]:
        for k, v in self.props.items():
            yield k, v

    def fetch(self) -> str:
        """Get this entity's content as text. Relative @ids are resolved
        against the crate's URL if it was loaded from one, otherwise against
        its directory. Content is decoded as UTF-8 unless an http response
        declares a charset"""
        url = self._url()
        if url is not None:
            response = self._fetch_http(url)
            charset = _charset(response.headers.get("content-type", ""))
            try:
                return response.content.decode(charset or "utf-8")
            except (UnicodeDecodeError, LookupError) as e:
                raise TinyCrateException(f"Couldn't decode {url}: {e}")
        try:
            with open(self._path(), "r", encoding="utf-8") as fh:
                content = fh.read()
                return content
        except Exception as e:
            raise TinyCrateException(f"File read failed: {e}")

    def fetch_bytes(self) -> bytes:
        """Get this entity's content as bytes, for binary files"""
        url = self._url()
        if url is not None:
            return self._fetch_http(url).content
        try:
            return self._path().read_bytes()
        except Exception as e:
            raise TinyCrateException(f"File read failed: {e}")

    def _url(self) -> Optional[str]:
        """The absolute URL to fetch this entity from, or None if it should
        be fetched from the crate directory"""
        if self.id[:4] == "http":
            return self.id
        if self.crate.base_url is not None:
            return urljoin(self.crate.base_url, self.id)
        return None

    def _path(self) -> Path:
        if self.crate.directory is None:
            # maybe use pwd for this?
            raise TinyCrateException("Can't load file: no crate directory")
        # @ids are URI references, so file paths may be percent-encoded
        return Path(self.crate.directory) / unquote(self.id)

    def _fetch_http(self, url: str) -> requests.Response:
        response = requests.get(url)
        if response.ok:
            return response
        raise TinyCrateException(
            f"http request to {url} failed with status {response.status_code}"
        )


def _charset(content_type: str) -> Optional[str]:
    """Get the charset parameter from a Content-Type header, if any"""
    for param in content_type.split(";")[1:]:
        key, _, value = param.strip().partition("=")
        if key.lower() == "charset":
            return value.strip("\"'")
    return None


class TinyCrate:
    """Object representing an RO-Crate"""

    def __init__(self, source: Union[str, Path, None] = None) -> None:
        self.directory: Optional[Path] = None
        # URL of the ro-crate-metadata.json, if the crate was loaded from one
        self.base_url: Optional[str] = None
        self._context_resolver: Optional[JSONLDContextResolver] = None
        self._id_index: dict[str, tuple[int, dict]] = {}
        if source is not None:
            if isinstance(source, PurePath):
                self._open_path(source)
            else:
                if type(source) is str:
                    if source.startswith(("https://", "http://")):
                        self._open_url(source)
                    else:
                        self._open_path(Path(source))
                else:
                    if type(source) is dict:
                        self._open_jsonld(source)
                    else:
                        t = type(source)
                        raise TinyCrateException(
                            "can only init from a str, Path or "
                            f"JSON-LD dict (got a {t})"
                        )
        else:
            self.context = RO_CRATE_CONTEXT
            self.graph: list[dict] = []

    def _open_jsonld(self, jsonld: dict[str, Any]) -> None:
        """Load a dict representing a JSON-LD"""
        if "@context" not in jsonld:
            raise TinyCrateException("No @context in json-ld")
        if "@graph" not in jsonld:
            raise TinyCrateException("No @graph in json-ld")
        self.context = jsonld["@context"]
        self.graph = jsonld["@graph"]
        for e in self.graph:
            if "@id" not in e:
                raise TinyCrateException(f"Entity with no @id in @graph: {e}")
        self._id_index = {e["@id"]: (i, e) for i, e in enumerate(self.graph)}

    def _open_path(self, path: Path) -> None:
        """Load a file or Path, which can be the jsonld file or its
        containing directory. Sets the directory property accordingly."""
        if path.is_dir():
            self.directory = path
            path = path / "ro-crate-metadata.json"
        else:
            self.directory = path.parent
        with open(path, "r", encoding="utf-8") as fh:
            jsonld = json.load(fh)
            self._open_jsonld(jsonld)

    def _open_url(self, url: str) -> None:
        """Load a crate from the url of the metadata.json, or of the crate
        root if the url ends with a /"""
        if url.endswith("/"):
            url = url + "ro-crate-metadata.json"
        response = requests.get(url)
        if response.ok:
            # json.loads detects UTF-8/16/32 from bytes, which is safer than
            # the encoding requests guesses for response.text
            jsonld = json.loads(response.content)
            self._open_jsonld(jsonld)
            self.base_url = url
        else:
            raise TinyCrateException(
                f"http request to {url} failed with status {response.status_code}"
            )

    @property
    def context_resolver(self) -> JSONLDContextResolver:
        """Lazily initialize the context resolver to avoid unnecessary processing on initialization"""
        if self._context_resolver is None:
            self._context_resolver = JSONLDContextResolver(self.context)
        return self._context_resolver

    def set_directory(self, directory: Path) -> None:
        """Set the directory for this crate. Relative @ids will be fetched
        from this directory even if the crate was loaded from a URL"""
        self.directory = directory
        self.base_url = None

    def add(self, t: Union[str, list[str]], i: str, props: dict[str, Any]) -> None:
        """Add an entity. If an entity with this @id already exists it is
        replaced, as @ids must be unique in an RO-Crate"""
        json_props = dict(props)
        json_props["@id"] = i
        json_props["@type"] = t
        if i in self._id_index:
            index, _ = self._id_index[i]
            self.graph[index] = json_props
        else:
            self.graph.append(json_props)
            index = len(self.graph) - 1
        self._id_index[i] = (index, json_props)

    def all(self) -> list[TinyEntity]:
        return [TinyEntity(self, e) for e in self.graph]

    def get(self, i: str) -> Optional[TinyEntity]:
        entry = self._id_index.get(i)
        if entry:
            _, e = entry  # unpacking (index, entity) tuple
            return TinyEntity(self, e)
        return None

    def deref(self, entity: TinyEntity, prop: str) -> Optional[TinyEntity]:
        """Given an entity and a property, try to follow the @id. Only works
        for single-valued properties: use deref_all for lists"""
        id_dict: Optional[Dict] = entity.get_dict(prop)
        if id_dict is not None:
            ref: Optional[str] = id_dict.get("@id", None)
            if ref is not None:
                return self.get(ref)
        return None

    def deref_all(self, entity: TinyEntity, prop: str) -> list[TinyEntity]:
        """Given an entity and a property which may have one value or a list,
        return every entity in this crate referenced by an @id. Literal
        values and references to entities not in the crate are skipped"""
        targets = []
        for val in entity.get_list(prop):
            if isinstance(val, dict) and "@id" in val:
                target = self.get(val["@id"])
                if target is not None:
                    targets.append(target)
        return targets

    def root(self) -> TinyEntity:
        """Find the Root Data Entity via the metadata descriptor, falling
        back to the legacy ro-crate-metadata.jsonld id used by RO-Crate 1.0"""
        metadata = self.get("ro-crate-metadata.json")
        if metadata is None:
            metadata = self.get("ro-crate-metadata.jsonld")
        if metadata is None:
            raise TinyCrateException("no ro-crate-metadata.json entity")
        root = self.deref(metadata, "about")
        if root is None:
            raise TinyCrateException("Missing or malformed root entity")
        return root

    def json(self) -> str:
        return json.dumps(
            {"@context": self.context, "@graph": self.graph},
            indent=2,
            ensure_ascii=False,
        )

    def write_json(self, crate_dir: Optional[Path] = None) -> None:
        """Write the json-ld to a file"""
        if crate_dir is None:
            crate_dir = self.directory or Path(".")
        crate_dir.mkdir(parents=True, exist_ok=True)
        with open(crate_dir / "ro-crate-metadata.json", "w", encoding="utf-8") as jfh:
            json.dump(
                {"@context": self.context, "@graph": self.graph},
                jfh,
                indent=2,
                ensure_ascii=False,
            )

    def resolve_term(self, term: str) -> str:
        """Resolve a JSON-LD term like 'name' or 'schema:name' to its full IRI

        Args:
            term (str): The term to resolve, e.g., 'name' or 'schema:name'

        Returns:
            str: The full IRI for the term, or the original term if not found
        """
        return self.context_resolver.resolve_term(term)


def minimal_crate(
    name: str = "Minimal crate",
    description: str = "Minimal crate",
    date_published: Optional[str] = None,
) -> TinyCrate:
    """Create ROCrate json with the minimal structure. Allowing the caller
    to pass in the datePublished to ensure that this can be run
    deterministically in tests"""
    crate = TinyCrate()
    dp: str = ""
    if date_published is None:
        dp = datetime.datetime.now().isoformat()[:10]
    else:
        dp = date_published
    crate.add(
        "Dataset",
        "./",
        {
            "name": name,
            "description": description,
            "license": {"@id": LICENSE_ID},
            "datePublished": dp,
        },
    )
    crate.add(
        "CreativeWork",
        LICENSE_ID,
        {
            "name": LICENSE_NAME,
            "description": LICENSE_DESCRIPTION,
            "identifier": LICENSE_IDENTIFIER,
        },
    )
    crate.add(
        "CreativeWork",
        "ro-crate-metadata.json",
        {
            "about": {"@id": "./"},
            "conformsTo": {"@id": RO_CRATE_PROFILE},
        },
    )
    return crate
