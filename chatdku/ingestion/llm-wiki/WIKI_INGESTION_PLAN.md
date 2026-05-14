# ChatDKU LLM Wiki Plan (DKU-Specific Index Design)

## Goal

Build a DKU-specific wiki layer that acts as a **natural-language index** over the advising knowledge base.

This wiki is not the retrieval engine and not a second bulletin. Its job is to:

- give a compact, general orientation to a topic,
- classify the topic in a DKU-specific way,
- normalize overlapping sources into clusters,
- route the reader to the best detailed source when needed.

## What changed in the design

The first design direction was too close to a detailed knowledge compendium.

That is the wrong target for ChatDKU because:

- DKU already has richer detailed materials such as the bulletin, handbook, manuals, and PDFs,
- the source base is highly duplicated across website, slide deck, FAQ, handbook, and form surfaces,
- the LLM should not read a huge page first if a thin topic index can route it to the correct source.

So the correct design target is:

- `general index first`
- `detail source second`

## What the source base actually looks like

Inspection of `/datapool/chat_dku_advising` shows the knowledge base is dominated by:

- `box_sync/ChatDKU Materials`
- `ChatDKU_Files`
- `UG_Updates`
- `dku_website/*`
- `event_data/*`

The highest-density materials are not generic webpages. They are:

- `ug_bulletin_2025-2026.pdf`
- `Current Student Handbook.pdf`
- `Faculty Advisor Manual.docx`
- `Understanding Major Declaration.pptx / pdf`
- `Registration Guide - Student Self-service Center.pdf`
- `DKU UG Signature Work Handbook`
- `SW Academic Calendar`
- `Advising FAQ`
- `CRNC FAQ`
- `Schedule Builder User Guide`
- multiple spreadsheets and working materials

This means the wiki must model:

- topic overlap,
- source duplication,
- authority order,
- version drift,
- routing value.

## DKU-specific design principle

The primary unit should be the **topic** a student or advisor is trying to understand, not the document and not the atomic fact.

Examples:

- `major declaration`
- `registration planning`
- `signature work`
- `leave of absence`
- `academic advising`
- `course substitution`

For each topic, the wiki should answer only the minimum index questions:

- what is this topic,
- who is it for,
- which source cluster covers it,
- which source should be opened first for detail,
- what related topics are nearby.

## Page model

Use four DKU-specific page types:

1. `topic_index`
   - compact landing page
   - first page an LLM or human reads

2. `source_cluster`
   - groups overlapping documents
   - explains authority order and duplication

3. `service_index`
   - describes office/service routing boundaries

4. `timeline_index`
   - summarizes deadline-heavy cycles without reproducing the full calendar

## Directory structure

```text
wiki/
  index.md
  overview.md
  topics/
  clusters/
  services/
  timelines/
  validation_report.md
graph/
  graph.json
  pages.json
```

## DKU taxonomy

Each page should carry one or more DKU-specific `topic_family` values:

- `advising`
- `major_track_program`
- `academic_policy`
- `registration_planning`
- `signature_work`
- `student_support`
- `forms_workflows`
- `office_service`
- `reference_catalog`

## Source normalization rule

Do not create one canonical page per file by default.

Instead:

1. detect topic clusters from file name, path, and source text,
2. assign files into a `source_cluster`,
3. generate a short `topic_index` page that points to that cluster,
4. keep raw source pages only as backing material.

## What the index page should contain

Every `topic_index` page should remain small enough for cheap first-pass reading.

It should contain:

- one-line summary
- why this page exists
- quick orientation bullets
- best sources to open next
- related topics
- source cluster status

It should not contain:

- full policy restatement
- long procedural bullet lists
- detailed exceptions copied from source
- repeated source excerpts unless needed for routing

## Maintenance workflow

The maintenance workflow should prioritize routing quality over content quantity.

1. Rebuild from `nodes.json`
2. Detect topic clusters
3. Update `topic_index` pages
4. Update `source_cluster` pages
5. Recompute related-page graph
6. Validate for:
   - duplicate clusters
   - poor source routing
   - garbled source extraction
   - untranslated or duplicated topic pages
   - missing authority order

## Why this fits ChatDKU

ChatDKU already has tools for detailed lookups:

- semantic search
- keyword search
- curriculum queries
- prerequisites
- requirement lookups

The wiki does not need to duplicate those functions.

Its value is upstream:

- faster orientation,
- better topic dispatch,
- cleaner source selection,
- easier maintenance across many overlapping DKU materials.
