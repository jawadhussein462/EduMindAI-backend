import json
from pathlib import Path
from typing import List

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

from langchain.docstore.document import Document
from loguru import logger
from tqdm import tqdm

from api.configs.config_loader import AppConfig


class ComplexAzurePDFParser:
    """
    Parser for PDF documents using Azure Form Recognizer.

    This class recursively loads PDFs from a folder, extracts text,
    tables, and math equations, and attaches detailed metadata
    (grade, subject, exam type, etc.) to each chunk.
    """

    def __init__(self, config: AppConfig):
        """
        Initialize the ComplexAzurePDFParser.

        Args:
            config (AppConfig)
        """
        self.folder_path = Path(config.exams_path)
        self.output_path = Path(config.parsed_data_path)
        self.client = DocumentAnalysisClient(
            endpoint=config.api.azure_formrecognizer_endpoint,
            credential=AzureKeyCredential(config.api.azure_formrecognizer_key),
        )
        logger.info(f"Initialized ComplexAzurePDFParser for folder: {self.folder_path}")

    def _analyze_document(self, file_path: Path):
        """
        Analyze a PDF document using Azure Form Recognizer.

        Args:
            file_path (Path): Path to the PDF file.

        Returns:
            DocumentResult: Result object from Azure Form Recognizer.
        """
        logger.debug(f"Analyzing document: {file_path}")
        with open(file_path, "rb") as f:
            poller = self.client.begin_analyze_document("prebuilt-layout", document=f)
            result = poller.result()
        logger.debug(f"Completed analysis: {file_path}")
        return result

    def _extract_metadata(self, file_path: Path) -> dict:
        """
        Extract metadata like grade, subject, and exam type from file path and name.

        Args:
            file_path (Path): Path to the PDF file.

        Returns:
            dict: Metadata dictionary with keys: source, grade, subject, exam_type, etc.
        """
        relative_path = file_path.relative_to(self.folder_path)
        parts = relative_path.parts[:-1]  # exclude file name
        filename = file_path.stem.lower()

        metadata = {
            "source": str(file_path),
            "grade": None,
            "subject": None,
            "exam_type": None,
            "curriculum": None,
            "language": None,
            "difficulty": None,
        }

        if len(parts) >= 2:
            metadata["grade"], metadata["subject"] = parts[:2]
        elif len(parts) == 1:
            metadata["grade"] = parts[0]

        # Infer exam type from filename
        if any(key in filename for key in ["final", "bac", "baccalaureate"]):
            metadata["exam_type"] = "final"
        elif any(key in filename for key in ["mid", "partial", "term1", "term2"]):
            metadata["exam_type"] = "partial"
        elif "quiz" in filename:
            metadata["exam_type"] = "quiz"
        elif "exercise" in filename:
            metadata["exam_type"] = "exercise"
        elif "mock" in filename:
            metadata["exam_type"] = "mock"

        logger.debug(f"Extracted metadata for {file_path}: {metadata}")
        return metadata

    def _convert_table_to_text(self, table) -> str:
        """
        Convert an Azure Form Recognizer table object to a markdown-style string.

        Args:
            table: Table object from Azure Form Recognizer result.

        Returns:
            str: String representation of the table.
        """
        rows = []
        max_cols = max(cell.column_index + cell.column_span for cell in table.cells)
        grid = [["" for _ in range(max_cols)] for _ in range(table.row_count)]

        for cell in table.cells:
            row, col = cell.row_index, cell.column_index
            grid[row][col] = cell.content.strip()

        table_text = []
        for row in grid:
            table_text.append(" | ".join(cell or " " for cell in row))
        return "\n".join(table_text)

    def _parse_result_to_documents(self, result, file_path: Path) -> List[Document]:
        """
        Parse Azure Form Recognizer result into a list of LangChain Document chunks.

        Args:
            result: Azure Form Recognizer analysis result.
            file_path (Path): Path to the original PDF file.

        Returns:
            List[Document]: List of Document objects with content and metadata.
        """
        docs = []
        base_metadata = self._extract_metadata(file_path)

        for page_num, page in enumerate(result.pages, start=1):
            page_metadata = {**base_metadata, "page": page_num}

            # Extract full text lines
            lines = [line.content for line in page.lines]
            raw_text = "\n".join(lines).strip()
            if raw_text:
                docs.append(
                    Document(
                        page_content=raw_text,
                        metadata={**page_metadata, "type": "text"},
                    )
                )

            # Extract tables
            for table_index, table in enumerate(page.tables):
                table_str = self._convert_table_to_text(table)
                docs.append(
                    Document(
                        page_content=table_str,
                        metadata={
                            **page_metadata,
                            "type": "table",
                            "table_index": table_index,
                        },
                    )
                )

            # Extract likely math/equation lines
            math_lines = [
                line.content
                for line in page.lines
                if any(c in line.content for c in "=^*/√π±∑∫∞≠≈≤≥")
            ]
            if math_lines:
                math_text = "\n".join(math_lines).strip()
                docs.append(
                    Document(
                        page_content=math_text,
                        metadata={**page_metadata, "type": "math_equation"},
                    )
                )

            logger.debug(
                f"Page {page_num} parsed: {len(lines)} lines, {len(page.tables)} tables, "
                f"{'yes' if math_lines else 'no'} math"
            )

        return docs

    def save_documents_to_jsonl(self, documents: List[Document]):
        """
        Save a list of LangChain Document objects to a JSONL file.

        Args:
            documents (List[Document]): List of parsed documents to save.
        """
        try:
            with open(self.output_path, "w", encoding="utf-8") as f:
                for doc in documents:
                    entry = {"content": doc.page_content, "metadata": doc.metadata}
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.success(f"📁 Saved parsed documents to {self.output_path}")
        except Exception as e:
            logger.exception(f"❌ Failed to save documents to {self.output_path}: {e}")

    def parse_all_pdfs(self) -> List[Document]:
        """
        Parse all PDFs in a folder and save results to a JSONL file.

        Returns:
            List[Document]: Parsed document objects.
        """
        all_docs = []
        pdf_files = list(self.folder_path.rglob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files under {self.folder_path}")
        assert 0
        for pdf_file in tqdm(pdf_files, desc="Parsing PDFs"):
            try:
                logger.info(f"Processing: {pdf_file}")
                result = self._analyze_document(pdf_file)
                docs = self._parse_result_to_documents(result, pdf_file)
                all_docs.extend(docs)
                logger.success(f"✅ Parsed: {pdf_file.name} ({len(docs)} chunks)")
            except Exception as e:
                logger.exception(f"❌ Failed to parse {pdf_file.name}: {e}")
        logger.info(f"📄 Total parsed document chunks: {len(all_docs)}")

        # Save to JSONL by default
        self.save_documents_to_jsonl(all_docs)

        return all_docs


if __name__ == "__main__":
    from api.configs.config_loader import load_config

    cfg = load_config()

    azure_parser = ComplexAzurePDFParser(cfg)

    documents = azure_parser.parse_all_pdfs()
    print(f"Total pages parsed: {len(documents)}")
    print(documents[0].page_content[:300])  # Preview first page

    # Preview metadata
    for doc in documents[:3]:
        print(doc.metadata)
