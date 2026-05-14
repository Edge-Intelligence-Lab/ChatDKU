# ChatDKU LLM Wiki Agent Schema

This file defines how an agent should maintain the ChatDKU wiki generated from ingestion outputs.

## Purpose

The ChatDKU wiki is a compiled knowledge layer built from normalized `nodes.json` outputs. It does not replace Chroma, Redis, or Postgres. It adds a persistent markdown layer that can accumulate source-grounded summaries, entities, contradictions, and high-level overviews.

## Three layers

- `raw source documents`
  - Immutable source of truth.
  - Produced and normalized by the existing ChatDKU ingestion pipeline.
- `nodes.json`
  - Canonical normalized intermediate artifact.
  - Remains the source for vector, keyword, and relational loaders.
- `wiki/`
  - LLM-maintained markdown knowledge layer.
  - Agents may update this layer, but must preserve source grounding.

## Current generated layout

- `wiki/index.md`
- `wiki/overview.md`
- `wiki/main.md`
- `wiki/validation_report.md`
- `wiki/sources/*.md`
- `wiki/entities/*.md`
- `graph/graph.json`
- `graph/pages.json`

## Ingest workflow

When asked to ingest or rebuild the wiki:

1. Read the latest `nodes.json`.
2. Rebuild source pages in `wiki/sources/`.
3. Rebuild entity pages in `wiki/entities/`.
4. Update `wiki/index.md` and `wiki/overview.md`.
5. Recompute `graph/graph.json` and `graph/pages.json`.
6. Regenerate `wiki/validation_report.md`.
7. Preserve contradictions instead of overwriting them.

## Query workflow

When asked a question against the wiki:

1. Read `wiki/index.md` and `wiki/overview.md` first.
2. Navigate to relevant `wiki/sources/*.md` and `wiki/entities/*.md` pages.
3. Prefer source-backed claims under `## Grounded Facts`.
4. If contradictions exist, surface them explicitly.
5. Do not state unsupported synthesis as verified fact.

## Lint workflow

When asked to lint or review the wiki:

- Check for missing summaries.
- Check for missing source references.
- Check for broken cross-references.
- Check for duplicate source pages.
- Check for pages with no inbound links.
- Check for unresolved contradictions.

## Hard rules

1. Source-backed content is the only trusted truth.
2. `nodes.json` and raw documents are immutable inputs.
3. Contradictions must be recorded, not silently merged away.
4. Every wiki page must keep traceable source references.
5. Agent-written prose should stay conservative and inspectable.
6. Query-time synthesis can be saved back into the wiki only if the page clearly cites its supporting source pages.

## Known current limitation

This implementation is currently deterministic and heuristic-first. It builds a persistent wiki structure, but it does not yet run an autonomous LLM maintenance loop during ingest. Agent-assisted updating is the next phase, not the current baseline.
