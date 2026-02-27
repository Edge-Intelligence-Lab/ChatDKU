import chromadb
from chromadb.utils.embedding_functions import HuggingFaceEmbeddingServer

from chatdku.config import config
from chatdku.core.tools.retriever.base_retriever import BaseDocRetriever, NodeWithScore
from chatdku.core.tools.utils import get_url


class VectorRetriever(BaseDocRetriever):
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
        Retrieve texts from the database that are
        semantically similar to the query.
        """
        db = chromadb.HttpClient(host=config.chroma_host, port=config.chroma_db_port)
        collection = db.get_collection(
            name=config.chroma_collection,
            embedding_function=HuggingFaceEmbeddingServer(
                url=config.tei_url + "/" + config.embedding + "/embed"
            ),
        )

        query_result = collection.query(
            query_texts=query,
            n_results=self.retriever_top_k,
            where=self.__get_chroma_filter(),
        )
        retrieved_nodes = self.chroma_result_to_nodes(query_result)
        return retrieved_nodes

    def __get_chroma_filter(
        self,
    ) -> dict:
        """
        Read the following to understand the logic of the filters:
        https://docs.trychroma.com/docs/querying-collections/metadata-filtering
        """
        search_mode = self.search_mode
        user_id = self.user_id
        exclude = self.exclude
        files = self.files
        if search_mode == 0:
            filters = {"user_id": user_id}
            if exclude:
                filters = {
                    "$and": [
                        {"user_id": user_id},
                        {"chunk_id": {"$nin": exclude}},
                    ]
                }

        # search from user's files
        elif search_mode == 1:
            filters = {
                "$and": [
                    {"user_id": user_id},
                    {"file_name": {"$in": files}},
                ],
            }

            if exclude:
                filters["$and"].append({"chunk_id": {"$nin": exclude}})
        elif search_mode == 2:
            filters = {
                "$or": [
                    {
                        "$and": [
                            {"user_id": user_id},
                            {"file_name": {"$in": files}},
                        ],
                    },
                    {"user_id": "Chat_DKU"},
                ],
            }
            if exclude:
                filters = {
                    "$and": [
                        {
                            "$or": [
                                {
                                    "$and": [
                                        {"user_id": user_id},
                                        {"file_name": {"$in": files}},
                                    ]
                                },
                                {"user_id": "Chat_DKU"},
                            ]
                        },
                        {"chunk_id": {"$nin": exclude}},
                    ]
                }
        return filters

    def chroma_result_to_nodes(self, result: dict) -> list[NodeWithScore]:
        ids = result["ids"][0]
        texts = result["documents"][0]
        metadatas = result["metadatas"][0]
        scores = result["distances"][0]

        return [
            NodeWithScore(
                node_id=ids[i],
                text=texts[i],
                metadata={
                    "file_name": metadatas[i]["file_name"],
                    "url": get_url(metadatas[i]),
                    "page_number": metadatas[i]["page_number"],
                },
                score=float(scores[i]),
            )
            for i in range(len(ids))
        ]
