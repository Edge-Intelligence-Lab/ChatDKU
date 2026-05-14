# ChatDKU Domain-Specific Wiki Schema (V1)

This schema defines the wiki as a **natural-language index**, not a replacement for DKU source materials and not a retrieval engine.

The intended access pattern is:

1. read a short, general index page,
2. identify the right source cluster,
3. jump to the best underlying source when details are needed.

## Design goals

The ChatDKU wiki should:

- summarize what a topic is about in a few lines,
- classify the topic into DKU-specific buckets,
- record which source cluster is authoritative,
- expose version overlap and source conflicts,
- route readers toward the right source documents.

The ChatDKU wiki should not:

- rewrite the DKU bulletin in full,
- copy every procedural detail into markdown,
- flatten all knowledge into generic entity pages,
- replace source documents as the final authority.

## Why DKU needs a custom schema

The actual source base under `/datapool/chat_dku_advising` is dominated by:

- `ug_bulletin`
- `student handbook`
- `faculty advisor manual`
- `UG updates`
- `signature work materials`
- `website landing pages`
- `forms`, `slides`, `FAQs`, and `XLSX` sheets

That means the wiki should index **topic clusters**, not isolated facts.

The dominant DKU topic families are:

- advising
- majors and tracks
- academic policies
- registration and planning
- signature work
- student support / special processes
- offices and service surfaces

## Core page types

The wiki should use a small set of DKU-specific page types.

### 1. `topic_index`

Primary page type.

This is the general page an LLM or human reads first.

Examples:

- `major declaration`
- `registration planning`
- `signature work`
- `leave of absence`
- `course substitution`
- `academic advising`

Purpose:

- give a short synopsis,
- classify the topic,
- identify the canonical source cluster,
- point to related topics,
- dispatch to the best detailed sources.

### 2. `source_cluster`

A normalized page for a group of overlapping sources that cover the same topic.

Examples:

- `major declaration cluster`
  - bulletin
  - advising slides
  - major declaration handout
- `signature work cluster`
  - handbook
  - academic calendar
  - mentor sheet

Purpose:

- record which documents overlap,
- identify preferred authority order,
- expose version duplication,
- note whether the cluster is stable, outdated, or mixed.

### 3. `service_index`

A short index page for offices or service surfaces.

Examples:

- `Office of Undergraduate Advising`
- `Registrar / Student Self-Service Center`
- `Signature Work support`
- `Student Accessibility Service`

Purpose:

- summarize the service boundary,
- state what kinds of topics route here,
- point to the source cluster and related topic indexes.

### 4. `timeline_index`

A compact calendar-oriented page for deadline-heavy topics.

Examples:

- `signature work annual cycle`
- `major declaration timing`
- `registration cycle`

Purpose:

- summarize the time structure,
- link to authoritative calendars or handbooks,
- avoid copying all dates unless they are directly grounded and stable.

## DKU-specific taxonomy

Every page should carry at least one `topic_family`.

Recommended controlled values:

- `advising`
- `major_track_program`
- `academic_policy`
- `registration_planning`
- `signature_work`
- `student_support`
- `forms_workflows`
- `office_service`
- `reference_catalog`

Optional `audience` values:

- `undergraduate`
- `faculty_advisor`
- `student`
- `staff`
- `pre_health`
- `pre_law`
- `signature_work_student`

Optional `source_surface` values:

- `bulletin`
- `handbook`
- `faq`
- `form`
- `guide`
- `slides`
- `website`
- `spreadsheet`
- `calendar`

## Canonical page structure

Each `topic_index` page should stay intentionally short.

### Required frontmatter

```yaml
---
page_type: topic_index
page_id: topic.major_declaration
title: Major Declaration
topic_family:
  - major_track_program
  - forms_workflows
audience:
  - undergraduate
dispatch_priority: high
canonical_source_cluster: cluster.major_declaration
preferred_detail_source:
  - source.ug_bulletin_2025_2026
  - source.understanding_major_declaration
related_pages:
  - topic.majors_overview
  - topic.academic_advising
  - timeline.major_declaration
source_surfaces:
  - bulletin
  - slides
  - website
stability: medium
status: active
last_verified: 2026-05-14
---
```

### Required body sections

```md
# Major Declaration

## One-Line Summary
Very short description of what this topic is.

## Why This Page Exists
What kind of question this page helps route.

## Quick Orientation
3-6 short bullets max.
- what the topic covers
- who it applies to
- where details usually live

## Best Sources To Open Next
- preferred source
- secondary source
- supporting service page

## Related Topics
- majors overview
- advising
- registration planning

## Source Cluster Status
- stable / duplicated / mixed / needs review
```

This is an index page, so it should be short enough that an LLM can read it first without paying the cost of a long source document.

## Source cluster schema

The `source_cluster` page is where duplication and authority get normalized.

### Required frontmatter

```yaml
---
page_type: source_cluster
page_id: cluster.major_declaration
title: Major Declaration Source Cluster
topic_family:
  - major_track_program
source_surfaces:
  - bulletin
  - slides
  - website
authority_order:
  - ug_bulletin
  - ugstudies_website
  - advising_materials
cluster_status: mixed
canonical_topic_pages:
  - topic.major_declaration
last_verified: 2026-05-14
---
```

### Required body sections

```md
# Major Declaration Source Cluster

## Cluster Summary
One short paragraph about what this cluster covers.

## Authority Order
- primary authority
- secondary authority
- supporting context

## Included Sources
- file / page name
- source type
- version hint
- why it belongs here

## Notes On Overlap
- duplicated
- translated
- derived
- outdated

## Known Gaps Or Conflicts
- if any
```

## Service index schema

The `service_index` page should explain routing, not reproduce office websites.

### Required body sections

- `One-Line Summary`
- `What This Service Helps With`
- `Topics Routed Here`
- `Best Sources To Open`
- `Related Topic Indexes`

## Timeline index schema

The `timeline_index` page should summarize timing shape, not dump every date.

### Required body sections

- `Cycle Summary`
- `What Changes By Term / Year`
- `Best Calendar / Handbook Sources`
- `Related Topic Indexes`

## Suggested first-wave DKU topic pages

These are good initial `topic_index` pages because they have many overlapping sources and high routing value:

- `topic.academic_advising`
- `topic.majors_overview`
- `topic.major_declaration`
- `topic.registration_planning`
- `topic.course_substitution`
- `topic.leave_of_absence`
- `topic.cr_nc`
- `topic.overload_policy`
- `topic.signature_work`
- `topic.student_self_service_center`

## Important modeling rule

The page should summarize the **topic**, not summarize each source independently.

That means:

- the `topic_index` page is the landing page,
- the `source_cluster` page explains the document overlap,
- the actual document page remains the detail source,
- full procedural detail stays in the underlying DKU material.

## LLM interaction pattern

The expected LLM workflow is:

1. open `wiki/index.md`,
2. open a relevant `topic_index` page,
3. use the topic page to identify the best detailed source,
4. open the source only when the question needs fine-grained detail.

So the wiki should optimize for:

- fast orientation,
- routing quality,
- source selection quality,
- source provenance,
- compactness.
