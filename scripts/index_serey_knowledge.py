# Indexes all Serey platform knowledge into ChromaDB collection 'serey_knowledge'.
# Run from the backend/ directory: python scripts/index_serey_knowledge.py
# Re-run whenever serey_knowledge_catalog.py is updated.

import chromadb
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts.serey_knowledge_catalog import SEREY_KNOWLEDGE, CONTEXTUAL_PREFIXES


def index_all():
    chroma_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chroma_db")
    )

    documents, metadatas, ids = [], [], []
    for entry in SEREY_KNOWLEDGE:
        # Embed: contextual prefix (if any) + title + content for richer semantic matching.
        # The prefix is only used for embedding — stored metadata keeps the original content.
        prefix = CONTEXTUAL_PREFIXES.get(entry["id"], "")
        doc_text = (
            f"{prefix}\n\n{entry['title']}\n\n{entry['content']}"
            if prefix
            else f"{entry['title']}\n\n{entry['content']}"
        )
        documents.append(doc_text)
        metadatas.append({
            "id": entry["id"],
            "category": entry["category"],
            "title": entry["title"],
            "content": entry["content"],
        })
        ids.append(entry["id"])

    # Delete + recreate + add can intermittently raise "Collection [uuid] does not exist"
    # due to a stale client cache. Retry with a fresh client so we never leave the KB wiped.
    last_err = None
    for attempt in range(1, 4):
        client = chromadb.PersistentClient(path=chroma_path)
        try:
            try:
                client.delete_collection("serey_knowledge")
            except Exception:
                pass
            collection = client.create_collection(
                name="serey_knowledge",
                metadata={"hnsw:space": "cosine"},
            )
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            count = collection.count()
            print(f"Indexed {count} Serey knowledge entries into ChromaDB.")
            return
        except Exception as e:
            last_err = e
            print(f"Re-index attempt {attempt} failed: {e}")
    raise RuntimeError(f"Failed to index serey_knowledge after 3 attempts: {last_err}")


if __name__ == "__main__":
    index_all()
