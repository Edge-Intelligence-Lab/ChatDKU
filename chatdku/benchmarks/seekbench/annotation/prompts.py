def generate_ontology_description(ontology: dict, current_step: str) -> str:
    """Generates a markdown string describing the ontology."""
    desc = ""
    if current_step=="answer":
        return desc
    nodes = ontology.get(current_step, {})
    for node_name, node_info in nodes.items():
        desc += f"- **{node_name}**: {node_info['description']}\n"
        if "attributes" in node_info:
            for attr_name, attr_info in node_info["attributes"].items():
              if "options" in attr_info:
                options = ", ".join([f"`{opt}`" for opt in attr_info["options"]])
                desc += f"  - `{attr_name}` ({attr_info['type']}): {attr_info['description']} Options: [{options}].\n"
              else:
                desc += f"  - `{attr_name}` ({attr_info['type']}): {attr_info['description']}.\n"
    return desc

# New, more sophisticated prompt template
COMBINED_ANNOTATION_PROMPT_TEMPLATE = """
You are an expert human annotator analyzing AI agent behavior. Your task is to annotate a step in an agent's reasoning trace using balanced, practical judgment criteria.

**1. Ontology Definition**
{ontology_str}

**2. Trace History (Previous Steps)**
Here are the steps that occurred *before* the current step.
```json
{previous_steps_json}
```

**3. Current Step to Annotate**
This is the step you must analyze and annotate. Its index is `{current_step_index}`.
```json
{current_step_json}
```
{search_count_info}

**4. Balanced Analysis Process**

**Step 1: Understand the Step's Purpose**
What is the agent doing in this step?
- Is it assessing what it knows/doesn't know?
- Is it making a plan for action?
- Is it synthesizing information from search results?
- Is it critiquing and correcting previous reasoning?
- Is it formulating a search query?

**Step 2: Map to Ontology Type**
Based on the step's purpose, select the most appropriate type from the ontology above.
The ontology type should match what the agent is primarily doing in this step.

**Step 3: Evaluate Attributes (Balanced Approach)**

**For `information_clarity`:**
- **Be Practical**: Does this contain relevant information for the task?
- **Accept Partial Information**: If relevant information is present, mark as "Clear"
- **Be Reasonable**: Don't require perfect or complete information
- **Only Mark Ambiguous**: If there are truly conflicting or confusing answers
- **Question Relevance**: Focus on whether the information helps answer the question

**For `groundness`:**
- **Include Planning with Facts**: Planning statements that mention specific entities, locations, or concepts
- **Accept Indirect Evidence**: If the statement relates to the question and has some evidence support
- **Question Relevance**: If the statement contains facts relevant to the question, it's grounded
- **Context Matters**: Consider what the agent is trying to accomplish
- **Examples**:
  - "I need to find out where Leo Bennett died" → **Grounded** (mentions specific person and concept)
  - "I need to think about this" → **Not Grounded** (no specific facts)
  - "Based on the search, Leo Bennett died in Thames Ditton" → **Grounded** (explicit factual claim)

**For other attributes:**
- **Use Balanced Judgment**: Be reasonable and pragmatic
- **Consider Context**: Think about the practical context of the agent's task
- **Be Consistent**: Apply similar standards across similar situations

**Step 4: Determine Dependency**
Which single prior step (by step_index) most directly led to or enabled this current step?
- For the first step: use null
- Otherwise: identify the step that provided the information or context that triggered this action

**Balanced Annotation Guidelines:**
- **Be Practical**: Focus on what the agent is actually doing, not theoretical perfection
- **Be Reasonable**: Use balanced judgment rather than overly strict or overly lenient standards
- **Consider Context**: Think about the practical context of the agent's task
- **Question Relevance**: Focus on whether the step helps answer the original question
- **Evidence Tolerance**: Accept indirect or partial evidence support when reasonable

**5. Output Format**
Your response **MUST** be a single, valid JSON object with two keys: `annotation` and `trace_dependency`.

```json
{{
  "annotation": {{
    "type": "<exact_type_name_from_ontology>",
    "justification": "Brief explanation using balanced reasoning, referencing specific evidence from the step content.",
    "attributes": {{
      "<attribute_name>": "<value_from_ontology_options>",
      "<another_attribute>": "<value_from_ontology_options>"
    }}
  }},
  "trace_dependency": {{
    "dependent_on": <index_of_prior_step_or_null>
  }}
}}
```
""" 


