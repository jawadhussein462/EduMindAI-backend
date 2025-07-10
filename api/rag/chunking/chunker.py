# chunking/chunker.py
"""
Chunker using LangChain's RecursiveCharacterTextSplitter for advanced chunking.
"""

from langchain_text_splitters import TokenTextSplitter
from loguru import logger
from tqdm import tqdm


class Chunker:
    def __init__(self, chunk_size=1000, overlap=200):
        self.splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap
        )

    def chunk(self, text):
        """
        Split text into chunks using RecursiveCharacterTextSplitter.
        Returns a list of text chunks.
        """
        if not isinstance(text, str):
            raise ValueError("Input text must be a string.")
        return self.splitter.split_text(text)

    def chunk_file(self, input_path, output_path):
        """Read text from input_path, chunk it, and save to output_path."""
        logger.info(f"Reading and chunking file: {input_path}")
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = self.chunk(text)
        logger.info(f"Writing {len(chunks)} chunks to {output_path}")
        with open(output_path, "w", encoding="utf-8") as out:
            for chunk in tqdm(chunks, desc=f'Writing chunks to {output_path}'):
                out.write(chunk + "\n---\n") 