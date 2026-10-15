# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- New crates default to RO-Crate 1.3
- `root()` falls back to the legacy RO-Crate 1.0 `ro-crate-metadata.jsonld`
  descriptor
- Multi-valued `@type` support: `TinyEntity.types` and `has_type()`
- Multi-valued properties: `TinyEntity.get_list()` and `TinyCrate.deref_all()`
- Entities with no `@type` no longer raise `KeyError`; entities with no `@id`
  raise `TinyCrateException`
- `fetch()` decodes percent-encoded `@id`s, and crates loaded from a URL fetch
  relative `@id`s from that URL; a URL ending in `/` loads the crate root
- `fetch_bytes()` for binary content; UTF-8 used consistently for metadata
  and for http text with no declared charset
- `add()` with an existing `@id` replaces the entity instead of duplicating it
- Fixed placeholder license fields in `minimal_crate()`
- Iterating over a `TinyEntity` or using `in` no longer loops forever (#17)
- `resolve_term()` passes through any absolute IRI, not just http(s)
- `fetch()` only goes to the network for http(s) `@id`s; other absolute IRIs
  such as `arcp://` raise `TinyCrateException`

## [0.1.5]

Performance improvements to TinyEntity and TinyCrate

## [0.1.2]

Fixed auto date bug, added type annotations to tinycrate.py

## [0.1.1]

Fixed Windows encoding bugs, added context resolver and CI, made it able to
load a completey networked crate

## [0.1.0]

Initial version broken out from rocrate-tabular
