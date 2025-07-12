import os
import asyncio
from typing import List

from api.rag.data_loader.loader import DataLoader
from api.rag.parsing.pdf_parser import PDFParser
from api.rag.chunking.chunker import Chunker
from api.rag.vector_store import VectorStore
from api.config_loader import AppConfig
from loguru import logger
from tqdm import tqdm


class ExamDataPipeline:
    """Three‑stage pipeline (parse → chunk → embed) for exam documents.

    The *public* API is **synchronous** – i.e. :pyfunc:`process_exam_files` –
    because many callers prefer a blocking function.  Internally we still use
    asyncio for the embedding stage, but we hide that detail from the user.

    If you *already* have an event‑loop running (e.g. in Jupyter) and call the
    sync wrapper, we detect the situation and run the coroutine as a task so
    that you don’t hit the dreaded «asyncio.run() cannot be called from a
    running event loop» error.  In that case the method returns the created
    :class:`asyncio.Task` so you can await it if you want.
    """

    # ------------------------------------------------------------------ #
    # INITIALISATION                                                     #
    # ------------------------------------------------------------------ #

    def __init__(self, config: AppConfig, max_concurrency: int = 10):
        self.config = config
        self.exams_path = config.exams_path or os.path.join(
            os.path.dirname(__file__), "../exams_random"
        )

        self.data_loader = DataLoader()
        self.pdf_parser = PDFParser(config)
        self.chunker = Chunker(config)
        self.vector_store = VectorStore(config)
        self._semaphore = asyncio.Semaphore(max_concurrency)

    # ------------------------------------------------------------------ #
    # PUBLIC API (synchronous)                                           #
    # ------------------------------------------------------------------ #

    def process_exam_files(self):
        """Run the full pipeline *synchronously*.

        Internally delegates to :pyfunc:`_process_exam_files_async`.
        If we are *not* already in an event loop we simply call
        :pyfunc:`asyncio.run`.  If we *are* (common in notebooks) we fall back
        to creating an :class:`asyncio.Task` and **return** it so that the
        caller can `await` the task if they choose.
        """
        try:
            return asyncio.run(self._process_exam_files_async())
        except RuntimeError as exc:
            if "asyncio.run() cannot be called from a running event loop" not in str(
                exc
            ):
                raise  # different problem → re‑raise

            logger.warning(
                "Detected an active event‑loop – running pipeline as a task instead…"
            )
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._process_exam_files_async())
            return task  # caller may ignore or `await` the task

    # ------------------------------------------------------------------ #
    # INTERNAL ASYNC IMPLEMENTATION                                      #
    # ------------------------------------------------------------------ #

    async def _process_exam_files_async(self) -> None:
        base_dir = os.path.dirname(__file__)
        parsing_dir = os.path.join(base_dir, "parsing", "parsed_data")
        chunking_dir = os.path.join(base_dir, "chunking", "chunked_data")
        os.makedirs(parsing_dir, exist_ok=True)
        os.makedirs(chunking_dir, exist_ok=True)

        # ── Stage 1 – PARSING (now async) ──────────────────────────────
        await self._parse_all_exam_files_async(parsing_dir)

        # ── Stage 2 – CHUNKING (still sync; usually CPU‑light) ─────────
        self._chunk_all_parsed_files(parsing_dir, chunking_dir)

        # ── Stage 3 – EMBEDDING (async, unchanged) ────────────────────
        await self._embed_all_chunked_files(chunking_dir)

    # ------------------------------------------------------------------ #
    # STAGE 1 – PARSING (ASYNC)                                          #
    # ------------------------------------------------------------------ #

    async def _parse_all_exam_files_async(self, parsing_dir: str) -> None:
        """Parse all exam files concurrently using asyncio threads."""

        logger.info("Step 1/3 – Parsing exam files…")
        tasks: List[asyncio.Task] = []

        for root, _, files in os.walk(self.exams_path):
            for fname in files:
                fpath = os.path.join(root, fname)
                parsed_fname = f"{fname}.parsed.txt"
                parsed_path = os.path.join(parsing_dir, parsed_fname)

                if not self.config.force_reload:
                    if os.path.exists(parsed_path):
                        logger.debug(f"✓ Already parsed  {parsed_path}")
                        continue

                # Use to_thread so the blocking I/O does not block the loop.
                async def _worker(name: str, src: str, dst: str):
                    async with self._semaphore:  # limit global concurrency
                        await asyncio.to_thread(self._parse_single_file, name, src, dst)

                tasks.append(asyncio.create_task(_worker(fname, fpath, parsed_path)))

        if tasks:
            for f in tqdm(asyncio.as_completed(tasks), total=len(tasks)):
                await f
        logger.info("✅  Parsing complete!")

    def _parse_single_file(self, fname: str, fpath: str, parsed_path: str) -> None:
        """Blocking helper – executed in a thread pool."""
        if fname.lower().endswith(".txt"):
            logger.info(f"Parsing TXT  → {fpath}")
            self.data_loader.load_and_save(fpath, parsed_path)
        elif fname.lower().endswith(".pdf"):
            logger.info(f"Parsing PDF  → {fpath}")
            try:
                self.pdf_parser.parse_and_save(fpath, parsed_path)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"⚠️  Failed to parse PDF {fpath}: {exc}")
        else:
            logger.debug(f"Skipping unsupported file: {fpath}")

    # ------------------------------------------------------------------ #
    # STAGE 2 – CHUNKING                                                 #
    # ------------------------------------------------------------------ #

    def _chunk_all_parsed_files(self, parsing_dir: str, chunking_dir: str) -> None:
        logger.info("Step 2/3 – Chunking parsed files…")
        for parsed_fname in os.listdir(parsing_dir):
            if not parsed_fname.endswith(".parsed.txt"):
                continue

            parsed_path = os.path.join(parsing_dir, parsed_fname)
            chunked_fname = parsed_fname.replace(".parsed.txt", ".chunked.txt")
            chunked_path = os.path.join(chunking_dir, chunked_fname)

            if not self.config.force_reload:
                if os.path.exists(chunked_path):
                    logger.debug(f"✓ Already chunked {chunked_path}")
                    continue

            logger.info(f"Chunking     → {parsed_fname}")
            self.chunker.chunk_file(parsed_path, chunked_path)

    # ------------------------------------------------------------------ #
    # STAGE 3 – EMBEDDING                                                #
    # ------------------------------------------------------------------ #

    async def _embed_all_chunked_files(self, chunking_dir: str) -> None:
        logger.info("Step 3/3 – Embedding chunks into the vector store…")
        tasks: List[asyncio.Task] = []

        for chunked_fname in os.listdir(chunking_dir):
            if not chunked_fname.endswith(".chunked.txt"):
                continue

            chunked_path = os.path.join(chunking_dir, chunked_fname)
            embedded_marker = f"{chunked_path}.embedded"

            if not self.config.force_reload:
                if os.path.exists(embedded_marker):
                    logger.debug(f"✓ Already embedded {chunked_path}")
                    continue

            docs = self._collect_docs_from_chunked(chunked_path)
            if not docs:
                logger.warning(f"No chunks found in {chunked_fname}")
                continue

            logger.info(f"Embedding {len(docs):>4} chunks from {chunked_fname}")

            async def embed_and_mark(docs_snapshot: List[str]):
                await self.vector_store.add_documents(docs_snapshot)

            with open(embedded_marker, "w", encoding="utf-8") as fp:
                fp.write("embedded")

            tasks.append(asyncio.create_task(embed_and_mark(docs)))

        if tasks:
            await asyncio.gather(*tasks)
        logger.info("✅  Embedding complete!")

    # ------------------------------------------------------------------ #
    # UTILITIES                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _collect_docs_from_chunked(chunked_path: str) -> List[str]:
        """Return a list of text chunks separated by a line containing only '---'."""
        docs: List[str] = []
        with open(chunked_path, "r", encoding="utf-8") as cf:
            chunk = ""
            for line in cf:
                if line.strip() == "---":  # newline delimiter
                    if chunk.strip():
                        docs.append(chunk.strip())
                    chunk = ""
                else:
                    chunk += line
            if chunk.strip():  # final chunk
                docs.append(chunk.strip())
        return ["\n".join(docs)]


# ---------------------------------------------------------------------- #
# CONVENIENCE WRAPPER FOR SCRIPTS                                        #
# ---------------------------------------------------------------------- #


def run_pipeline(config: AppConfig):
    """Blocking convenience wrapper for CLI usage."""
    ExamDataPipeline(config).process_exam_files()


if __name__ == "__main__":
    from api.config_loader import load_config

    cfg = load_config()
    run_pipeline(cfg)
