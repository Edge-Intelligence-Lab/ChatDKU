QA_PROMPT = """
You are an expert QA dataset generator.

Your task is to generate exactly 5 Question-Answer pairs from the given context.

You MUST return ONLY valid JSON in the following exact format:

```json 
{{ "qa_pairs":[ {{ "question": "Which organization accredits Duke University?", "ground_truth": "Duke University is accredited by the Southern Association of Colleges and Schools Commission on Colleges (SACSCOC).", "max_iteration": 2 }}, {{ "question": "If a student takes courses at Duke Kunshan University and later applies to another university, what factors determine whether those courses will be accepted for transfer?", "ground_truth": "Although Duke University may accept certain course work from Duke Kunshan University, other universities independently decide whether to accept transfer credits, and such course work may not be accepted even if it appears on a Duke University transcript.", "max_iteration": 5 }}, {{ "question": "Explain how Duke Kunshan University’s partnership structure and accreditation status affect a student’s academic recognition.", "ground_truth": "Duke Kunshan University partners with Duke University, Wuhan University, and Kunshan, and students become alumni of both institutions. However, Duke University is accredited by SACSCOC while Duke Kunshan University is not, and this accreditation does not extend to DKU or its students.", "max_iteration": 4 }}, {{ "question": "How does the university ensure students stay informed about academic and administrative requirements, and what responsibilities do students have in this process?", "ground_truth": "Duke Kunshan University provides all students with email accounts and uses electronic mail for official communication. Students are expected to regularly check and respond to these communications to stay informed.", "max_iteration": 3 }}, {{ "question": "How do general education requirements and major requirements together contribute to fulfilling degree requirements at Duke Kunshan University?", "ground_truth": "General education requirements include Common Core, distribution, quantitative reasoning, language, and writing courses, while major requirements consist of 16–19 courses totaling 64–76 credits. Together, these components contribute to fulfilling overall degree requirements.", "max_iteration": 5 }}, {{ "question": "What is the significance of DKU 101 in the curriculum, and how does it relate to the overall credit structure of the degree?", "ground_truth": "DKU 101 is a non-credit mini-term course worth 0 credits, meaning it is part of the curriculum experience but does not contribute to the total credits required for the degree.", "max_iteration": 4 }} ] }}
```

STRICT RULES:
- Output MUST be valid JSON
- Output MUST contain the key "qa_pairs"
- "qa_pairs" MUST be a list of exactly 5 items
- DO NOT return {{}}
- DO NOT return an empty list
- DO NOT include explanations or text outside JSON
- Each question MUST be answerable strictly from the context. Multi hop questions should be extremely difficult.
- Questions should vary in difficulty (2 to 5 hops). 
- Multihop questions can include multiple questions from the chunks.

Context:
{chunk}
"""