QA_PROMPT = """
You are an Expert Human QA generator. Your task is to generate Question-Answer (QA) pair based on the given corpus for an agent system. You design questions of different difficulty and produce answers based on the question. The question you generate is used for benchmarking.

**QA Metadata**
`question` : The question based on the corpus.
`grounded_truth` : The answer based on the corpus.
`max_iteration` : The number of hops required to generate the answer. Values Range from 2 to 5

----

**Example**

- Example Chunk:
['Students will be alumni of both institutions.\n\nDuke University is accredited by the Southern Association of Colleges and Schools Commission on Colleges (SACSCOC) in the United States to award baccalaureate, master’s and doctorate degrees. Duke Kunshan University is not accredited by SACSCOC and the accreditation of Duke University does not extend to or include Duke Kunshan University or its students. Further, although Duke University agrees to accept certain course work from Duke Kunshan University to be applied toward an award from Duke University, that course work may not be accepted by other colleges or universities in transfer, even if it appears on a transcript from Duke University. The decision to accept course work in transfer from any institution is made by the institution considering the acceptance of credits or course work.\n\nDuke Kunshan University recognizes and utilizes electronic mail as a medium for official communications. The university provides all students with email accounts. All students are expected to access their email accounts on a regular basis to check for and respond as necessary to such communications.', 'Table of Contents\n# Part 1: General Information\n\nMission Statement\n\nStatement on Diversity and Inclusion\n\nWho We Are\n\nPartners\n\n- Duke University\n- Wuhan University\n- Kunshan\n\nDuke Kunshan University Community Standard\n\n# Part 2: A Liberal Arts Education at Duke Kunshan University\n\nA 21st Century Curriculum\n\nA Liberal Arts College Experience\n\nDual Degrees\n\nAnimating Principles\n\n# Part 3: The Curriculum\n\nOverview\n\nKey Components\n\nStructures\n\nCore Components\n\nDegree Requirements\n\n- General Education Requirements\n- - Common Core (3 courses, 12 credits)\n- Distribution Requirement (3 courses, 12 credits)\n- Quantitative Reasoning Course Requirement (1 course, 4 credits)\n- Language Courses (4-8 courses, 8-16 credits)\n- Writing Course (1 course, 2 credits)\n\nMajor Requirements (16-19 courses, 64-76 credits)\n\nCredits Required for Degree\n\nNon-Credit Mini-Term Courses\n\nDKU 101 (0 Credits)\n\n# Part 4: Admission, Scholarships and Financial Aid\n\nPrinciples of Selection\n\nHow to Apply\n\nApplication Timelines\n\nApplication Requirements\n\nScholarships and Financial Aid\n\nNotification and Responses\n\n# Part 5: Financial Information']


- Example Response:
```json
{{
    "question": "Which organization accredits Duke University?",
    "ground_truth": "Duke University is accredited by the Southern Association of Colleges and Schools Commission on Colleges (SACSCOC).",
    "max_iteration": 2

}}


```
----

Chunk:
{chunk}
"""