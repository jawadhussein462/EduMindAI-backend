import json
from typing import List
from pathlib import Path

from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from api.configs.config_loader import AppConfig


class SmartChunker:
    """
    Smart chunker for parsed documents. Applies hybrid chunking strategy:
    - Tables and math blocks are kept intact.
    - Text blocks are recursively split for optimal embedding.
    - Nearby tables/math are merged with text chunks when useful.
    """

    def __init__(self, config: AppConfig):
        """
        Args:
            config (AppConfig)
        """

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunking.chunk_size,
            chunk_overlap=config.chunking.overlap,
            separators=["\n\n", "\n", ".", " ", ""],
        )

    def _load_from_jsonl(self, path: Path) -> List[Document]:
        """
        Load parsed documents from a JSONL file.

        Args:
            path (Path): Path to the JSONL file.

        Returns:
            List[Document]: List of LangChain Document objects.
        """
        documents = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                documents.append(
                    Document(page_content=data["content"], metadata=data["metadata"])
                )
        return documents

    def _save_to_jsonl(self, documents: List[Document], output_path: Path):
        """
        Save chunked documents to JSONL.

        Args:
            documents (List[Document]): List of Document chunks.
            output_path (Path): Destination path for JSONL.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for doc in documents:
                entry = {"content": doc.page_content, "metadata": doc.metadata}
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _chunk_documents(self, docs: List[Document]) -> List[Document]:
        """
        Chunk documents using hybrid strategy.

        Args:
            docs (List[Document]): Raw parsed documents.

        Returns:
            List[Document]: Chunked document list ready for embedding.
        """
        chunked_docs = []

        for doc in docs:
            doc_type = doc.metadata.get("type", "text")

            if doc_type == "text":
                splits = self.text_splitter.split_text(doc.page_content)
                for i, chunk in enumerate(splits):
                    new_metadata = {
                        **doc.metadata,
                        "chunk_index": i,
                        "chunk_type": "text",
                    }
                    chunked_docs.append(
                        Document(page_content=chunk, metadata=new_metadata)
                    )

            elif doc_type in ["table", "math_equation"]:
                new_metadata = {**doc.metadata, "chunk_type": doc_type}
                chunked_docs.append(
                    Document(page_content=doc.page_content, metadata=new_metadata)
                )

        return chunked_docs

    def process(self, input_path: Path, output_path: Path) -> List[Document]:
        """
        Full process: load parsed JSONL, chunk documents, and save to output.

        Args:
            input_path (Path): Path to parsed JSONL input.
            output_path (Path): Path to write chunked JSONL output.

        Returns:
            List[Document]: Chunked documents.
        """
        parsed_docs = self._load_from_jsonl(input_path)
        chunked_docs = self._chunk_documents(parsed_docs)
        self._save_to_jsonl(chunked_docs, output_path)
        return chunked_docs


if __name__ == "__main__":
    from api.configs.config_loader import load_config

    cfg = load_config()

    chunker = SmartChunker(cfg)

    input_path = Path("outputs/parsed_docs.jsonl")
    output_path = Path("outputs/chunked_docs.jsonl")

    chunks = chunker.process(input_path, output_path)
    print(f"Saved {len(chunks)} chunks to {output_path}")
