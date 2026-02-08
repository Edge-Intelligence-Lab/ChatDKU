import os
import re
import string
from itertools import combinations

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from redis import Redis
from redis.commands.search.query import Query
from redisvl.schema import IndexSchema

from chatdku.config import config
from chatdku.core.tools.retriever.base_retriever import BaseDocRetriever, NodeWithScore
from chatdku.core.tools.utils import get_url


class KeywordRetriever(BaseDocRetriever):
    def __init__(
        self,
        internal_memory: dict,
        retriever_top_k: int = 25,
        user_id: str = "Chat_DKU",
        search_mode: int = 0,
        files: list | None = None,
    ):
        super().__init__(
            internal_memory,
            retriever_top_k,
            user_id,
            search_mode,
            files,
        )

    def query(self, query: str) -> list[NodeWithScore]:
        """
        Retrieve texts from the database that contain the
        same keywords in the query.
        """
        client = Redis(
            host=config.redis_host,
            port=6379,
            username="default",
            password=config.redis_password,
            db=0,
        )

        schema = IndexSchema.from_yaml(
            os.path.join(config.module_root_dir, "custom_schema.yaml")
        )
        index_name = schema.index.name

        # Escape all punctuations, e.g. "can't" -> "can\'t"
        def _escape_strs(strs: list[str]):
            if strs:
                pattern = f"[{re.escape(string.punctuation)}]"
                return [
                    re.sub(pattern, lambda match: f"\\{match.group(0)}", s)
                    for s in strs
                ]
            else:
                return []

        def _extract_keywords(query):
            tokens = word_tokenize(query.lower())
            stop_words = set(stopwords.words("english"))
            # Keep tokens that are not stopwords and not pure punctuation
            keywords = [
                t
                for t in tokens
                if t not in stop_words and t not in string.punctuation and len(t) > 1
            ]
            return keywords

        # Sometimes the LLM inputs a list of strings
        # instead of a single string. So we need to
        # handle that case.
        if isinstance(query, str):
            # Break down the query into tokens
            tokens = _extract_keywords(query)
            # Remove tokens that are PURELY punctuation
            orig_keywords = _escape_strs(tokens)

            # FIXME: Hack for improving performance with multiple keywords.
            # There ought to be better ways than this.
            # Combinations of the original keywords are generated
            # to "boost" the result,
            # e.g. searching for "a b" would become "a OR b OR (a AND b)".
            # Without boosting, documents with a lot of either just
            # "a" or "b" would be given a heavier preferences,
            # even though we would prefer documents with
            # both "a" and "b".
            # Larger weights are given to combinations of larger size.
            keywords = []
            weights = []
            # Changed this to 2 from 4
            # See issue #152
            TUPLE_LIMIT = 2
            BOOST_FACTOR = 2
            for i in range(1, TUPLE_LIMIT + 1):
                for combo in combinations(orig_keywords, i):
                    keywords.append(" ".join(combo))
                    weights.append(BOOST_FACTOR ** (i - 1))

            # Trying to preserve the original keyword combination too
            if len(orig_keywords) > 2:
                keywords.append(" ".join(orig_keywords))
                weights.append(BOOST_FACTOR ** (TUPLE_LIMIT + 1))

            # `|` means searching the union of the words/tokens.
            # `%` means fuzzy search with Levenshtein distance of 1.
            # Query attributes are used here to set the weight of the keywords.
            text_str = " | ".join(
                [
                    f"({keyword}) => {{ $weight: {weight} }}"
                    for keyword, weight in zip(keywords, weights)
                ]
            )
        elif isinstance(query, list):
            text_str = " | ".join(query)

        query_str = "@text:(" + text_str + ")"

        exclude = _escape_strs(self.exclude)
        exclude_str = " ".join([f"-@id:({e})" for e in exclude])
        if exclude_str:
            query_str += " " + exclude_str

        # See issue #175 for not using PARAMS
        query_cmd = (
            Query(query_str)
            .dialect(2)
            .scorer("BM25")
            .paging(0, self.retriever_top_k)
            .with_scores()
        )

        results = client.ft(index_name).search(query_cmd)
        retrieved_nodes = self.redis_result_to_nodes(results)

        return retrieved_nodes

    def redis_result_to_nodes(self, results) -> list[NodeWithScore]:
        return [
            NodeWithScore(
                node_id=doc.id,
                text=doc.text,
                metadata={
                    "filename": os.path.basename(doc.file_path),
                    "url": get_url({"file_path": doc.file_path}),
                    "page_number": doc.page_number,
                },
                score=float(doc.score),
            )
            for doc in results.docs
        ]

    def __add_redis_filter(self, query_str: str) -> str:
        # Adding the user_id filter if the user wants to search for
        if self.search_mode == 0:
            query_str = query_str + f" @user_id:{{{'Chat_DKU'}}}"

        elif self.search_mode == 1:
            if len(self.files) == 0:
                docs_str = os.path.splitext(self.files[0])[0]
            else:
                docs_str = "|".join(
                    f"{os.path.splitext(name)[0]}" for name in self.files
                )

            query_str = (
                query_str
                + f" @user_id:{{{self.user_id}}} "
                + f"@file_name:{{{docs_str}}}"
            )

        elif self.search_mode == 2:
            query_str = query_str + f" @user_id:{{{'Chat_DKU'}}}"
            # if len(self.files) == 0:
            #     docs_str = os.path.splitext(self.files[0])[0]
            # else:
            #     docs_str = "|".join(
            #         f"{os.path.splitext(name)[0]}" for name in self.files
            #     )
            #
            # user_clause = f"(@user_id:{{Chat_DKU}} | (@user_id:{{{self.user_id}}} @file_name:{{{docs_str}}}))"  # noqa: E501
            # query_str = query_str + f" {user_clause}"
