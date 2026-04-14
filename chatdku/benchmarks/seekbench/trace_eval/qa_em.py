# Copyright 2024 Bytedance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import string
import random

def normalize_answer(s):
    def remove_articles(text):
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def em_check(prediction, golden_answers):
    if isinstance(golden_answers, str):
        golden_answers = [golden_answers]
    normalized_prediction = normalize_answer(prediction)
    score = 0
    for golden_answer in golden_answers:
        golden_answer = normalize_answer(golden_answer)
        if golden_answer == normalized_prediction:
            score = 1
            break
    return score


def subem_check(prediction, golden_answers):
    if isinstance(golden_answers, str):
        golden_answers = [golden_answers]
    normalized_prediction = normalize_answer(prediction)
    score = 0
    for golden_answer in golden_answers:
        golden_answer = normalize_answer(golden_answer)
        if golden_answer in normalized_prediction:
            score = 1
            break
    return score


def extract_solution(solution_str):
    """Extract the answer from the solution string."""
    
    # Find all possible answer markers
    tag_matches = list(re.finditer(r'<answer>', solution_str))
    alt_matches = list(re.finditer(r'^\s*[Aa]nswer:', solution_str, re.MULTILINE))

    last_tag_pos = tag_matches[-1].start() if tag_matches else -1
    last_alt_pos = alt_matches[-1].start() if alt_matches else -1

    if last_tag_pos == -1 and last_alt_pos == -1:
        return None

    if last_tag_pos > last_alt_pos:
        # The last answer is in an <answer> tag
        content_part = solution_str[last_tag_pos + len('<answer>'):]
        if '</answer>' in content_part:
            content = content_part.split('</answer>', 1)[0]
        else:
            content = content_part
        return content.strip()
    else:
        # The last answer is in "Answer: " format
        # Re-run a capturing regex on the part of the string from the last match on.
        match = re.search(r'^\s*[Aa]nswer:\s*(.*)', solution_str[last_alt_pos:], re.MULTILINE | re.DOTALL)
        if match:
            return match.group(1).strip()

    return None


def compute_score_em(solution_str, ground_truth, method='strict', format_score=0., score=1., do_print=False):
    """The scoring function for exact match (EM).

    Args:
        solution_str: the solution text
        ground_truth: the ground truth
        method: the method to extract the solution, choices are 'strict' and 'flexible'
        format_score: the score for the format
        score: the score for the correct answer
    """
    answer = extract_solution(solution_str)
    
    if do_print:
        print(f"--------------------------------")
        print(f"Golden answers: {ground_truth['target']}")
        print(f"Extracted answer: {answer}")
        print(f"Solution string: {solution_str}")
    
    if answer is None:
        return 0
    else:
        if em_check(answer, ground_truth['target']):
            return score
        else:
            return format_score


def compute_score_subem(solution_str, ground_truth, method='strict', format_score=0., score=1.):
    """The scoring function for substring exact match (EM).

    Args:
        solution_str: the solution text
        ground_truth: the ground truth
        method: the method to extract the solution, choices are 'strict' and 'flexible'
        format_score: the score for the format
        score: the score for the correct answer
    """
    answer = extract_solution(solution_str=solution_str)
    do_print = random.randint(1, 64) == 1
    
    if do_print:
        print(f"--------------------------------")
        print(f"Golden answers: {ground_truth['target']}")
        print(f"Extracted answer: {answer}")
        print(f"Solution string: {solution_str}")
    
    if answer is None:
        return 0
    else:
        if subem_check(answer, ground_truth['target']):
            return score
        else:
            return format_score


def f1_check(prediction, golden_answers):
    if isinstance(golden_answers, str):
        golden_answers = [golden_answers]
    
    normalized_prediction = normalize_answer(prediction)
    max_f1 = 0.0

    for golden_answer in golden_answers:
        normalized_golden = normalize_answer(golden_answer)
        
        pred_tokens = set(normalized_prediction.split())
        golden_tokens = set(normalized_golden.split())

        if not golden_tokens or not pred_tokens:
            continue

        common_tokens = pred_tokens & golden_tokens
        
        precision = len(common_tokens) / len(pred_tokens)
        recall = len(common_tokens) / len(golden_tokens)
        
        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
            if f1 > max_f1:
                max_f1 = f1
    
    return max_f1


def compute_score_f1(solution_str=None, ground_truth=None, method='strict', format_score=0., score=1., answer=None):
    """The scoring function for F1 score.

    Args:
        solution_str: the solution text
        ground_truth: the ground truth
        method: the method to extract the solution, choices are 'strict' and 'flexible'
        format_score: the score for the format
        score: the score for the correct answer
    """
    if answer is None:
        if solution_str is not None:
            answer = extract_solution(solution_str=solution_str)
        else:
            return 0.
    
    if answer is None:
        return 0.
    else:
        return f1_check(answer, ground_truth['target'])