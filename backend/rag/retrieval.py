import os
from pathlib import Path

import numpy as np
from google import genai

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "documents"
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")


def load_documents() -> list[dict]:
    documents = []

    for path in sorted(DATA_DIR.glob("*.txt")):
        content = path.read_text(encoding="utf-8")
        documents.append({"source": path.name, "content": content})

    return documents


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        return 0.0
    return float(np.dot(a, b) / denominator)


def search_documents(question: str, top_k: int = 3) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    documents = load_documents()

    if not documents:
        return []

    if not api_key:
        words = {word.lower().strip(".,?!") for word in question.split() if len(word) > 2}
        scored = []
        for document in documents:
            text = document["content"].lower()
            score = sum(1 for word in words if word in text)
            scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:top_k] if item[0] > 0]

    client = genai.Client(api_key=api_key)
    texts = [question] + [document["content"] for document in documents]
    result = client.models.embed_content(model=EMBEDDING_MODEL, contents=texts)
    vectors = [np.array(item.values, dtype=float) for item in result.embeddings]
    query_vector = vectors[0]

    scored = []
    for document, vector in zip(documents, vectors[1:]):
        scored.append((_cosine_similarity(query_vector, vector), document))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] | {"score": round(item[0], 4)} for item in scored[:top_k]]
