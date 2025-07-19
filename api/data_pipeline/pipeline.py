from pathlib import Path
from loguru import logger

from api.data_pipeline.chunkers.smart_chunker import SmartChunker
from api.data_pipeline.parsers.enhanced_parser import ComplexAzurePDFParser
from api.data_pipeline.vectorstores.vector_store_standard import StandardVectorStore


def run_pipeline(
    input_folder: Path,
    output_dir: Path = Path("outputs"),
    embedding_mode: str = "standard",  # or "versioned"
):
    """
    Runs the full pipeline: parsing → chunking → vectorstore.

    Args:
        input_folder (Path): Folder containing PDF documents.
        output_dir (Path): Output folder for JSONL files and Chroma DB.
        embedding_mode (str): "standard" or "versioned"
    """
    from api.configs.config_loader import load_config

    cfg = load_config()

    logger.info("🚀 Starting exam document pipeline")

    # Paths
    parsed_path = output_dir / "parsed_docs.jsonl"
    chunked_path = output_dir / "chunked_docs.jsonl"
    chroma_base_dir = output_dir / "chroma_store"
    assert 0
    # Step 1: Parse PDFs
    logger.info("📄 Step 1: Parsing PDFs")
    parser = ComplexAzurePDFParser(cfg)
    parser.parse_all_pdfs(input_folder, parsed_path)

    # Step 2: Chunking
    logger.info("🔪 Step 2: Chunking documents")
    chunker = SmartChunker(cfg)
    chunker.process(parsed_path, chunked_path)

    # Step 3: Build Vector Store
    logger.info("🧠 Step 3: Embedding and storing vectors")

    if embedding_mode == "standard":
        vs_builder = StandardVectorStore(cfg)
        docs = vs_builder.load_documents_from_jsonl(chunked_path)
        vs_builder.build_vectorstore(docs)

    elif embedding_mode == "versioned":
        from api.data_pipeline.vectorstores.vector_store_versioned import (
            VersionedVectorStore,
        )

        vs_builder = VersionedVectorStore(cfg)
        vs_builder.build_all(input_jsonl=chunked_path, base_dir=chroma_base_dir)

    else:
        logger.error(f"❌ Invalid embedding_mode: {embedding_mode}")
        return

    logger.success("✅ Full pipeline completed successfully!")


if __name__ == "__main__":
    run_pipeline(input_folder=Path("exams_random"), embedding_mode="versioned")
