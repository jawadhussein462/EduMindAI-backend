import json
from pathlib import Path
from typing import List, Optional

from langchain.docstore.document import Document
from langchain_community.vectorstores.chroma import Chroma
from langchain_community.embeddings import OpenAIEmbeddings

from api.configs.config_loader import AppConfig


class StandardVectorStore:
    """
    Standard version: Stores all documents in a single Chroma vector DB.
    """

    def __init__(
        self,
        config: AppConfig,
        embedding_model: Optional[OpenAIEmbeddings] = None,
    ):
        self.collection_name = config.exams_path
        self.persist_directory = Path(config.vector_store.persist_directory)
        self.embedding_model = embedding_model or OpenAIEmbeddings(
            api_key=config.api.openai_api_key
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

    def build_vectorstore(self, docs: List[Document]) -> Chroma:
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        vectorstore = Chroma.from_documents(
            documents=docs,
            embedding=self.embedding_model,
            collection_name=self.collection_name,
            persist_directory=str(self.persist_directory),
        )
        vectorstore.persist()
        self.save_metadata(docs)
        return vectorstore

    def save_metadata(self, docs: List[Document]):
        metadata = {
            "collection_name": self.collection_name,
            "embedding_model": "openai/text-embedding-3-large",
            "total_chunks": len(docs),
            "example_metadata": docs[0].metadata if docs else {},
        }
        meta_path = self.persist_directory / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def load_vectorstore(self) -> Chroma:
        return Chroma(
            embedding_function=self.embedding_model,
            collection_name=self.collection_name,
            persist_directory=str(self.persist_directory),
        )
