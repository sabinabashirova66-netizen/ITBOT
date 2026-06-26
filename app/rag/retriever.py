"""Гибридный поиск: ChromaDB (векторный) + BM25, объединение через RRF."""
import os
import logging
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = "codestart_kb"
TOP_K = 3
RRF_VECTOR_WEIGHT = 0.6
RRF_BM25_WEIGHT = 0.4
RRF_K = 60


@dataclass
class RetrievedChunk:
    text: str
    category: str
    source: str
    score: float


class HybridRetriever:
    def __init__(self) -> None:
        self._client: chromadb.HttpClient | None = None
        self._collection = None
        self._model: SentenceTransformer | None = None
        self._all_docs: list[dict] | None = None
        self._bm25: BM25Okapi | None = None

    def _ensure_connected(self) -> bool:
        if self._collection is not None:
            return True
        try:
            self._client = chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_collection(COLLECTION_NAME)
            self._model = SentenceTransformer("intfloat/multilingual-e5-small")
            self._load_bm25_index()
            logger.info("Retriever подключён к ChromaDB")
            return True
        except Exception as e:
            logger.error("ChromaDB недоступна: %s", e)
            self._collection = None
            return False

    def _load_bm25_index(self) -> None:
        result = self._collection.get(include=["documents", "metadatas"])
        self._all_docs = [
            {"id": id_, "text": doc, "metadata": meta}
            for id_, doc, meta in zip(
                result["ids"], result["documents"], result["metadatas"]
            )
        ]
        tokenized = [doc["text"].lower().split() for doc in self._all_docs]
        self._bm25 = BM25Okapi(tokenized)

    def _vector_search(self, query: str, n: int) -> list[tuple[int, float]]:
        embedding = self._model.encode([query]).tolist()
        results = self._collection.query(
            query_embeddings=embedding,
            n_results=min(n, len(self._all_docs)),
            include=["documents", "metadatas", "distances"],
        )
        ids = results["ids"][0]
        distances = results["distances"][0]
        id_to_index = {doc["id"]: i for i, doc in enumerate(self._all_docs)}
        return [(id_to_index[id_], 1 - dist) for id_, dist in zip(ids, distances)]

    def _bm25_search(self, query: str, n: int) -> list[tuple[int, float]]:
        scores = self._bm25.get_scores(query.lower().split())
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:n]

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[tuple[int, float]],
        bm25_results: list[tuple[int, float]],
    ) -> list[tuple[int, float]]:
        scores: dict[int, float] = {}
        for rank, (idx, _) in enumerate(vector_results):
            scores[idx] = scores.get(idx, 0) + RRF_VECTOR_WEIGHT / (RRF_K + rank + 1)
        for rank, (idx, _) in enumerate(bm25_results):
            scores[idx] = scores.get(idx, 0) + RRF_BM25_WEIGHT / (RRF_K + rank + 1)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        if not self._ensure_connected():
            return []

        candidate_n = TOP_K * 5
        vector_results = self._vector_search(query, candidate_n)
        bm25_results = self._bm25_search(query, candidate_n)
        fused = self._reciprocal_rank_fusion(vector_results, bm25_results)

        chunks = []
        for idx, score in fused[:TOP_K]:
            doc = self._all_docs[idx]
            chunks.append(RetrievedChunk(
                text=doc["text"],
                category=doc["metadata"].get("category", ""),
                source=doc["metadata"].get("source", ""),
                score=score,
            ))
        return chunks

    def format_context(self, query: str) -> str:
        chunks = self.retrieve(query)
        if not chunks:
            return ""
        parts = []
        for chunk in chunks:
            parts.append(f"[{chunk.category.upper()}]\n{chunk.text}")
        return "\n\n---\n\n".join(parts)


retriever = HybridRetriever()
