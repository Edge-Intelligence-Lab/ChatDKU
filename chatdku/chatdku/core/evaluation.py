from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict

class TransformerEvaluator:
    def __init__(self, model_name: str = "sentence-transformers/all-mpnet-base-v2"):
        """
        Initialize the evaluator with a sentence transformer model.
        Args:
            model_name (str): The name of the sentence transformer model.
        """
        self.model = SentenceTransformer(model_name)

    def evaluate(self, user_query: str, generated_answer: str, context: List[str]) -> Dict[str, float]:
        """
        Evaluates the generated response using semantic similarity metrics.
        Args:
            user_query (str): The user's query.
            generated_answer (str): The model's generated response.
            context (List[str]): A list of retrieved contexts.
        Returns:
            Dict[str, float]: Evaluation metrics scores.
        """
        # Encode query, answer, and context
        query_embedding = self.model.encode([user_query])
        answer_embedding = self.model.encode([generated_answer])
        context_embeddings = self.model.encode(context)

        # Compute scores
        faithfulness = self._faithfulness(answer_embedding, context_embeddings)
        answer_relevancy = self._cosine_similarity(answer_embedding, query_embedding)
        context_precision = self._precision(answer_embedding, context_embeddings)
        context_recall = self._recall(answer_embedding, context_embeddings)
        context_relevancy = self._f1_score(context_precision, context_recall)

        return {
            "Faithfulness": faithfulness,
            "Answer Relevancy": answer_relevancy,
            "Context Precision": context_precision,
            "Context Recall": context_recall,
            "Context Relevancy": context_relevancy,
        }

    def _cosine_similarity(self, vec_a, vec_b) -> float:
        """
        Compute cosine similarity between two vectors.
        """
        return float(cosine_similarity(vec_a, vec_b)[0][0])

    def _faithfulness(self, answer_embedding, context_embeddings) -> float:
        """
        Compute the average cosine similarity of the answer to the context.
        """
        similarities = cosine_similarity(answer_embedding, context_embeddings)
        return float(similarities.mean())

    def _precision(self, answer_embedding, context_embeddings) -> float:
        """
        Compute precision: the proportion of the answer that aligns with the context.
        """
        similarities = cosine_similarity(answer_embedding, context_embeddings)
        return float(similarities.max(axis=1).mean())  # Max similarity for each context

    def _recall(self, answer_embedding, context_embeddings) -> float:
        """
        Compute recall: the proportion of the context captured by the answer.
        """
        similarities = cosine_similarity(context_embeddings, answer_embedding)
        return float(similarities.max(axis=1).mean())  # Max similarity for each answer

    def _f1_score(self, precision: float, recall: float) -> float:
        """
        Compute F1 score based on precision and recall.
        """
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)
