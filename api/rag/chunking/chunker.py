# chunking/chunker.py
"""
Chunker using LangChain's TextSplitter for advanced chunking.
"""

import tiktoken
from api.config_loader import AppConfig
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    CharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)
import re
from loguru import logger
from tqdm import tqdm

from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings


class Chunker:
    def __init__(self, config: AppConfig):
        """Initialize the Chunker with specified chunk size, overlap, and chunking method."""
        self.config = config
        self.splitter = self._initialize_splitter(
            config.chunking.chunk_size,
            config.chunking.overlap,
            config.chunking.chunk_type,
        )
        # self.splitter = TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)

    def _initialize_splitter(self, chunk_size, overlap, chunk_type):
        """
        Initialize the appropriate text splitter based on chunk_type.

        Returns:
            TextSplitter: Configured LangChain text splitter instance.

        Raises:
            ValueError: If chunk_type is not supported.
        """
        if chunk_type == "RecursiveCharacterTextSplitter":
            return RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                separators=["\n\n", "\n", " ", ""],
                length_function=lambda x: len(
                    tiktoken.encoding_for_model("gpt-4").encode(x)
                ),
            )
        elif chunk_type == "TokenTextSplitter":
            return TokenTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                encoding_name="cl100k_base",  # Matches GPT models
            )
        elif chunk_type == "CharacterTextSplitter":
            return CharacterTextSplitter(
                chunk_size=chunk_size, chunk_overlap=overlap, separator="\n"
            )
        elif chunk_type == "MarkdownHeaderTextSplitter":
            return MarkdownHeaderTextSplitter(
                headers_to_split_on=[
                    ("#", "Header 1"),
                    ("##", "Header 2"),
                    ("###", "Header 3"),
                ],
                strip_headers=False,
            )
        elif chunk_type == "SemanticChunker":
            embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            return SemanticChunker(
                embeddings,
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=95.0,
            )
        else:
            raise ValueError(
                f"Unsupported chunk_type: {chunk_type}. Supported types are: "
                "RecursiveCharacterTextSplitter, TokenTextSplitter, CharacterTextSplitter, "
                "MarkdownHeaderTextSplitter, SemanticChunker"
            )

    @staticmethod
    def convert_to_markdown(text: str):
        """Convert plain text from _parse_with_azure to Markdown format."""
        try:
            if text.startswith("[Azure Document Intelligence error"):
                return text  # Propagate error from _parse_with_azure

            # Split text into pages
            pages = text.split("\n\n")
            all_text = []

            # Process each page
            for page_idx, page_text in enumerate(pages):
                markdown_text = f"# Page {page_idx + 1}\n"

                # Heuristic conversion without Azure metadata
                lines = page_text.split("\n")
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    # Infer headers: short lines (<50 chars) or all-caps
                    if len(line) < 50 or line.isupper():
                        markdown_text += f"## {line}\n"
                    # Detect potential tables (e.g., lines with consistent delimiters like |, tabs, or spaces)
                    elif re.match(r"(\S+\s+\S+\s+\S+)+", line):
                        # Simplified table detection: assume space-separated values
                        cells = [cell.strip() for cell in line.split()]
                        if len(cells) >= 2:  # Minimum for a table
                            markdown_text += "## Table\n"
                            markdown_text += "| " + " | ".join(cells) + " |\n"
                            markdown_text += (
                                "| " + " | ".join(["---"] * len(cells)) + " |\n"
                            )
                            markdown_text += "\n"
                    # Detect equations (e.g., LaTeX-like patterns)
                    elif re.search(r"\\\[|\\\(|\\\{|\\\w+", line):
                        markdown_text += f"```latex\n{line}\n```\n"
                    else:
                        markdown_text += f"{line}\n"
                markdown_text += "\n"

                all_text.append(markdown_text.strip())

            return "\n\n".join(all_text)

        except Exception as e:
            logger.error(f"Markdown conversion error: {e}")
            return f"[Markdown conversion error: {e}]"

    def chunk(self, text):
        """
        Split text into chunks.
        Returns a list of text chunks.
        """
        if not isinstance(text, str):
            raise ValueError("Input text must be a string.")

        if self.config.chunking.chunk_type == "MarkdownHeaderTextSplitter":
            text = self.convert_to_markdown(text)
            markdown_chunks = self.splitter.split_text(text)

            # Sub-split large chunks to fit token limits
            recursive_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunking.chunk_size,
                chunk_overlap=self.config.chunking.overlap,
                separators=["\n\n", "\n", " ", ""],
                length_function=lambda x: len(
                    tiktoken.encoding_for_model("gpt-4").encode(x)
                ),
            )
            final_chunks = []
            for chunk in markdown_chunks:
                # Include metadata (headers) in the chunk content
                chunk_text = ""
                if chunk.metadata:
                    for header_level, header_text in chunk.metadata.items():
                        chunk_text += f"{header_level} {header_text}\n"
                chunk_text += chunk.page_content
                # Sub-split the chunk
                sub_chunks = recursive_splitter.split_text(chunk_text)
                final_chunks.extend(sub_chunks)

            return final_chunks

        return self.splitter.split_text(text)

    def chunk_file(self, input_path, output_path):
        """Read text from input_path, chunk it, and save to output_path."""
        logger.info(f"Reading and chunking file: {input_path}")
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = self.chunk(text)
        logger.info(f"Writing {len(chunks)} chunks to {output_path}")
        with open(output_path, "w", encoding="utf-8") as out:
            for chunk in tqdm(chunks, desc=f"Writing chunks to {output_path}"):
                out.write(chunk + "\n---\n")
