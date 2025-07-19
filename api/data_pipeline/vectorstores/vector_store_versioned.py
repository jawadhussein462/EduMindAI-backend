import json
from pathlib import Path
from typing import List, Optional, Dict

from langchain.docstore.document import Document
from langchain_community.vectorstores.chroma import Chroma
from langchain_community.embeddings import OpenAIEmbeddings

from api.configs.config_loader import AppConfig


class VersionedVectorStore:
    """
    Versioned vector store: builds one Chroma DB per (subject, grade) group.
    """

    def __init__(
        self, config: AppConfig, embedding_model: Optional[OpenAIEmbeddings] = None
    ):
        self.embedding_model = embedding_model or OpenAIEmbeddings(
            api_key=config.api.openai_api_key,
        )

    def load_documents_from_jsonl(self, jsonl_path: Path) -> List[Document]:
        docs = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                docs.append(
                    Document(page_content=data["content"], metadata=data["metadata"])
                )
        return docs

    def group_documents_by_subject_grade(
        self, docs: List[Document]
    ) -> Dict[str, List[Document]]:
        groups = {}
        for doc in docs:
            subject = doc.metadata.get("subject", "unknown")
            grade = doc.metadata.get("grade", "unknown")
            key = f"{subject}_{grade}".lower().replace(" ", "_")
            groups.setdefault(key, []).append(doc)
        return groups

    def build_vectorstore(
        self, docs: List[Document], persist_dir: Path, collection_name: str
    ) -> Chroma:
        persist_dir.mkdir(parents=True, exist_ok=True)
        vectorstore = Chroma.from_documents(
            documents=docs,
            embedding=self.embedding_model,
            collection_name=collection_name,
            persist_directory=str(persist_dir),
        )
        vectorstore.persist()
        self.save_metadata(persist_dir, docs, collection_name)
        return vectorstore

    def save_metadata(
        self, persist_dir: Path, docs: List[Document], collection_name: str
    ):
        metadata = {
            "collection_name": collection_name,
            "embedding_model": "openai/text-embedding-3-large",
            "total_chunks": len(docs),
            "example_metadata": docs[0].metadata if docs else {},
        }
        meta_path = persist_dir / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def build_all(self, input_jsonl: Path, base_dir: Path = Path("chroma_store")):
        all_docs = self.load_documents_from_jsonl(input_jsonl)
        grouped = self.group_documents_by_subject_grade(all_docs)

        for key, group_docs in grouped.items():
            persist_path = base_dir / key
            print(f"📦 Building vector store for {key} → {persist_path}")
            self.build_vectorstore(
                docs=group_docs, persist_dir=persist_path, collection_name=key
            )

    def load_vectorstore(self, persist_dir: Path, collection_name: str) -> Chroma:
        return Chroma(
            embedding_function=self.embedding_model,
            collection_name=collection_name,
            persist_directory=str(persist_dir),
        )
