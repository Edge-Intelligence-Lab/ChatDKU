import argparse
import json
import os
import re
# from langfuse.openai import AsyncOpenAI
# from langfuse.openai import openai
from openai import AsyncOpenAI
from dotenv import load_dotenv
from tqdm import tqdm
import logging
import asyncio
import uuid
try:
    from .prompts import (
        generate_ontology_description,
        COMBINED_ANNOTATION_PROMPT_TEMPLATE,
        PREMISE_EVALUATION_PROMPT,
        UNIFIED_RESULT_ANALYSIS_PROMPT,
        LOCAL_SUFFICIENCY_AND_EXTRACTION_PROMPT,
        GLOBAL_SUFFICIENCY_PROMPT,
    )
except ImportError:
    from prompts import (
        generate_ontology_description,
        COMBINED_ANNOTATION_PROMPT_TEMPLATE,
        PREMISE_EVALUATION_PROMPT,
        UNIFIED_RESULT_ANALYSIS_PROMPT,
        LOCAL_SUFFICIENCY_AND_EXTRACTION_PROMPT,
        GLOBAL_SUFFICIENCY_PROMPT,
    )
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
# Set Langfuse configuration to disable tracing
# openai.langfuse_enabled = False
DEFAULT_ONTOLOGY_PATH = os.path.join(os.path.dirname(__file__), "ontology.json")

async def annotate_tool_result(step, trace, ontology, model, max_retries=3, delay=5):
    """
    Unified function to analyze any tool result for quality and clarity,
    using a dynamic prompt to provide context for each tool type.
    """
    parent_index = step.get('trace_dependency', {}).get('dependent_on')
    if parent_index is None or not (0 <= parent_index < len(trace)):
        return
    
    tool_step = trace[parent_index]
    tool_type = tool_step.get("type")
    step_type = step.get("type")
    
    # Get the correct annotation type from ontology
    # For result types, ontology structure is: {"step_type": {"annotation_type": {...}}}
    # We need to get the annotation_type (which is typically "search_result" for all result types)
    step_ontology = ontology.get(step_type, {})
    if not step_ontology:
        # Fallback: use "search_result" as default for all result types
        annotation_type = "search_result"
    else:
        # Get the first (and typically only) key as the annotation type
        annotation_type = next(iter(step_ontology.keys()), "search_result")
    
    # Dynamically build the 'input_details' part of the prompt
    input_details = ""
    if tool_type == "search" or tool_type == "google_scholar":
        query = tool_step.get("query", "")
        if isinstance(query, list):
            query_str = "\n".join(f"- {q}" for q in query)
            input_details = f"**Search Query(s):**\n{query_str}"
        else:
            input_details = f"**Search Query:**\n{query}"
            
    elif tool_type == "visit":
        url = tool_step.get("url", [])
        goal = tool_step.get("goal", "")
        if isinstance(url, list):
            url = ", ".join(url)
        input_details = f"**Visited URL(s):**\n{url}\n\n**Visit Goal:**\n{goal}"

    elif tool_type == "parse_file":
        files = tool_step.get("files", [])
        if isinstance(files, list):
            files = ", ".join(files)
        input_details = f"**Parsed File(s):**\n{files}"

    elif tool_type == "python":
        code = tool_step.get("code", "")
        input_details = f"**Executed Code:**\n```python\n{code}\n```"
    
    # Convert all result types to a unified 'documents' format for the prompt
    documents = []
    if step_type in ["search_result", "scholar_result"]:
        documents = step.get("documents", [])
    elif step_type in ["visit_result", "file_result", "python_result"]:
        content = step.get("content", "")
        title_map = {
            "visit_result": "Visited Content",
            "file_result": "Parsed File Content",
            "python_result": "Python Execution Output"
        }
        documents = [{"title": title_map.get(step_type), "content": content}]
    else:
        return # Not a result step
    
    # Final prompt assembly
    prompt = UNIFIED_RESULT_ANALYSIS_PROMPT.format(
        input_details=input_details,
        documents_json=json.dumps(documents, indent=2)
    )

    llm_response = await call_llm(prompt, model, max_retries, delay)

    if llm_response:
        # Restructure the annotation to be consistent with other step types
        # Use the annotation type from ontology
        step["annotation"] = {
            "type": annotation_type,
            "attributes": {
                "information_quality": llm_response.get("information_quality", "Unspecified"),
                "information_clarity": llm_response.get("information_clarity", "Unspecified"),
                "quality_justification": llm_response.get("quality_justification", "Unspecified"),
                "clarity_justification": llm_response.get("clarity_justification", "Unspecified")
            }
        }


