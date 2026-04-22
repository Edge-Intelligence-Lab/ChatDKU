# ChatDKU Ingestion Wiki Plan

## Goal

Build a wiki-generation layer on top of the current ChatDKU ingestion pipeline so that data is not only chunked for retrieval, but also compiled into a persistent, human-readable knowledge layer.

The goal is not to replace vector search. The goal is to add a second layer that:

- organizes source content into stable wiki pages,
- accumulates cross-source knowledge over time,
- reduces repeated synthesis at query time,
- makes important entities, concepts, and policies easier to inspect and maintain.

## Why Borrow from `llm-wiki-agent`

The key idea worth borrowing is not the exact implementation, but the **compiled knowledge layer with cross-referenceable pages**:

- source files remain immutable,
- ingestion produces structured wiki pages,
- pages are summarized and linked ahead of time,
- contradictions and coverage gaps are surfaced during ingestion instead of only during retrieval.

This fits ChatDKU well because current ingestion already has:

- stable file-level metadata such as `file_path`, `file_name`, timestamps, and access fields,
- a node-generation stage in `update_data.py`,
- downstream vector stores in Chroma and Postgres.

So the missing piece is a **wiki layer** between raw documents and retrieval.

## What This Wiki Should Not Become

This wiki layer should **not** become:

- another copy of PostgreSQL rows in markdown form,
- another keyword-heavy index that increases retrieval complexity,
- a freeform LLM summary space with weak grounding.

If the wiki only stores semi-structured facts that are already present in Postgres, then it adds little value.  
The real advantage of the wiki is different:

- it summarizes source knowledge in real time during ingestion,
- it builds explicit cross-references between related pages,
- it creates a higher-level navigable knowledge layer for retrieval,
- it gives query-time retrieval a more precise target than raw chunks alone.

In other words, the wiki should be a **linked knowledge layer**, not just a second storage table.

## Recommended Architecture

Use a four-layer model:

1. **Source layer**
   - Existing website, PDF, XLSX, CSV, event, and scraped HTML files
   - Remains unchanged

2. **Node layer**
   - Existing `nodes.json`
   - Continues to support vector indexing and retrieval

3. **Wiki layer**
   - New generated markdown knowledge base
   - Built from source files and/or node groups
   - Adds summaries, references, and cross-page links

4. **Index / Retrieval layer**
   - Existing Chroma / Postgres / Redis
   - Optionally augmented later with wiki-derived nodes

In short:

`raw files -> update_data -> nodes.json -> wiki builder -> wiki pages -> optional wiki indexing`

## What the Wiki Should Contain

The wiki should not mirror every chunk. It should generate durable knowledge pages with useful cross-references.

Recommended page types:

- `sources/`
  - one page per source document or source unit
  - summary, key facts, links, metadata, open questions

- `entities/`
  - people, offices, programs, schools, centers, services

- `concepts/`
  - recurring ideas such as application process, curriculum, financial aid, permissions, event categories

- `policies/`
  - stable operational rules, deadlines, requirements, workflow-type information

- `overview/`
  - high-level synthesis by domain, such as admissions, academics, campus life, events

For ChatDKU, this is more useful than a generic research wiki because many user questions are domain-structured rather than purely semantic.

## Advantages and Limitations

### Main advantages

- **Better retrieval targets**
  - queries can retrieve higher-level wiki pages instead of only raw chunks
  - this is especially helpful for broad questions where users want synthesized guidance

- **Cross-referenceable knowledge**
  - related programs, offices, deadlines, policies, and concepts can be connected ahead of time
  - this gives retrieval more precision than isolated chunks

- **More maintainable knowledge surface**
  - humans can inspect and review wiki pages much more easily than vector rows or database records

- **Grounded synthesis during ingestion**
  - the system can summarize once, link once, and reuse that structure later

### Main limitations

- **Risk of hallucinated synthesis**
  - if the schema is too open, the LLM may invent unsupported summaries or relationships

- **Risk of duplicating existing storage**
  - if the wiki is only a structured fact dump, it becomes too similar to current Postgres metadata

- **Risk of retrieval complexity**
  - adding too many keywords, tags, or extra retrieval fields may complicate the system without clear gains

- **Risk of drift**
  - if wiki content is not tightly grounded in sources, it can drift away from raw documents and nodes

## Suggested Directory Structure

Inside `ChatDKU-ingestion`, a clean structure would be:

