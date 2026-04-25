---
name: Course-Recommendation
description: Instructions for recommending courses and building schedules for DKU undergraduates. Use when a student asks what to take, for a schedule recommendation, or whether a course fits their degree plan.
license: Proprietary.
version: 0.1.0
metadata:
    tags: [instruction]
    category: advising
---

# Course Recommendation Instructions

Source of truth: DKU Undergraduate Bulletin 2025-2026, Part 3 (The Curriculum).

## When to Use

Trigger on requests like "what should I take next session?", "help me plan my schedule", "can this course count for X?", "am I on track to graduate?", or any schedule-building task. Do **not** use for questions that are purely about a single course's content, prerequisites, or logistics — route those to `SyllabusLookup`, `PrerequisiteLookup`, or `CourseScheduleLookup` directly.

## Required Context Before Recommending

Before suggesting anything, you must know (ask if missing):
1. **Year of study** (1–4) and matriculation year — requirements follow the Bulletin of the matriculation year.
2. **Student Type** — international vs. Chinese Mainland / HK-Macau-Taiwan (HMT). Chinese/HMT students have extra requirements (CHSC, PE, military training).
3. **Language track** — English for Academic Purposes (EAP), Chinese as a Second Language (CSL), or waived. This determines 8–16 language credits.
4. **Declared or intended major** (or "undeclared"). Incoming students haven't declared their major.
5. **Courses already completed / in progress** — needed to check prerequisites and avoid duplicates.

If the student is exploring rather than planning, skip (4)–(5) and give requirement-structure guidance.

## Duke Kunshan University's Academic Year Structure

Each session is 7-week long, with a following exam week.
We have 4 sessions in an academic year (From August to May). There are two semesters, and each semester has two sessions. In one session, students generally take 2 x 4 credit courses and additional 2-credit language or writing course.
In the first 7 week session of their first term, first-year students are restricted to a maximum of 8 credits (one four-credit course, one two-credit language course, and one additional two-credit writing course.), plus one optional PE course.
The maximum number of credits in any subsequent 7-week session without special permission is 10 (two 4-credit courses and one 2-credit course), plus one PE course.
In fall and spring terms, the normal course load is 16-20 credits (8-10 credits in each 7-week session).

## Degree Requirement Cheat Sheet

Graduation: **136 DKU credits** (international) or **158** (Chinese/HMT, includes CHSC + military + PE). 34 of the 136 must come from courses taught/co-taught by Duke faculty (~8.5 courses).

### General Education
| Requirement | Courses | Credits | Notes |
|---|---|---|---|
| Common Core | 3 | 12 | Y1 *China in the World*; Y2 *Global Challenges in Sci/Tech/Health*; Y3 *Ethics, Citizenship & the Examined Life*. Must be taken Fall/Spring of the **designated year** — failure can block study-away. |
| Distribution | 3 | 12 | 4 credits in each of Arts & Humanities, Natural & Applied Sciences, Social Sciences. |
| Quantitative Reasoning | 1 | 4 | Course with QR attribute. Cannot be satisfied by AP/IPC. |
| Language (EAP or CSL) | 4–8 | 8–16 | EAP track: 101A/B + 102A/B. CSL track: ≥8 credits, must pass CHINESE 202B or higher. |
| Writing (W) | 1 | 2 | Taken in first-year's **first session**. |
| Mini-term | 1 | 0 | Non-credit, 1-week exploratory course; any year. |

### Major (16–19 courses, 64–76 credits)
- **Divisional Foundation** (2–5 courses) — finish **by end of junior year**; juniors with gaps get priority / administrative adjustment.
- **Interdisciplinary Studies** (4–7 courses) — the primary academic community; advanced seminars in Y3/Y4.
- **Disciplinary Studies** (4–8 courses) — depth track.
- **Signature Work** (8 credits) — 3 thematic courses (drawn from interdisciplinary/disciplinary/electives, topic tied to major) + 2 Capstones in senior year (two 4-credit, or one 2-credit junior + one 4-credit + one 2-credit senior). Mentor must be identified in sophomore year, proposal in junior year.

### Electives (8–13 courses, 32–52 credits)
Absorbs the distribution + QR courses and any extra breadth/depth. Students need electives beyond the GenEd + major minimum to reach 136 credits.

### DKU 101

Extends DKU's first-year orientation. This 7-week, non-credit, non-graded course meets weekly, and all DKU first-year students must take it during the first session of their first year. Attendence is required at all sessions in order to fulfill this degree requirement. Students who fail to complete the DKU 101 requirement will be required to repeat the course in the following year.

### Additional for Chinese / HMT Students
- Chinese Society & Culture (CHSC): 16 credits (taught in Chinese; **do not** count toward the 136 for the Duke degree).
- Military training: 4 credits (HMT may substitute this with CHSC courses).
- Physical Education: 8 half-credit courses (4 credits; max 2 count toward the 136) + annual physical proficiency test.

