"""
PDFParser using OpenAI GPT-4o vision API for robust PDF extraction.
"""

from openai import OpenAI
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from loguru import logger
from tqdm import tqdm
from api.configs.config_loader import AppConfig


# -----------------------------------------------------------------------------------------------
class SimpleAzurePDFParser:
    """
    Parser for PDF documents using Azure Form Recognizer.

    This class recursively  extracts text content and saves parsed data to .txt files.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.api_key = config.api.openai_api_key
        self.client = OpenAI(api_key=self.api_key)
        self.azure_endpoint = config.api.azure_formrecognizer_endpoint
        self.azure_key = config.api.azure_formrecognizer_key
        self.azure_client = DocumentAnalysisClient(
            self.azure_endpoint, AzureKeyCredential(self.azure_key)
        )

    def _parse(self, pdf_path):
        return self._parse_with_azure(pdf_path)

    def _parse_with_azure(self, pdf_path):
        if not self.azure_client:
            raise RuntimeError("Azure Document Intelligence client not initialized.")
        try:
            with open(pdf_path, "rb") as f:
                poller = self.azure_client.begin_analyze_document(
                    "prebuilt-document", document=f
                )
                result = poller.result()
            all_text = []
            for page in tqdm(result.pages, desc=(f"Parsing Azure pages in {pdf_path}")):
                page_lines = [line.content for line in page.lines]
                all_text.append(" ".join(page_lines))
            return "\n\n".join(all_text)
        except Exception as e:
            logger.error(f"Azure Document Intelligence error: {e}")
            return f"[Azure Document Intelligence error: {e}]"

    def parse_and_save(self, input_path, output_path):
        """
        Parse PDF and save extracted text to output_path.

        Returns:
            None: This function does not return a value;
            it saves the parsed content to the specified output path.
        """
        logger.info(f"Saving parsed text to {output_path}")
        text = self._parse(input_path)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