JUDGE_PROMPT = """
You are an expert evaluator. Your task is to determine if the provided 'answer' is correct based on the 'ground_truth'.
The answer does not need to be a perfect match, but it must be semantically correct and capture the key information from the ground truth.

**Ground Truth:**
{ground_truth}

**Answer:**
{answer}

Based on the comparison, is the answer correct?
Your response must be a single JSON object with a single boolean key: "is_correct".

{{
    "is_correct": <yes_or_no>
}}
"""

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Load environment variables and initialize OpenAI client
load_dotenv()
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE") or None,
)

async def call_llm(prompt, model, max_retries=3, delay=5):
    """Calls the OpenAI API with retry logic and the most robust JSON parsing."""
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"},
                # metadata={"langfuse_session_id": session_id}
            )
            content = response.choices[0].message.content

            # --- Final robust parsing logic ---
            # Greedily find the substring that looks like a valid JSON object
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                json_str = match.group(0)
                try:
                    # Test if the extracted string is valid JSON
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logging.error(f"Extracted JSON-like string failed to parse on attempt {attempt + 1}/{max_retries}: {e}")
                    logging.error(f"Problematic extracted string: >>>\n{json_str}\n<<<")
            else:
                 logging.error(f"Could not find any JSON-like object in the response on attempt {attempt + 1}/{max_retries}.")
                 logging.error(f"Full problematic content: >>>\n{content}\n<<<")

            if attempt + 1 == max_retries:
                return None
            await asyncio.sleep(delay)

        except Exception as e:
            logging.error(f"API call failed on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt + 1 == max_retries:
                return None
            await asyncio.sleep(delay)
    return None

async def call_judge_llm(ground_truth, answer, model):
    """Calls the LLM to judge the correctness of an answer."""
    prompt = JUDGE_PROMPT.format(ground_truth=ground_truth, answer=answer)
    llm_response = await call_llm(prompt, model) # Reusing the existing robust call_llm function
    if llm_response and isinstance(llm_response.get("is_correct"), bool):
        return llm_response.get("is_correct")
    else:
        logging.warning(f"Judge LLM call failed or returned malformed data. Response: {llm_response}")
        return None 


async def annotate_step(trace_with_indices, step_index, ontology, lock, ground_truth=None, model=None):
    """Annotates a single step for its node type and its error dependency.
    NOTE: This function no longer handles 'search_result' steps, as they are now processed
    by the new two-stage global evaluation logic in `annotate_trace`.
    """
    current_step = trace_with_indices[step_index]
    step_type = current_step.get("type")

    # --- Unified Annotation for non-search tool results ---
    if step_type in ["visit_result", "scholar_result", "file_result", "python_result"]:
        # First, establish the deterministic dependency link to the preceding tool call
        if step_index > 0:
            current_step["trace_dependency"] = {"dependent_on": step_index - 1}
        else:
            current_step["trace_dependency"] = {"dependent_on": None}
        
        # Now, call the unified analysis function (pass ontology for dynamic annotation type lookup)
        # The original 'annotate_tool_result' is still valid for these simpler, non-cumulative results.
        await annotate_tool_result(current_step, trace_with_indices, ontology, model)
        return # End processing for this step here

    elif step_type.endswith("Answer"): # Handles CorrectAnswer and IncorrectAnswer
        current_step["trace_dependency"] = {"dependent_on": step_index - 1 if step_index > 0 else None}
        current_step["annotation"] = {
            "type": step_type,
            "justification": "System-generated answer based on correctness."
        }
        # LLM as a Judge
        if ground_truth and step_type == "IncorrectAnswer":
            is_correct = await call_judge_llm(ground_truth, current_step["content"], model)
            # If the LLM judge returns a boolean, we update the annotation.
            # Otherwise, we don't add the key.
            if is_correct is not None:
                current_step["annotation"]["is_correct"] = is_correct
            if is_correct:
                # remove IncorrectAnswer and change the type to CorrectAnswer
                current_step["type"] = "CorrectAnswer"
                current_step["annotation"]["justification"] = "System-generated answer based on correctness."
                current_step["content"] = current_step["content"]
                current_step["annotation"]["type"] = "CorrectAnswer"
        return

    # Use the LLM for complex annotation of 'reasoning' and all tool call steps
    tool_call_types = ["search", "visit", "google_scholar", "parse_file", "python"]
    if step_type not in ["reasoning"] + tool_call_types:
        # For other simple steps, assign a default dependency and skip LLM annotation.
        if step_index > 0:
            current_step["trace_dependency"] = {"dependent_on": step_index - 1}
        else:
            current_step["trace_dependency"] = {"dependent_on": None}
        current_step["annotation"] = {"type": step_type, "justification": "Dependency inferred by position, not analyzed by LLM."}
        return

    # The prompt context should not include the annotations of previous steps
    # to avoid confusing the LLM. We create a clean version of the full history for the prompt.
    previous_steps_for_prompt = []
    for step in trace_with_indices[:step_index]:
        # Create a clean copy of the step, removing annotations that would confuse the LLM
        clean_step = {k: v for k, v in step.items() if k not in ['annotation', 'trace_dependency']}
        previous_steps_for_prompt.append(clean_step)


    # Prepare a version of the current step for the prompt, handling list inputs
    current_step_for_prompt = {k: v for k, v in current_step.items() if k not in ['annotation', 'trace_dependency']}
    if step_type in ["search", "google_scholar"]:
        query = current_step_for_prompt.get("query", "")
        if isinstance(query, list):
            # For the prompt, combine multiple queries into a single representative string
            current_step_for_prompt["query"] = " | ".join(map(str, query))

    # If the current step is a tool call, add the count to the prompt.
    search_count_info = ""
    if step_type in tool_call_types:
        # Count tool calls of the same type up to the current step
        type_count = sum(1 for step in trace_with_indices[:step_index + 1] if step.get("type") == step_type)
        
        # Get previous inputs of the same tool type
        previous_inputs = []
        for step in trace_with_indices[:step_index]:
            if step.get("type") == step_type:
                if step_type in ["search", "google_scholar"]:
                    previous_inputs.append(step.get("query"))
                elif step_type == "visit":
                    previous_inputs.append(f"URL(s): {step.get('url')}, Goal: {step.get('goal')}")
                elif step_type == "parse_file":
                    previous_inputs.append(step.get("files"))
                elif step_type == "python":
                    previous_inputs.append(step.get("code"))

        search_count_info = f"\nThis is {step_type} number {type_count} in the session. The previous inputs for this tool were: {previous_inputs}."

    prompt = COMBINED_ANNOTATION_PROMPT_TEMPLATE.format(
        ontology_str=generate_ontology_description(ontology, step_type),
        previous_steps_json=json.dumps(previous_steps_for_prompt, indent=2),
        current_step_json=json.dumps(current_step_for_prompt, indent=2),
        current_step_index=step_index,
        search_count_info=search_count_info
    )

    llm_response = None
    max_retries = 3
    for attempt in range(max_retries):
        response = await call_llm(prompt, model)

        # Basic response check
        if not response:
            logging.warning(f"LLM call for step {step_index} returned no response on attempt {attempt + 1}/{max_retries}.")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
            continue

        # --- Validation ---
        # 1. Annotation structure validation
        ann_data = response.get("annotation", {})
        if "type" not in ann_data or "justification" not in ann_data:
            logging.warning(f"Attempt {attempt + 1}/{max_retries}: Malformed annotation for step {step_index} (missing type/justification).")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
            continue
            
        # 2. Annotation type validation against ontology
        step_type_from_llm = ann_data.get("type")
        actual_step_type = current_step.get("type")
        if step_type_from_llm not in ontology.get(actual_step_type, {}):
            logging.warning(f"Attempt {attempt + 1}/{max_retries}: Invalid annotation type '{step_type_from_llm}' for step {step_index} of type {actual_step_type}.")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
            continue
        
        # All checks passed
        llm_response = response
        break

    if not llm_response:
        logging.error(f"LLM annotation failed for step {step_index} after {max_retries} attempts. Skipping annotations.")
        current_step["annotation"] = {"error": f"LLM validation failed after {max_retries} retries"}
        current_step["trace_dependency"] = {"dependent_on": step_index - 1}
        return

    # --- Annotation Data Validation ---
    annotation_data = llm_response.get("annotation", {})
    step_type_from_llm = annotation_data.get("type") 
    current_step["annotation"] = annotation_data

    # --- Dependency Edge Data Validation ---
    # We can trust the data here because it was validated in the retry loop.
    # dependency_data = llm_response.get("trace_dependency", {})
    # dependent_on_index = dependency_data.get("dependent_on")
    if step_index == 0:
         current_step["trace_dependency"] = {"dependent_on": None}
    else:
        current_step["trace_dependency"] = {"dependent_on": step_index - 1}

    # --- Process Attributes ---
    if "annotation" in current_step and "attributes" in llm_response.get("annotation", {}):
        attributes = llm_response["annotation"].get("attributes", {})
        
        # --- Ontology-Based Attribute Filtering ---
        # Get the list of allowed attributes for the returned annotation type from the ontology
        step_ontology = ontology.get(actual_step_type, {})
        annotation_type_ontology = step_ontology.get(step_type_from_llm, {})
        allowed_attributes = annotation_type_ontology.get("attributes", {}).keys()
        
        # Filter the attributes from the LLM response, keeping only the allowed ones
        filtered_attributes = {
            k: v for k, v in attributes.items() if k in allowed_attributes and v is not None
        }
        
        current_step["annotation"]["attributes"] = filtered_attributes
        
        # --- Attribute Back-propagation (DEPRECATED) ---
        # This logic is no longer needed as result attributes are handled by a dedicated function
        # and filtering now prevents attribute leakage.


async def annotate_search_result_globally(step, question, cumulative_evidence, model):
    """
    Implements the new two-stage evidence evaluation for search results.
    - Stage 1: Local sufficiency & key info extraction per query.
    - Stage 2: Global sufficiency assessment against the main question.
    """
    documents = step.get("documents", [])
    if not documents:
        # If there are no search results, we can't do much. Mark as insufficient.
        step["annotation"] = {
            "type": "search_result",
            "attributes": {
                "information_quality": "Insufficient",
                "quality_justification": "The search returned no documents.",
                "information_clarity": "Clear",
                "clarity_justification": "N/A",
                "local_sufficiency_results": [],
            }
        }
        return

    # --- STAGE 1: Local Sufficiency & Extraction ---
    queries = step.get("parent_query", []) # 'parent_query' is set in annotate_step
    if not isinstance(queries, list):
        queries = [queries]

    local_prompt = LOCAL_SUFFICIENCY_AND_EXTRACTION_PROMPT.format(
        queries_json=json.dumps(queries, indent=2),
        documents_json=json.dumps(documents, indent=2)
    )
    local_response = await call_llm(local_prompt, model)

    newly_extracted_info = []
    local_sufficiency_results = []
    if local_response and "results" in local_response and isinstance(local_response["results"], list):
        local_sufficiency_results = local_response["results"]
        for res in local_sufficiency_results:
            if res.get("is_sufficient") and res.get("key_information"):
                # Add citation metadata to the extracted info
                info_snippet = f"From query '{res.get('query')}': {res.get('key_information')}"
                newly_extracted_info.append(info_snippet)

    # Update the main evidence store
    cumulative_evidence.extend(newly_extracted_info)

    # --- STAGE 2: Global Sufficiency ---
    global_prompt = GLOBAL_SUFFICIENCY_PROMPT.format(
        question=question,
        cumulative_evidence_json=json.dumps(cumulative_evidence, indent=2)
    )
    global_response = await call_llm(global_prompt, model)

    # --- Final Annotation ---
    if global_response:
        step["annotation"] = {
            "type": "search_result",
            "attributes": {
                "information_quality": global_response.get("information_quality", "Unspecified"),
                "information_clarity": global_response.get("information_clarity", "Unspecified"),
                "quality_justification": global_response.get("quality_justification", "Unspecified"),
                "clarity_justification": global_response.get("clarity_justification", "Unspecified"),
                "local_sufficiency_results": local_sufficiency_results,
                "cumulative_evidence_count": len(cumulative_evidence)
            }
        }
    else:
        # Fallback if global evaluation fails
        step["annotation"] = {
            "type": "search_result",
            "attributes": {
                "information_quality": "Insufficient",
                "quality_justification": "Global sufficiency evaluation failed.",
                "information_clarity": "Unclear",
                "clarity_justification": "Global sufficiency evaluation failed.",
                "local_sufficiency_results": local_sufficiency_results,
            }
        }


async def evaluate_groundness(step, trace, question, model):
    """
    A dedicated function to perform a second pass analysis on a step's premise.
    This is used for all non-result steps (reasoning, search, visit, etc.).
    """
    text_to_analyze = ""
    step_type = step.get("type")

    # Extract the relevant text content to analyze for grounding
    if step_type == "reasoning":
        text_to_analyze = step.get("content", "")
    elif step_type in ["search", "google_scholar"]:
        query = step.get("query", "")
        if isinstance(query, list):
            text_to_analyze = " | ".join(map(str, query))
        else:
            text_to_analyze = str(query)
    elif step_type == "visit":
        urls = step.get("url", [])
        goal = step.get("goal", "")
        url_str = ", ".join(urls) if isinstance(urls, list) else str(urls)
        text_to_analyze = f"Visiting URL(s): {url_str} with goal: {goal}"
    elif step_type == "parse_file":
        files = step.get("files", [])
        file_str = ", ".join(files) if isinstance(files, list) else str(files)
        text_to_analyze = f"Parsing file(s): {file_str}"
    elif step_type == "python":
        text_to_analyze = step.get("code", "")

    if not text_to_analyze:
        return # Cannot evaluate if there is no text content
        
    # Find all search evidence that the agent had access to up to this point
    search_evidence = []
    step_index = step.get('step_index', 0)
    
    # Collect all evidence from previous result steps
    for i in range(step_index):
        prev_step = trace[i]
        # Handle doc-based results
        if prev_step.get("type") in ["search_result", "scholar_result"] and "documents" in prev_step:
            search_evidence.extend(prev_step.get("documents", []))
        # Handle content-based results and unify them into the documents format
        elif prev_step.get("type") == "visit_result" and "content" in prev_step:
            search_evidence.append({"title": "Visited Content", "content": prev_step.get("content")})
        elif prev_step.get("type") == "file_result" and "content" in prev_step:
            search_evidence.append({"title": "Parsed File Content", "content": prev_step.get("content")})
        elif prev_step.get("type") == "python_result" and "content" in prev_step:
            search_evidence.append({"title": "Python Execution Output", "content": prev_step.get("content")})
    
    # If no search evidence found, try to get the immediate parent search result (legacy check)
    if not search_evidence:
        parent_index = step.get('trace_dependency', {}).get('dependent_on')
        if parent_index is not None and (0 <= parent_index < len(trace)):
            parent_step = trace[parent_index]
            if parent_step.get("type") == "search_result":
                search_evidence = parent_step.get("documents", [])
    
    # If still no evidence, create a placeholder
    if not search_evidence:
        search_evidence = [{"error": "No search evidence found for this reasoning step"}]

    prompt = PREMISE_EVALUATION_PROMPT.format(
        question=question,
        search_evidence_json=json.dumps(search_evidence, indent=2),
        reasoning_text=text_to_analyze  # Use the dynamically extracted text here
    )
    
    llm_response = await call_llm(prompt, model) # Reusing the robust call_llm

    if llm_response:
        # Ensure attributes container exists
        if "annotation" not in step:
            step["annotation"] = {"type": step.get("type", None)}
        if "attributes" not in step.get("annotation", {}):
            step["annotation"]["attributes"] = {}

        # Extract schema with backward compatibility
        llm_pg = llm_response.get("groundness", llm_response.get("premiseGrounding"))
        llm_anchor = llm_response.get("anchor_type", llm_response.get("anchorType", "NONE"))
        llm_citations = llm_response.get("evidence_citations", llm_response.get("citations", []))
        llm_unmatched = llm_response.get("unmatched_premises", llm_response.get("unmatchedPremises", []))
        llm_just = (
            llm_response.get("premise_justification")
            or llm_response.get("justification")
            or "Unspecified"
        )

        # Guardrail: For reasoning step types, validate grounding based on anchor_type
        annotation_type = step.get("annotation", {}).get("type")
        if annotation_type in ["StateAssessment", "PlanFormation", "InformationSynthesis", "CritiqueAndCorrection"]:
            # If anchor_type is EVIDENCE, require evidence citations for Directly Grounded
            if llm_anchor == "EVIDENCE":
                if not llm_citations:
                    llm_pg = "Not Grounded"
            # If there are unmatched premises, mark as Not Grounded
            if isinstance(llm_unmatched, list) and len(llm_unmatched) > 0:
                llm_pg = "Not Grounded"

        # Normalize labels to match downstream analysis expectations.
        if llm_pg in ["Directly Grounded", "Grounded"]:
            llm_pg = "Grounded"
        elif llm_pg in ["NotGrounded", "Ungrounded"]:
            llm_pg = "Not Grounded"

        if llm_anchor not in {"EVIDENCE", "QUESTION", "TRACE", "NONE"}:
            llm_anchor = "NONE"

        # Final write with explicit fields
        step["annotation"]["attributes"]["groundness"] = llm_pg or "Unspecified"
        step["annotation"]["attributes"]["anchor_type"] = llm_anchor or "NONE"
        step["annotation"]["attributes"]["evidence_citations"] = llm_citations or []
        step["annotation"]["attributes"]["unmatched_premises"] = llm_unmatched or []
        step["annotation"]["attributes"]["premise_justification"] = llm_just


async def annotate_trace(trace, ontology, lock, ground_truth=None, question=None, model=None):
    """Processes all annotations for a single trace."""
    # Add a step_index to each step for clear referencing.
    for i, step in enumerate(trace):
        step['step_index'] = i
    
    # Initialize the cumulative evidence store for this trace
    cumulative_evidence = []

    # --- PASS 1: Basic Annotation (The "What") ---
    # This loop now handles the new evidence evaluation logic
    for i in range(len(trace)):
        current_step = trace[i]
        step_type = current_step.get("type")
        
        # --- New Logic for Search Results ---
        if step_type == "search_result":
            # Set dependency
            current_step["trace_dependency"] = {"dependent_on": i - 1 if i > 0 else None}
            # Find the parent search query
            if i > 0 and trace[i-1].get("type") == "search":
                current_step["parent_query"] = trace[i-1].get("query", [])
            else:
                current_step["parent_query"] = []
            
            await annotate_search_result_globally(current_step, question, cumulative_evidence, model)
        
        # --- Existing Logic for Other Step Types ---
        else:
            await annotate_step(trace, i, ontology, lock, ground_truth, model)

    # --- PASS 2: Premise Evaluation (The "Why") ---
    # Evaluate the premise for ALL non-result steps that should have it.
    for step in trace:
        step_type = step.get("type")
        if step_type not in ["search_result", "visit_result", "scholar_result", "file_result", "python_result"] and not step_type.endswith("Answer"):
            await evaluate_groundness(step, trace, question, model)
             
    return trace


async def main():
    parser = argparse.ArgumentParser(description="Annotate agent traces using OpenAI.")
    parser.add_argument("--input_file", required=True, help="Path to the input .jsonl file.")
    parser.add_argument("--output_file", required=True, help="Path to the output .jsonl file.")
    parser.add_argument("--ontology_file", default=DEFAULT_ONTOLOGY_PATH, help="Path to the ontology JSON file.")
    parser.add_argument("--concurrency", type=int, default=30, help="Number of concurrent requests to OpenAI.")
    parser.add_argument("--model", default="gpt-4.1-mini", help="Model to use for annotation.")
    parser.add_argument("--agent_model", default="Qwen3-30B-A3B-Instruct-2507", help="Model to use by the agent")
    parser.add_argument("--dataset", default="ChatDKU", help="dataset for evaluation")
    args = parser.parse_args()

    try:
        ontology_file=os.path.abspath(args.ontology_file)
        with open(ontology_file, 'r') as f:
            ontology = json.load(f)
        logging.info(f"Successfully loaded ontology from {args.ontology_file}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Failed to load ontology from {args.ontology_file}: {e}")
        return
    
    input_file=os.path.abspath(args.input_file)

    with open(input_file, 'r') as infile:
        traces = [json.loads(line) for line in infile]

    ontology_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(args.concurrency)

    async def process_and_annotate_trace(trace_data):
        async with semaphore:
            try:
                # Make a deep copy to avoid modifying original data in case of partial failure
                processed_trace = json.loads(json.dumps(trace_data['trace']))
                ground_truth = [trace_data.get('ground_truth')]
                question = trace_data.get('question') # <-- Get the question



                # Pass the question to the annotation function
                processed_trace = await annotate_trace(processed_trace, ontology, ontology_lock, ground_truth, question=question, model=args.model)

                trace_data['trace'] = processed_trace
                return trace_data
            except Exception as e:
                logging.error(f"A critical error occurred while processing a trace: {e}. Trace was not written to output.", exc_info=True)
                logging.error(f"Original trace that caused failure: {json.dumps(trace_data)}")
                return None

    tasks = [process_and_annotate_trace(trace_data) for trace_data in traces]

    output_file=os.path.abspath(args.output_file)

    with open(output_file, 'w') as outfile:
        for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Annotating Traces"):
            result = await future
            if result:
                id_=uuid.uuid4()
                result.update(
                    {
                        'dataset':args.dataset,
                        'model':args.agent_model,
                        'id':str(id_)
                    }
                )


                outfile.write(json.dumps(result) + '\n')

    try:
        with open(ontology_file, 'w') as f:
            json.dump(ontology, f, indent=2)
        logging.info(f"Ontology updated and saved back to {args.ontology_file}")
    except Exception as e:
        logging.error(f"Failed to save updated ontology to {args.ontology_file}: {e}")


    logging.info(f"Annotation complete. Output saved to {args.output_file}")

if __name__ == "__main__":
    asyncio.run(main()) 