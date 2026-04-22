# Wiki Main Document Schema (V0)

This is the initial semi-structured contract for the generated consolidated wiki document.

## Main document sections

1. `Build Log`
2. `Domain Breakdown`
3. `Source Inventory`
4. `Validation`

## Per-source block format

Each source entry in `Source Inventory` should contain:

- `page_id`
- `domain`
- `status`
- `node_count`
- `last_updated`
- `Source Refs`
- `Source Log`
- `Digest`
- `Verified Facts`
- `Contradictions`
- `Reference Context`

## Source reference format

Each entry should include:

- `data_path`
- `file_path`
- `file_name`
- `source_type`
- `last_modified` (if present)

## Grounded fact format

Each fact should include:

- `label`
- `value`
- `evidence`
- `source_ref`

## Contradiction note format

Each note should include:

- `label`
- `status`: `resolved` / `unresolved` / `needs_review`
- `note`: short explanation
- `refs`: conflicting source refs
