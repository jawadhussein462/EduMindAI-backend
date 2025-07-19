from __future__ import annotations

import json
from typing import List, TypedDict

from loguru import logger
from pydantic import BaseModel, ValidationError
from tqdm import tqdm

from langchain_community.vectorstores.chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from api.configs.config_loader import AppConfig
import asyncio


class ExamMeta(BaseModel):
    branch: List[str]
    subject: str
    # add more fields if you need them
    title: str  # short human-readable title / summary

    def to_embedding_text(self) -> str:
        """Text that will be embedded."""
        branch_text = " | ".join(self.branch)
        return f"{branch_text} | {self.subject} | {self.title}"


class MetaDict(TypedDict):
    branch: List[str]
    subject: str
    full_chunk: str


class VectorStore:
    # Allowed branches, lower‑case for easy comparison inside the model
    ALLOWED_BRANCHES = [
        "general science",
        "life science",
        "arts and humanities",
        "social and economic sciences",
        "middle school certificate",
    ]

    JSON_PROMPT = (
        "You are given a chunk of text that belongs to an exam document.\n"
        "Extract the following JSON ONLY (no extra keys, no markdown). "
        "⚠️  The `branch` field MUST be a list whose elements are chosen ONLY from the "
        "following English terms exactly as written (case‑insensitive): "
        '["general science", "life science", "arts and humanities", '
        '"social and economic sciences" ""middle school certificate"]. If more than one branch applies include all '
        "relevant entries; otherwise use an empty list [].\n"
        "{{\n"
        '  "branch": ["<one or more from the allowed list>"],\n'
        '  "subject": "<course name>",\n'
        '  "title":   "<a 1‑sentence descriptive title in English>"\n'
        "}}\n"
        "Chunk:\n{chunk}\n"
        "JSON:"
    )

    def __init__(self, config: AppConfig):
        self.config = config
        persist_directory = (
            config.vector_store.get("persist_directory", ".chroma_db")
            if config.vector_store
            else ".chroma_db"
        )

        self.embeddings = OpenAIEmbeddings(api_key=config.api.openai_api_key)
        self.llm = ChatOpenAI(
            model=config.llm.model,
            # temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
            top_p=config.llm.top_p,
            frequency_penalty=config.llm.frequency_penalty,
            presence_penalty=config.llm.presence_penalty,
            api_key=config.api.openai_api_key,
        )
        self.db = Chroma(
            persist_directory=persist_directory,
            embedding_function=self.embeddings,
        )

    # -------------------------- Metadata extraction ----------------------- #
    async def _extract_meta(self, chunk: str) -> ExamMeta | None:
        prompt = self.JSON_PROMPT.format(chunk=chunk[:4000])  # protect token budget
        raw = await self.llm.agenerate([[HumanMessage(content=prompt)]])
        txt = raw.generations[0][0].message.content.strip()
        return self._safe_parse(txt)

    @classmethod
    def _normalise_branches(cls, branches: List[str]) -> List[str]:
        # Lower‑case, strip, and keep only allowed branches
        cleaned = [b.lower().strip() for b in branches]
        return [b for b in cleaned if b in cls.ALLOWED_BRANCHES]

    @classmethod
    def _safe_parse(cls, txt: str) -> ExamMeta | None:
        try:
            data = json.loads(txt)

            # Ensure branch is always a list and validate choices
            raw_branches = data.get("branch", [])
            if isinstance(raw_branches, str):
                raw_branches = [raw_branches]

            data["branch"] = cls._normalise_branches(raw_branches)
            return ExamMeta(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Metadata parse failed: {e}\nRaw LLM output: {txt}")
            return None

    # ------------------------------ Indexing ------------------------------ #
    async def add_documents(self, chunks: List[str]) -> None:
        docs: List[Document] = []
        for chunk in tqdm(chunks, desc="Extracting metadata"):
            meta = await self._extract_meta(chunk)
            if not meta:
                # fallback – store without filtering fields
                meta = ExamMeta(
                    branch=["general science"], subject="UNKNOWN", title="Untitled"
                )

            docs.append(
                Document(
                    page_content=meta.to_embedding_text(),
                    metadata={  # type: ignore[arg-type]
                        "branch": "|".join(
                            meta.branch
                        ),  # Store as pipe-separated string
                        "subject": meta.subject,
                        "full_chunk": chunk,
                    },
                )
            )

        logger.info(f"Adding {len(docs)} documents to Chroma")
        self.db.add_documents(docs)
        self.db.persist()

    # ----------------------------- Retrieval ------------------------------ #
    async def _prepare_query(self, query: str) -> tuple[str, dict]:
        """
        Parse the user query the same way we parsed the chunks.
        Returns (embedding_text, chroma_filter)
        """
        meta = await self._extract_meta(query) or ExamMeta(
            branch=["general science"], subject="UNKNOWN", title=query[:60]
        )
        # Chroma filter: match any overlap between stored branches and query branches
        # Now that branch is a pipe-separated string, use $contains for filtering
        filter_: dict = (
            {"branch": {"$in": meta.branch[0].split("|")}} if meta.branch else {}
        )
        return meta.to_embedding_text(), filter_

    async def search(self, query: str, k: int = 5):
        embedding_text, filter_ = await self._prepare_query(query)
        # Chroma will first apply the metadata filter, then similarity search
        return await asyncio.to_thread(
            self.db.similarity_search, embedding_text, k, filter_
        )
