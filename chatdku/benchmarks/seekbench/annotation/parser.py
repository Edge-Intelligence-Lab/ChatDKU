import json
import pickle
import re
import argparse
from typing import List, Dict, Any
import os

def parse_information(info_str: str) -> List[Dict[str, str]]:
    """Parses the content of an <information> block into a list of documents."""
    docs = []
    # Regex to find documents starting with 'Doc X' optionally with '(Title: "...")'
    doc_matches = re.finditer(r'Doc \d+(?:\(Title: "(?P<title>.*?)"\))?\s*(?P<content>.*?)(?=(Doc \d+|$))', info_str, re.DOTALL)
    for match in doc_matches:
        docs.append({
            "title": (match.group('title') or "").strip(),
            "content": match.group('content').strip()
        })
    return docs

def parse_sequences_str(sequence: str) -> Dict[str, Any]:
    """
    Parses the `sequences_str` field into a structured trace and final answer.
    """
    trace = []
    final_answer = ""
    
    assistant_part_match = re.search(r"<\|im_start\|>assistant\n([\s\S]*?)<\|im_end\|>", sequence)
    if not assistant_part_match:
        return {"trace": [], "final_answer": None, "queries": []}
        
    content = assistant_part_match.group(1).strip()
    
    # Regex to find all known tags. The text between matches is free-form reasoning.
    pattern = re.compile(r"(<think>[\s\S]*?<\/think>|<search>[\s\S]*?<\/search>|<information>[\s\S]*?<\/information>|<answer>[\s\S]*?<\/answer>)", re.DOTALL)
    
    cursor = 0
    queries = []
    for match in pattern.finditer(content):
        start, end = match.span()
        preceding_text = content[cursor:start].strip()
        if preceding_text:
            trace.append({"type": "reasoning", "content": preceding_text})
        
        tag_content = match.group(1)
        
        if tag_content.startswith("<think>"):
            trace.append({
                "type": "reasoning", # Merged as per schema
                "content": tag_content[len("<think>"): -len("</think>")].strip()
            })
        elif tag_content.startswith("<search>"):
            trace.append({
                "type": "search",
                "query": tag_content[len("<search>"): -len("</search>")].strip()
            })
            queries.append(tag_content[len("<search>"): -len("</search>")].strip())
        elif tag_content.startswith("<information>"):
            info_docs = parse_information(tag_content[len("<information>"): -len("</information>")].strip())
            trace.append({
                "type": "search_result",
                "documents": info_docs
            })
        elif tag_content.startswith("<answer>"):
            answer_text = tag_content[len("<answer>"): -len("</answer>")].strip()
            final_answer = answer_text
            # We will add the answer step later based on correctness
            
        cursor = end

    # There might be trailing reasoning text after the last tag
    trailing_text = content[cursor:].strip()
    if trailing_text:
        trace.append({"type": "reasoning", "content": trailing_text})

    return {"trace": trace, "final_answer": final_answer, "queries": queries}

def extract_structured_data_from_file(jsonl_path: str, flawed_data_file: str = None) -> List[Dict[str, Any]]:
    """
    Reads a .jsonl file, parses the 'sequences_str' for each line,
    and returns a list of structured data objects.
    """
    structured_results = []
    # Initialize flawed questions container safely
    flawed_questions = set()
    if flawed_data_file:
        try:
            with open(flawed_data_file, "rb") as f:
                loaded = pickle.load(f)
                # Be tolerant to list or set
                if isinstance(loaded, (set, list)):
                    flawed_questions = set(loaded)
                else:
                    flawed_questions = set()
        except FileNotFoundError:
            # No previous flawed file; start fresh
            flawed_questions = set()

        
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                print(data)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON from line {i+1}: {line.strip()}")
                continue
            if flawed_data_file and data.get("question") in flawed_questions:
                continue
            sequences_str = data.get("sequences_str", "")
            if not sequences_str.endswith("<|im_end|>"):
                print(f"Warning: sequences_str does not end with <|im_end|> for line {i+1}: {line.strip()}")
                sequences_str = sequences_str + "<|im_end|>"
            # Fix common tag mismatches and duplications
            # Count opening and closing answer tags
            open_tags = sequences_str.count("<answer>")
            print(f"Open tags: {open_tags}")
            close_tags = sequences_str.count("</answer>")
            print(f"close tags: {close_tags}")
            
            # Handle duplicate closing tags when there are more closing than opening tags
            if close_tags > open_tags:
                # Find all positions of closing tags
                positions = [m.start() for m in re.finditer("</answer>", sequences_str)]
                # Keep only the first 'open_tags' number of closing tags
                if open_tags > 0:
                    for pos in positions[open_tags:]:
                        sequences_str = sequences_str[:pos] + sequences_str[pos+9:]  # 9 is length of "</answer>"
                else:
                    # If no opening tags, remove all closing tags
                    sequences_str = sequences_str.replace("</answer>", "")
            
            # Handle missing closing tags
            elif open_tags > close_tags:
                # Add missing closing tags at the end
                sequences_str = sequences_str + "</answer>" * (open_tags - close_tags)
                
            parsed_info = parse_sequences_str(sequences_str)
            if len(parsed_info["queries"]) <= 1 and (data.get("is_correct") == 1.0 or len(parsed_info["queries"]) == 0):
                # add flawed question to the set (always track in-memory; file persists only if path provided)
                q = data.get("question")
                if isinstance(q, str):
                    flawed_questions.add(q)
                print(f"Single query, skipping: {data.get('question')}")
                continue
            # Add the final answer node with correctness
            trace = parsed_info["trace"]
            if parsed_info["final_answer"]:
                is_correct = data.get("is_correct") == 1.0
                answer_node_type = "CorrectAnswer" if is_correct else "IncorrectAnswer"
                trace.append({
                    "type": answer_node_type,
                    "content": parsed_info["final_answer"]
                })

            structured_data = {
                "question": data.get("question"),
                "ground_truth": data.get("ground_truth", {}).get("target", []),
                "reward": data.get("reward"),
                "is_correct": data.get("is_correct") == 1.0,
                "trace": trace,
                "final_answer": parsed_info["final_answer"],
                "queries": parsed_info["queries"]
            }
            structured_results.append(structured_data)
    if flawed_data_file:
        with open(flawed_data_file, "wb") as f:
            pickle.dump(flawed_questions, f)
            
    return structured_results

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Extract structured data from evaluation result .jsonl files.")
    parser.add_argument("input_file", type=str, help="Path to the input .jsonl file.")
    parser.add_argument("-o", "--output_file", type=str, help="Path to the output .jsonl file. If not provided, prints to stdout.")
    parser.add_argument("--flawed_data_file", type=str, default=None, help="Path to the flawed data file.")
    
    args = parser.parse_args()
    print("processing:", args.input_file)
    input_file=os.path.abspath(args.input_file)
    structured_data = extract_structured_data_from_file(input_file, args.flawed_data_file)
    
    if args.output_file:
        output_file=os.path.abspath(args.output_file)
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in structured_data:
                f.write(json.dumps(item) + '\n')
        print(f"Successfully processed {len(structured_data)} items and saved to {args.output_file}")
    else:
        for item in structured_data:
            print(json.dumps(item))

if __name__ == '__main__':
    main() 