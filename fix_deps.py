"""Fix qdrant-client Python 3.12 compatibility issue."""
import subprocess, sys, json

PYTHON = sys.executable
log = []

def run(args, label):
    r = subprocess.run([PYTHON, "-m"] + args, capture_output=True, text=True)
    log.append(f"=== {label} ===")
    log.append(r.stdout.strip())
    if r.returncode != 0:
        log.append("STDERR: " + r.stderr.strip())
    return r.returncode == 0

# Step 1: Install pinned versions
run(["pip", "install", "qdrant-client==1.12.1", "protobuf<5.0.0", "-q"], "pip install")

# Step 2: Check version
run(["pip", "show", "qdrant-client"], "qdrant version")

# Step 3: Test mem0 import
r = subprocess.run([PYTHON, "-c", "from mem0 import MemoryClient; print('MemoryClient import OK')"],
                   capture_output=True, text=True)
log.append("=== mem0 import test ===")
log.append((r.stdout + r.stderr).strip())

# Step 4: Test chromadb search
r2 = subprocess.run([PYTHON, "-c", """
import chromadb
c = chromadb.PersistentClient(path='chroma_db')
col = c.get_collection('components')
print('ChromaDB count:', col.count())
r = col.get(include=['metadatas'])
print('Components:', [m['name'] for m in r['metadatas']])
q = col.query(query_texts=['pricing plans'], n_results=2)
print('Search(pricing):', [m['name'] for m in q['metadatas'][0]])
q2 = col.query(query_texts=['hero landing page'], n_results=2)
print('Search(hero):', [m['name'] for m in q2['metadatas'][0]])
"""], capture_output=True, text=True, cwd=r"C:\Users\Draxler\Documents\SEREY\SEREY-AI-builder\backend")
log.append("=== ChromaDB check ===")
log.append((r2.stdout + r2.stderr).strip())

output = "\n".join(log)
with open("fix_deps_result.txt", "w") as f:
    f.write(output)
print(output)