```text
ChatDKU-ingestion/
  docs/
    WIKI_INGESTION_PLAN.md
  schemas/
    wiki_page_schema.md
  wiki/
    index.md
    overview.md
    log.md
    sources/
    entities/
    concepts/
    policies/
    syntheses/
  graph/
    graph.json
    graph.html
  configs/
    wiki_rules.md
```

If you want to keep generated artifacts separate from planning docs, `wiki/` can later move under the main ChatDKU data directory instead.

## How It Should Fit the Current Ingestion

### Existing pipeline

Current ingestion is already split into:

- parsing and normalization in `update_data.py`
- vector loading in `load_chroma.py` and `load_postgres.py`
- keyword loadign in `load_redis.py`

### Recommended addition

Insert a new phase after `update_data.py`:

`update_data.py -> build_wiki.py -> load_chroma.py / load_postgres.py / load_redis.py`

That means:

- `update_data.py` remains the canonical parser
- wiki generation reads normalized data instead of reparsing everything differently
- vector loaders stay mostly unchanged

This keeps responsibilities clear.

## Core Design Principles

### 1. The wiki should be document-aware, not chunk-aware

Chunking is useful for vector retrieval but too low-level for a wiki.

The wiki builder should group nodes back into a source-level or section-level view using metadata such as:

- `file_path`
- `file_name`
- `page_number`
- access fields
- source type

### 2. The wiki should be domain-shaped

Do not make only generic `entity` and `concept` pages.

For ChatDKU, you likely want domain-aware categories such as:

- admissions
- academics
- student life
- events
- administration
- services

### 3. The wiki should be conservative

Only stable, supported information should become wiki facts.

This is especially important because some current issues already involve:

- mixed program boundaries,
- ambiguous sources,
- event-like temporary pages,
- public vs internal access differences.

### 4. The wiki should be traceable

Every wiki page should keep source references back to the original files.

This is critical for maintenance and debugging.

### 5. The wiki should enforce source-grounded truth

The agent should treat source-backed content as the only ground truth.

That means:

- every important statement in the wiki should be traceable to one or more source references,
- unsupported synthesis should never be written as if it were a verified fact,
- if the source does not clearly support a claim, the page should mark it as uncertain, unresolved, or omit it.

This is one of the most important safeguards against hallucination.

### 6. The wiki should be semi-structured, not fully rigid and not fully freeform

The wiki should not be reduced to database-style fields only, because then it loses the main value of `llm-wiki-agent`: summarization plus linked knowledge.

But it also should not be open-ended prose.

The right balance is:

- structured fields for grounding, references, and provenance,
- controlled sections for summaries and cross-references,
- explicit source-backed links between related pages.

## Recommended Page Format

Each wiki page should contain:

- title
- page type
- tags/domain
- source references
- last updated timestamp
- body sections

Suggested fields and sections:

- `title`
- `page_type`
- `domain`
- `source_refs`
- `ground_truth_refs`
- `cross_refs`
- `last_updated`
- `status`

- Summary
- Verified Facts / Ground Truth
- Reference Context
- Related pages
- Open questions or ambiguity notes

This is enough to make the wiki useful without collapsing it into a database replica.

## Semi-Structured Schema Direction

The first schema should explicitly constrain the most error-prone parts:

### 1. Source grounding

Each page should carry source references in a stable format, for example:

- source file path
- canonical source URL if available
- source type
- last updated timestamp

### 2. Ground-truth blocks

Important claims should be stored as grounded entries, not only prose.  
Examples:

- requirement
- deadline
- contact
- policy statement
- scope note

Each such item should point back to a source reference.

This is the main mechanism that prevents the wiki from drifting into unsupported summary text.

### 3. Cross references

Cross-reference is still a core value and should remain first-class.

But references should also be structured enough to be machine-usable.  
Examples:

- related page id / slug
- relation type
- evidence source

This makes later graph building and retrieval much easier.

### 4. Reference context

For each grounded item or summary section, the schema should make room for a short supporting context block, so that later retrieval can pull not only the final wiki sentence, but also the nearby evidence.

### 5. Contradiction tracking

The agent should explicitly check whether a new source conflicts with existing wiki content or with other sources already linked to the same page.

This should not be treated as an optional cleanup step. It should be part of the ingestion contract.

At minimum, the schema should support:

- a contradiction note,
- the conflicting source references,
- a short explanation of what conflicts,
- a status such as `resolved`, `unresolved`, or `needs_review`.

If multiple sources disagree, the wiki should preserve the disagreement instead of collapsing them into a single synthesized claim.

## Recommended Schema Philosophy

