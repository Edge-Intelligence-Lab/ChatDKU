# Wiki Build Rules (V0)

## Grounding

- Source-backed content is the only trusted truth.
- Do not write unsupported conclusions as verified facts.
- Keep `source_ref` for every extracted grounded fact.

## Scope

- V0 generates one consolidated `wiki/main.md`.
- `entities/`, `concepts/`, and `policies/` are reserved for later phases.

## Contradictions

- Preserve conflicting source-backed claims.
- Mark contradiction status as `unresolved` unless manually reviewed.

## Traceability

- The main wiki document must include a source reference section for every source entry.
- Keep reference context snippets for maintenance and debugging.
- Keep source logs such as data path, access metadata, and chunking hints in the main document.
