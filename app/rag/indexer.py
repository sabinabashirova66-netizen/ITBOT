"""
Индексирует базу знаний в ChromaDB.
Запуск: python -m app.rag.indexer
"""
import os
import re
import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_DIR = Path(__file__).parent / "knowledge_base"
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = "codestart_kb"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 90  # ~15% от 600


def _split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    tokens = text.split()
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk = " ".join(tokens[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def _load_documents() -> list[dict]:
    category_map = {
        "courses.txt": "catalog",
        "faq.txt": "faq",
        "cases.txt": "cases",
    }
    docs = []
    for filename, category in category_map.items():
        filepath = KNOWLEDGE_BASE_DIR / filename
        if not filepath.exists():
            logger.warning("Файл не найден: %s", filepath)
            continue
        raw = filepath.read_text(encoding="utf-8")
        chunks = _split_into_chunks(raw)
        for i, chunk in enumerate(chunks):
            docs.append({
                "text": chunk,
                "metadata": {
                    "category": category,
                    "source": filename,
                    "chunk_index": i,
                },
                "id": f"{filename}_{i}",
            })
        logger.info("Загружено %d чанков из %s", len(chunks), filename)
    return docs


def run_indexing() -> None:
    logger.info("Подключение к ChromaDB %s:%s", CHROMA_HOST, CHROMA_PORT)
    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        settings=Settings(anonymized_telemetry=False),
    )

    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info("Старая коллекция удалена")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    model = SentenceTransformer("intfloat/multilingual-e5-small")
    logger.info("Модель эмбеддингов загружена")

    docs = _load_documents()
    if not docs:
        logger.error("Нет документов для индексации")
        return

    texts = [d["text"] for d in docs]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    collection.add(
        ids=[d["id"] for d in docs],
        embeddings=embeddings,
        documents=texts,
        metadatas=[d["metadata"] for d in docs],
    )
    logger.info("Индексация завершена. Добавлено %d чанков", len(docs))


if __name__ == "__main__":
    run_indexing()
