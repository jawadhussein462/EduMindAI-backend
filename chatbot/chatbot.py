from typing import List, Dict, Optional
import json
import asyncio  # Ensure this is at the top of your file if not already

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage, HumanMessage, BaseMessage
)
from chatbot.prompts import (
    system_prompt,
    resume_prompt,
    filter_related_questions_prompt,
    fill_exam_exercise_prompt,
    compile_exam_document_prompt,
    parse_exam_exercises_prompt,
    clarification_prompt,
)
from chatbot.rag.vector_store import (
    VectorStore
)
from config_loader import AppConfig
from chatbot.rag.exam_data_pipeline import ExamDataPipeline
from loguru import logger
from pydantic import BaseModel


class ExerciseModel(BaseModel):
    """Schema for a single exercise in the exam."""
    topic: str
    grade: str
    description: str
    general_question: str
    subquestions: List[str]


class ExamModel(BaseModel):
    """Top-level container: a mapping of numbered exercises."""
    exercises: Dict[str, ExerciseModel]
    

class ExamQuestionAgent:
    """An intelligent agent for generating exam questions in a single call."""

    def __init__(self, config: AppConfig, data_pipeline: Optional[ExamDataPipeline] = None):
        # Configuration ----------------------------------------------------
        self.config = config
        self.chat_config = config.chat
        self.llm_config = config.llm

        # LLM client -------------------------------------------------------
        self.llm = ChatOpenAI(
            model=self.llm_config.model,
            temperature=self.llm_config.temperature,
            max_tokens=self.llm_config.max_tokens,
            top_p=self.llm_config.top_p,
            frequency_penalty=self.llm_config.frequency_penalty,
            presence_penalty=self.llm_config.presence_penalty,
            api_key=config.api.openai_api_key,
        )

        # Vector store for retrieval --------------------------------------
        self.vector_store = VectorStore(config)

        # Message history (system prompt + conversation turns) -------------
        self.message_history: List[BaseMessage] = [
            SystemMessage(content=system_prompt)
        ]

        # Exam data pipeline ----------------------------------------------
        self.data_pipeline = data_pipeline or ExamDataPipeline(config)
        logger.info(
            "Processing and indexing exam files on agent initialisation ..."
        )
        self.data_pipeline.process_exam_files()

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------
    def _update_history(self, message: BaseMessage) -> None:
        """Append *message* and trim history to the configured length."""
        self.message_history.append(message)
        max_history = self.chat_config.history_length
        # Keep the system message plus the last *max_history* turns
        if len(self.message_history) > max_history + 1:
            self.message_history = [
                self.message_history[0],
                *self.message_history[-max_history:]
            ]

    async def _get_relevant_context(self, query: str, k: int = 5) -> str:
        """Return *k* most similar document chunks as a single context string."""
        relevant_docs = await self.vector_store.search(
            query, k=k
        )
        if not relevant_docs:
            return ""

        context_parts: list[str] = []
        for i, chunk in enumerate(relevant_docs):
            subject = chunk.metadata.get("subject", "Unknown")
            doc = chunk.metadata.get("full_chunk", "Unknown")
            context_parts.append(
                f"CHUNK {i + 1} (Subject: {subject}):\n"
                f"--------------------------------------------------------\n\n"
                f"{doc}"
                f"--------------------------------------------------------\n\n"
            )
        return "\n\n".join(context_parts)

    async def _generate_resume_question(self) -> str:
        """Craft a concise follow‑up question that naturally continues the session."""
        # Exclude the system prompt and take the last 3 turns
        recent_messages: list[BaseMessage] = self.message_history[1:][-3:]
        if not recent_messages:
            return ""

        context_summary = "\n\n".join(
            f"{m.type}: {m.content}" for m in recent_messages
        )
        resume_prompt_str = resume_prompt.format(context_summary=context_summary)
        response = await self.llm.agenerate(
            [[HumanMessage(content=resume_prompt_str)]]
        )
        return response.generations[0][0].message.content.strip()

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    async def send_message(self, message: str) -> str:
        """Processes user request, generates structured exam content as formatted text."""
        logger.info(
            "[ExamAgent] Retrieving relevant context for user message..."
        )
        context = await self._get_relevant_context(message)

        logger.info(
            "[ExamAgent] Parsing exam structure into exercises"
        )
        exercises = await self._parse_exam_exercises(message, context)

        # Prepare tasks for all exercises
        tasks = [
            self._fill_exam_exercise(exercise, context)
            for key, exercise in exercises.exercises.items()
        ]
        keys = list(exercises.exercises.keys())

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)

        # Map results back to their keys
        questions = dict(zip(keys, results))

        logger.info(
            "[ExamAgent] Compiling structured exam document"
        )
        exam_doc = await self._compile_exam_document(
            context, message, questions
        )
        logger.info(
            "[ExamAgent] Exam generation complete."
        )
        return exam_doc

    async def _filter_to_only_related_questions(self, exercise: ExerciseModel, context: str) -> str:
        """Generate a formatted exam exercise (text, not JSON) using the LLM."""
        # Use model_dump() to get a dict, then remove 'subquestions'
        exercise_dict = exercise.model_dump()
        exercise_dict.pop('description', None)
        exercise_dict.pop('general_question', None)
        exercise_dict.pop('subquestions', None)
        exercise_json = json.dumps(exercise_dict)

        prompt = filter_related_questions_prompt.format(
            exercise_json=exercise_json,
            context=context
        )

        response = await self.llm.agenerate([[HumanMessage(content=prompt)]])
        content = response.generations[0][0].message.content.strip()
        logger.info(
            f"[ExamAgent] Filtered exercise content: {content}"
        )
        return content
        
    async def _fill_exam_exercise(self, exercise: ExerciseModel, context: str) -> str:
        """Generate a formatted exam exercise (text, not JSON) using the LLM."""
        # Use model_dump() to get a dict, then remove 'subquestions'
        exercise_dict = exercise.model_dump()
        exercise_dict.pop('general_question', None)
        exercise_dict.pop('subquestions', None)
        exercise_json = json.dumps(exercise_dict)
        
        context = await self._filter_to_only_related_questions(exercise, context)

        prompt = fill_exam_exercise_prompt.format(
            exercise_json=exercise_json,
            context=context
        )

        response = await self.llm.agenerate(
            [[HumanMessage(content=prompt)]]
        )
        content = response.generations[0][0].message.content.strip()
        return content

    async def _compile_exam_document(
            self,
            context: str,
            user_request: str,
            questions: Dict[str, str]
    ) -> str:
        """Format the generated questions into a structured exam document string."""
        doc_lines = []
        for idx, (key, qtext) in enumerate(questions.items(), 1):
            doc_lines.append(f"Exercise {idx}\n{qtext}\n")
        
        exam = "\n".join(doc_lines)
        prompt = compile_exam_document_prompt.format(exam=exam)
        response = await self.llm.agenerate([[HumanMessage(content=prompt)]])
        content = response.generations[0][0].message.content.strip()
        logger.info(f"[ExamAgent] Compiled exam document content: {content}")

        return content

    async def _parse_exam_exercises(self, message: str, context: str) -> ExamModel:
        """Request and validate structured exam plan using Pydantic parsing only, via output_schema."""

        prompt = parse_exam_exercises_prompt.format(
            context=context,
            message=message
        )

        response = await self.llm.agenerate([[HumanMessage(content=prompt)]])
        content = response.generations[0][0].message.content.strip()
        logger.info(f"[ExamAgent] Received exam exercises content: {content}")

        # Remove markdown code fences if present
        if content.startswith('```'):
            # Remove the first line (``` or ```json)
            lines = content.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            # Remove the last line if it is a closing code fence
            if lines and lines[-1].strip().startswith('```'):
                lines = lines[:-1]
            content = '\n'.join(lines).strip()

        # Parse the JSON string to a Python dict
        try:
            exercises_dict = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}\nContent received:\n{content}")
            raise

        # Validate and return as ExamModel
        return ExamModel.model_validate(exercises_dict)

    async def get_relevant_context(self, message: str) -> str:
        """Async wrapper for :py:meth:`_get_relevant_context`."""
        return await self._get_relevant_context(message)

    async def ask_for_clarification(self, message: str) -> dict:
        """Use the LLM to determine if clarification is needed and generate a follow-up question if so."""
        # Prompt the LLM to check for missing info and generate a clarification question if needed
        prompt = clarification_prompt.format(message=message)
        response = await self.llm.agenerate([[HumanMessage(content=prompt)]])
        content = response.generations[0][0].message.content.strip()
        if content.strip().upper() == 'CLEAR':
            return {"clarification_needed": False, "clarification": ""}
        else:
            return {"clarification_needed": True, "clarification": content}
