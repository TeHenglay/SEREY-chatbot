# One-time script to index all components into ChromaDB.
# Run from the backend/ directory: python scripts/index_components.py
# Re-run whenever component_catalog.py is updated.

import chromadb
import json
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from scripts.component_catalog import COMPONENTS


def index_all():
    client = chromadb.PersistentClient(path="./chroma_db")

    # Delete and recreate for a clean re-index
    try:
        client.delete_collection("components")
        print("🗑  Deleted existing 'components' collection.")
    except Exception:
        pass

    collection = client.create_collection(
        name="components",
        metadata={"hnsw:space": "cosine"},
    )

    documents, metadatas, ids = [], [], []

    for i, comp in enumerate(COMPONENTS):
        doc_text = (
            f"Component: {comp['name']}\n"
            f"Description: {comp['description']}\n"
            f"Props: {json.dumps(comp['props'], indent=2)}\n"
            f"Example usage: {json.dumps(comp['example'], indent=2)}"
        )
        documents.append(doc_text)
        metadatas.append({
            "name": comp["name"],
            "example_json": json.dumps(comp["example"]),
        })
        ids.append(f"comp_{i}")

    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    count = collection.count()
    print(f"✅ Indexed {count} components into ChromaDB.")


if __name__ == "__main__":
    index_all()
