# Indexes all Serey platform knowledge into ChromaDB collection 'serey_knowledge'.
# Run from the backend/ directory: python scripts/index_serey_knowledge.py
# Re-run whenever serey_knowledge_catalog.py is updated.

import chromadb
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts.serey_knowledge_catalog import SEREY_KNOWLEDGE


def index_all():
    chroma_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chroma_db")
    )
    client = chromadb.PersistentClient(path=chroma_path)

    # Delete and recreate for a clean re-index
    try:
        client.delete_collection("serey_knowledge")
        print("🗑  Deleted existing 'serey_knowledge' collection.")
    except Exception:
        pass

    collection = client.create_collection(
        name="serey_knowledge",
        metadata={"hnsw:space": "cosine"},
    )

    documents, metadatas, ids = [], [], []

    for entry in SEREY_KNOWLEDGE:
        # Embed: title + content together for richer semantic matching
        doc_text = f"{entry['title']}\n\n{entry['content']}"
        documents.append(doc_text)
        metadatas.append({
            "id": entry["id"],
            "category": entry["category"],
            "title": entry["title"],
            "content": entry["content"],
        })
        ids.append(entry["id"])

    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    count = collection.count()
    print(f"✅ Indexed {count} Serey knowledge entries into ChromaDB.")


if __name__ == "__main__":
    index_all()
