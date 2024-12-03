# Evaluation Metrics

---

## Automated Evaluation: How It Works in This Branch

### Running the Evaluation
In this branch, you can run the file `agent.py`, which automatically evaluates generated answers after they are produced.

### Key Details
- **Latency:** The latency for generating answers will be slightly higher because the evaluation is performed automatically after each generation.
- **Faithfulness Scores Disclaimer:**  
  - The faithfulness scores from this automated evaluation might appear **lower** than expected. This is because there is **no ground truth** for the generated answers during automated evaluation. Instead, the system approximates scores by comparing the retrieved context with the generated answers.
  - This limitation makes automated faithfulness evaluation less reliable for benchmarking but useful for rapid experimentation.

### Purpose of Automated Evaluation
The primary purpose of this automated evaluation is to facilitate **hyperparameter optimization** and **faster testing**. By approximating the evaluation scores, you can identify promising configurations without manual intervention.

### Manual Evaluation for Benchmarking
Despite the automated system, manual evaluation remains the **gold standard** for benchmarking. Final evaluations and comparisons will always rely on human judgment to ensure accuracy and reliability.

---

## Overview

This repository provides an evaluation framework for assessing Retrieval-Augmented Generation (RAG) systems. The framework uses five core metrics to evaluate the quality of retrieval and generation:

- **Faithfulness**
- **Answer Relevancy**
- **Context Precision**
- **Context Recall**
- **Context Relevancy**

These metrics are designed to address the limitations of traditional evaluation methods by focusing on the specific needs of RAG systems, combining robust retrieval with accurate and relevant generation.

---

## Why These Metrics?

### 1. Faithfulness
Faithfulness measures whether the generated response is factually accurate and grounded in the retrieved evidence. This is particularly important for preventing hallucination or unsubstantiated claims. 

**Comparison to Other Metrics:**
- Traditional metrics like BLEU and ROUGE focus on n-gram overlap, which does not guarantee factual correctness. For instance, a response could match the ground truth textually but still be factually incorrect.
- Perplexity evaluates the fluency of a model’s output but does not assess whether the content is factually accurate or grounded.

Faithfulness directly evaluates factual alignment, making it a more appropriate metric for RAG systems.

---

### 2. Answer Relevancy
Answer relevancy assesses whether the generated response directly addresses the query. It evaluates the alignment between the user's question and the generated answer.

**Comparison to Other Metrics:**
- BLEU, ROUGE, and METEOR measure similarity to a reference answer but can reward responses that match irrelevant parts of the reference.
- Perplexity cannot distinguish between relevant and irrelevant outputs, as it measures fluency rather than semantic appropriateness.

Answer relevancy emphasizes the utility of the output, ensuring it aligns with the user's intent.

---

### 3. Context Precision
Context precision evaluates how much of the retrieved evidence is relevant to the query. It focuses on minimizing noise in the retrieval process.

**Comparison to Other Metrics:**
- Recall@k and similar metrics measure retrieval coverage but do not penalize irrelevant retrieval. This can result in high scores even if much of the retrieved context is irrelevant.
- BLEU and ROUGE are unsuitable for assessing retrieval quality because they only compare generated answers to reference outputs.

Context precision is critical for evaluating the quality of retrieval in RAG systems, ensuring the retrieved context is useful for downstream generation.

---

### 4. Context Recall
Context recall measures how much of the relevant evidence is retrieved, ensuring completeness in the retrieval process.

**Comparison to Other Metrics:**
- Recall@k captures retrieval coverage but does not provide insight into the overall balance between relevance and noise. It may overemphasize retrieving more documents without ensuring their quality.
- Precision-based metrics alone fail to assess whether important context is missing.

By balancing precision and recall, context recall ensures that retrieval is both comprehensive and relevant.

---

### 5. Context Relevancy
Context relevancy measures the semantic alignment of the retrieved context with both the query and the generated response, providing a holistic assessment of retrieval quality.

**Comparison to Other Metrics:**
- Recall@k focuses on quantity without considering whether the retrieved context is semantically aligned with the query or response.
- BLEU, ROUGE, and METEOR do not evaluate retrieval at all, leaving a critical aspect of RAG systems unevaluated.

Context relevancy bridges the gap between retrieval and generation, making it essential for holistic RAG evaluation.

---

## Scoring System

Each metric is scored on a scale of **0 to 1**, where:

- **0:** Indicates poor performance, such as irrelevant retrieval or incoherent responses.
- **1:** Indicates excellent performance, with perfect alignment, relevance, or faithfulness.

### Score Interpretation

#### Faithfulness and Answer Relevancy
- **0.0 - 0.4:** The generated response contains significant errors or irrelevancies.
- **0.5 - 0.6:** The response is partially accurate but may include minor hallucinations or incomplete answers.
- **0.7 - 0.8:** The response is mostly accurate and relevant, with only subtle inaccuracies or omissions.
- **0.9 - 1.0:** The response is fully accurate and directly addresses the query.

#### Context Precision and Recall
- **0.0 - 0.4:** Retrieval includes irrelevant evidence (low precision) or misses most relevant evidence (low recall).
- **0.5 - 0.6:** Retrieval is moderately accurate but may miss critical elements or include some noise.
- **0.7 - 0.8:** Retrieval is high quality, capturing most relevant evidence while minimizing noise.
- **0.9 - 1.0:** Retrieval is comprehensive and highly precise, providing only relevant and complete evidence.

#### Context Relevancy
- **0.0 - 0.4:** The retrieved context does not align with the query or generated response.
- **0.5 - 0.6:** The context is partially relevant but lacks full alignment with the query or response.
- **0.7 - 0.8:** The context is mostly relevant, with minor misalignments.
- **0.9 - 1.0:** The context is fully relevant and enhances the generated response.