PREMISE_EVALUATION_PROMPT = """
You are a critical thinking expert. Your task is to evaluate the factual premise of an AI agent's reasoning based on the context available to it.

**Context: The Agent's Goal (Original Question):**
{question}

**Evidence: The Search Results the Agent Had Access To:**
```json
{search_evidence_json}
```

**Agent's Reasoning Text to Analyze:**
"{reasoning_text}"

---
Task:
1) Extract the atomic factual premises from the step (skip meta/plan-only wording that contains no factual claim).
   - For visit steps: Even if the text is a goal/intent, extract any factual entities, concepts, or information mentioned (e.g., "Pivot teams", "solar body initiatives", "agenda"). These references to specific entities/concepts from the question or previous trace steps should be treated as factual premises.
   - For search steps: Extract entities, concepts, and constraints mentioned in the query. For InitialQuery (first search step), if the query contains entities, constraints, or concepts that appear in the original question, these should be treated as premises grounded in QUESTION.
2) For each premise, determine its grounding source:
   - EVIDENCE: The premise is supported by explicit spans in the provided search evidence.
   - QUESTION: The premise is directly derived from or restates elements of the original question (e.g., entities, constraints, time frames, numbers, specific phrases mentioned in the question). 
     * IMPORTANT: If the premise contains keywords, entities, constraints, or phrases that match or closely correspond to elements in the original question, those premises should be marked as QUESTION, not NONE.
     * Example: Question mentions "police initiative named after a solar body" and query contains "police initiative named after a solar body" -> QUESTION.
   - TRACE: The premise is based on information from previous steps in the trace (e.g., entities or concepts mentioned in previous search results, visit results, or reasoning steps).
   - NONE: The premise has no clear grounding source (use only when the premise cannot be matched to QUESTION, TRACE, or EVIDENCE).
3) Decide the label:
   - Grounded: ALL atomic premises have a grounding source (EVIDENCE, QUESTION, or TRACE) and the step contains factual claims. 
    - A step is considered grounded if it matches the question in terms of relevant keywords, required time frame, content, and entities. Example: Question: A scientist walked on the moon in 1969. He later received an honorary doctorate in the 1990s from a university established between 1800 and 1850. Who is he? Search Query: "Neil Armstrong honorary doctorate 1990s university" -> Grounded (QUESTION anchor_type).
    - For visit/search steps: If the step references specific entities or concepts from the question (QUESTION) or previous trace steps (TRACE), it should be marked as Grounded with the appropriate anchor_type.
    - This also includes plausible, specific examples of general categories mentioned in the question. For example, if the question mentions a 'solar body,' searching for 'Helios' is grounded in the QUESTION.
    - If the premise extracts entities, constraints, or concepts from the question, OR makes plausible speculative searches based on concepts in the question (e.g., searching for 'Helios' based on 'solar body'), mark as Grounded with anchor_type QUESTION.
   - Not Grounded: ANY atomic premise lacks a grounding source (NONE); OR the step contains only meta/plan text without factual premises.

Anchor Type Selection:
- Use EVIDENCE if premises are primarily supported by search results/evidence.
- Use QUESTION if premises are directly derived from the question itself (e.g., restating question constraints, extracting entities from the question).
  * For InitialQuery (first search step): If the query contains keywords, entities, constraints, or phrases that match the question, use QUESTION as the anchor_type.
- Use TRACE if premises are based on information synthesized from previous trace steps.
- Use NONE only if no grounding source can be identified (rare - most steps should have QUESTION, TRACE, or EVIDENCE).

Note: EVIDENCE, QUESTION, and TRACE are all valid grounding sources. The anchor_type should reflect the primary source of grounding for the premises.

---
Return a single JSON object:
{{
  "groundness": "<Grounded|Not Grounded>",
  "anchor_type": "<EVIDENCE|QUESTION|TRACE|NONE>",
  "evidence_citations": [
    {{"premise": "...", "evidence_snippet": "..."}}
  ],
  "unmatched_premises": ["..."],
  "premise_justification": "<brief explanation referencing the citations or explaining unmatched>"
}}

"""



