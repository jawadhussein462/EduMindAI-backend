import json


def inspect_parsed_docs(path="outputs/parsed_docs.jsonl", sample=3):
    with open(path, "r") as f:
        lines = [json.loads(l) for l in f]
    print(f"🧾 Parsed entries: {len(lines)}")
    for doc in lines[:sample]:
        print("\n📄 Source:", doc["metadata"].get("source"))
        print("📚 Subject:", doc["metadata"].get("subject"))
        print("📖 Snippet:", doc["content"][:300])


def inspect_chunked_docs(path="outputs/chunked_docs.jsonl", sample=5):
    with open(path, "r") as f:
        chunks = [json.loads(l) for l in f]
    print(f"🧩 Total chunks: {len(chunks)}")

    for ch in chunks[:sample]:
        print(
            "\n🧠 Grade:",
            ch["metadata"].get("grade"),
            "| Subject:",
            ch["metadata"].get("subject"),
        )
        print("🔹 Snippet:", ch["content"][:200])


def inspect_vectordb_docs():
    from api.configs.config_loader import load_config
    from api.data_pipeline.vectorstores.vector_store_versioned import (
        VersionedVectorStore,
    )

    cfg = load_config()
    vs = VersionedVectorStore(cfg).load_vectorstore(
        persist_dir="outputs/chroma_store/math_grade_9", collection_name="math_grade_9"
    )
    print("🔢 Vectors stored:", vs._collection.count())