## Attribute Counting Rules (apply every time)

1. A course with **two divisional attributes** counts for only one area.
2. **QR + divisional** → counts as only one of the two.
3. **W + divisional** → counts as only one of the two.
4. Transfer / study-away / summer credits for Distribution or QR need division-chair approval. **AP/IPC cannot satisfy QR or Distribution.**
5. Credit caps toward the 136: ≤8 D-grade credits; ≤2 PE credits; ≤16 Credit/No-Credit credits; ≤40 combined transfer/AP/IPC; ≤24-equivalent in Duke grad/professional courses.

## Procedure

1. **Gather context** (see "Required Context"). Do not guess the student's track.
2. **Pull the student's major requirements** via `MajorRequirementsLookup` — this gives the authoritative list of foundation, interdisciplinary, and disciplinary courses for their matriculation year.
3. **Identify remaining gaps** by subtracting completed courses from: Common Core (by year), Language sequence, Writing, QR, Distribution (per division), Foundation, Interdisciplinary, Disciplinary, Signature Work, Mini-term, and (for Chinese/HMT) CHSC/PE/military.
4. **Prioritize** in this order:
   - Year-locked Common Core for the current year (missing it risks study-away eligibility).
   - Writing (first-year, first session only).
   - EAP/CSL sequence progression (sequential, gating).
   - Divisional Foundation if the student is in junior year with gaps.
   - Prerequisite chains for the major (use `PrerequisiteLookup`).
   - Signature Work milestones at the right year.
   - Distribution + QR to round out breadth.
5. **Check offerings** with `CourseScheduleLookup` for the target session — only recommend courses actually offered, with seats consistent with the student's year.
6. **Verify prerequisites** for each candidate with `PrerequisiteLookup` before suggesting it.
7. **Anchor on enumerated schedules.** When `CourseRecommender` returns a "Plausible non-conflicting schedules" section, treat those combinations as the trustworthy starting point — they are deterministically proven to have no primary-section time conflicts within a session. Pick from these rather than re-assembling a schedule by hand. If none of the listed combinations match the student's preferences, you may swap in another eligible-and-offered course, but you must then re-verify time fit by inspecting the day flags and `Mtg Start`/`Mtg End` of the candidate sections via `CourseScheduleLookup`.
8. **Present the recommendation** as a short plan: for each course, state (a) course code/title and chosen section, (b) which requirement it satisfies, (c) why it fits now (prereq chain, year-lock, breadth gap), (d) the meeting days/times. Offer alternatives where reasonable.
9. **Cite** the Bulletin section whenever you state a rule (e.g., "Bulletin 2025-2026, Part 3, Distribution Requirement").

## Pitfalls

- **Don't double-count.** A course with QR + Social-Sciences attribute fills only one — decide which, and tell the student.
- **Don't assume the current year's Bulletin applies.** Requirements are frozen at matriculation unless the student elects to move forward.
- **Don't recommend Common Core out of sequence.** Y1 → Y2 → Y3; missing the designated-year window triggers administrative action.
- **Don't forget the 34-Duke-credit rule.** A plan heavy in DKU-only faculty courses may satisfy 136 credits but not the Duke degree.
- **Don't treat PE / CHSC / military as optional for Chinese students** — they're MOE-mandated.
- **Don't recommend AP/IPC as a QR or Distribution substitute.** It won't count.
- **Don't over-load electives before gating requirements are done.** A senior missing Foundation courses is a registration-hold risk.
- **Don't invent course codes or attributes.** Every course name, code, attribute, and prerequisite must come from a tool call, not memory.

## Verification

Before returning the final recommendation, confirm:
- [ ] Each recommended course exists in the current schedule (`CourseScheduleLookup`).
- [ ] Prerequisites are met (`PrerequisiteLookup`).
- [ ] Each course is mapped to exactly one requirement bucket in the plan.
- [ ] **No two recommended primary sections in the same session share a meeting day at overlapping times.** Use the schedules enumerated by `CourseRecommender` whenever available — they are guaranteed conflict-free. If you build a schedule outside that list, walk the day flags + `Mtg Start`/`Mtg End` of every section pair yourself.
- [ ] **Lab / recitation / discussion fit acknowledged.** `CourseRecommender`'s conflict check covers only primary lectures (sections with purely numeric labels). For each recommended course, check whether the chosen primary has a paired secondary (suffixes like `L`, `R`, `D`) and confirm at least one secondary slot is conflict-free against the rest of the schedule.
- [ ] Year-locked items (Common Core, Writing, Foundation deadline) are addressed or explicitly deferred with reasoning.
- [ ] Credit total per session is reasonable for a DKU 7-week session (typically 2 in-depth courses, optionally 1 in a 14-week block).
- [ ] For Chinese/HMT students, CHSC/PE/military progress is acknowledged.
- [ ] Sources cited: Bulletin section + tool results.