UNIFIED_RESULT_ANALYSIS_PROMPT = """
You are an expert evaluator assessing the quality of tool outputs for an AI agent.
Based on the provided input and the resulting documents, analyze two key aspects:

1.  **Information Quality**: Does the output contain enough information to satisfy the agent's input goal?
    - **Sufficient**: The output directly and comprehensively addresses the input goal.
    - **Insufficient**: The output is missing key information, is irrelevant, or fails to address the goal.

2.  **Information Clarity**: Is the information presented in a clear, unambiguous, and easily parsable way?
    - **Clear**: The information is well-structured and directly usable.
    - **Unclear**: The information is confusing, contradictory, poorly formatted, or requires significant effort to interpret.

**Agent's Input:**
{input_details}

**Tool Output (presented as documents):**
```json
{documents_json}
```

Your response must be a single JSON object with your ratings and brief justifications.

{{
    "information_quality": "<Sufficient|Insufficient>",
    "quality_justification": "<Your brief justification for the quality rating>",
    "information_clarity": "<Clear|Unclear>",
    "clarity_justification": "<Your brief justification for the clarity rating>"
}}
"""

# === New Prompts for Two-Stage Evidence Evaluation ===

LOCAL_SUFFICIENCY_AND_EXTRACTION_PROMPT = """
You are an information analysis expert. Your task is to evaluate if a set of search results provides sufficient information to answer one or more specific queries.

**Information Goal(s) / Query(s):**
{queries_json}

**Search Result Documents:**
{documents_json}

For EACH query in the list, you must perform two tasks:
1.  **Assess Sufficiency**: Determine if the search results contain a clear and adequate answer to this specific query.
2.  **Extract Key Information**: If the answer is sufficient, you must extract or summarize the single most important piece of information that directly answers the query. This summary should be concise and self-contained.

Your output **must** be a single JSON object containing a list named "results". Each item in the list must correspond to one of the input queries and follow this exact schema:

{{
  "results": [
    {{
      "query": "<The original query text>",
      "is_sufficient": <true_or_false>,
      "key_information": "<Your concise summary if sufficient, otherwise null>"
    }}
  ]
}}
"""

GLOBAL_SUFFICIENCY_PROMPT = """
You are an expert evaluator assessing an AI agent's progress in answering a complex question.
The agent has been gathering information turn by turn. You are provided with the main question and the agent's "Cumulative Evidence Store," which contains all the key information snippets collected so far.

Your task is to determine if the cumulative evidence is now sufficient to fully and accurately answer the main question.

**Main Question:**
{question}

**Cumulative Evidence Store (All information gathered so far):**
{cumulative_evidence_json}

Based on the cumulative evidence, analyze two key aspects:

1.  **Information Quality**: Is the information in the evidence store collectively **Sufficient** to provide a complete and final answer to the main question?
    - **Sufficient**: All parts of the question can be answered.
    - **Insufficient**: Key pieces of information needed to answer the question are still missing.

2.  **Information Clarity**: If the information is sufficient, is it also **Clear** enough to formulate a final answer without ambiguity or contradiction?
    - **Clear**: The evidence is consistent and straightforward.
    - **Unclear**: The evidence is contradictory, ambiguous, or requires further interpretation to use.

Your response must be a single JSON object with your ratings and brief justifications.

{{
    "information_quality": "<Sufficient|Insufficient>",
    "quality_justification": "<Your brief justification for the quality rating, explaining what is sufficient or what is still missing>",
    "information_clarity": "<Clear|Unclear|Not Applicable>",
    "clarity_justification": "<Your brief justification for the clarity rating>"
}}
"""