The initial schema should therefore aim for:

- **more structure than markdown notes**
- **less rigidity than a relational table**

The wiki page should be:

- readable by humans,
- traceable to raw sources,
- linkable across pages,
- simple enough for the LLM to fill consistently,
- structured enough to support retrieval and validation.

## Key Steps to Implement

### Phase 1: Define the wiki contract

Before writing code, define:

- page types
- naming rules
- frontmatter fields
- reference format
- cross-reference format
- ground-truth block format
- contradiction block format
- what counts as a source page vs entity page vs policy page
- what content is allowed to be promoted into stable wiki knowledge

This should live in a single schema/rules document.

### Phase 2: Build source-page generation

Start with the easiest, most deterministic layer:

- one wiki page per source file
- summarize and normalize content
- preserve metadata and source path
- attach structured references and cross-reference slots
- enforce that all page content is source-grounded
- surface contradictions instead of resolving them prematurely

This gives immediate value and low hallucination risk.

### Phase 3: Build cross-source aggregation

Once source pages work, add higher-level aggregation:

- entity extraction
- concept grouping
- policy grouping
- overview synthesis by domain
- explicit cross-reference generation between related pages
- contradiction detection across related source pages

This is where `llm-wiki-agent` ideas become most useful.

### Phase 4: Add validation

You need a lightweight wiki quality pass:

- missing source references
- malformed reference blocks
- broken links
- duplicate entities
- conflicting facts
- orphan pages
- claims without clear ground-truth support
- summaries that overstate what the cited sources actually say

This should be treated as part of ingestion quality, not an optional extra.

### Phase 5: Optional graph layer

Once wiki pages are stable, build:

- deterministic links from explicit cross references
- optional inferred links later

This is useful, but not required for the first version.

## Minimal First Version

To keep scope realistic, the first version should only do:

1. generate `wiki/sources/*.md` from normalized source files
2. include structured source references and grounded fact blocks
3. include cross-reference fields even if link generation is initially simple
4. include contradiction notes when sources disagree
5. generate `wiki/index.md`
6. generate one `wiki/overview.md`
7. keep source traceability

Do **not** start with:

- full entity graph,
- contradiction resolution,
- automatic healing,
- query-time wiki synthesis storage

Those can come later.

## How This Helps Retrieval

The wiki layer can improve retrieval in two ways:

1. **Human-facing maintenance**
   - easier to inspect what data exists
   - easier to spot wrong or mixed knowledge

2. **Machine-facing retrieval**
   - wiki pages can later be indexed as a second retrieval corpus
   - cross-referenced wiki pages can give retrieval more precise and semantically richer targets
   - this may support more stable answers for high-level questions than raw chunk search alone

That means the wiki is both an operational tool and a retrieval asset.

## Main Risks

### Over-summarization

If the wiki abstracts too aggressively, it may lose important details that still matter in retrieval.

### Mixing unstable and stable information

Event pages, temporary notices, and program-specific pages should not all be promoted equally.

### Duplicated truth layers

If the wiki and nodes diverge, maintenance becomes harder.

To avoid this:

- raw files remain source of truth,
- nodes remain retrieval truth,
- wiki is a compiled interpretation layer with explicit provenance.

### Collapsing contradictory sources into one answer

If the agent tries to "smooth over" disagreement between sources, the wiki may look cleaner but become less trustworthy.

To avoid this:

- preserve conflicting source-backed claims,
- attach contradiction notes directly to affected pages,
- avoid writing a single unified conclusion unless sources actually support it.

## Recommended Build Order

1. Finalize wiki schema and page taxonomy
2. Define ground-truth and contradiction formats
3. Build source-page generator from current ingestion outputs
4. Add index and overview generation
5. Add validation/linting
6. Add domain aggregation pages
7. Add graph only if the wiki proves stable

## Final Recommendation

Yes, the `llm-wiki-agent` approach is worth borrowing, but in a **ChatDKU-adapted** form.

The best structure is:

- keep current ingestion as the parsing/indexing backbone,
- add a wiki builder as a separate stage,
- use a semi-structured schema from the start,
- preserve explicit references, cross-references, and source grounding,
- require the agent to check for contradictory sources during wiki generation,
- require grounded facts instead of unsupported synthesized claims,
- avoid turning the wiki into another Postgres-like storage layer,
- then gradually add aggregated entity/concept/policy pages.

This gives you a maintainable path toward a persistent linked knowledge layer without disrupting the current vector ingestion pipeline.
