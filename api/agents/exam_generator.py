from pathlib import Path
from typing import Dict, Any, Optional

from langchain_community.vectorstores.chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import PromptTemplate

from api.constants import OPENAI_API_KEY
from api.agents.base_agent import BaseAgent


class ExamGeneratorAgent(BaseAgent):
    def __init__(
        self,
        base_vector_dir: Path,
        model_name: str = "gpt-4",
        with_context: bool = True,
    ):
        self.base_vector_dir = Path(base_vector_dir)
        self.llm = ChatOpenAI(model_name=model_name, api_key=OPENAI_API_KEY)
        self.embedding_model = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
        self.with_context = with_context

        self.prompt_template = PromptTemplate.from_template(
            """
You are an educational assistant generating exams for students.

Generate a {num_questions}-question {exam_type} exam for grade {grade} in the subject of {subject}.
{topic_clause}

{context_clause}

Format the exam clearly, with numbered questions. Do not include answers.
        """
        )

    def retrieve_context(
        self, subject: str, grade: str, topic: Optional[str] = None, k: int = 5
    ) -> str:
        collection = f"{subject}_{grade}".lower().replace(" ", "_")
        vector_path = self.base_vector_dir / collection

        if not vector_path.exists():
            return ""

        vs = Chroma(
            persist_directory=str(vector_path),
            collection_name=collection,
            embedding_function=self.embedding_model,
        )
        retriever = vs.as_retriever(search_kwargs={"k": k})

        query = topic or f"{subject} exam topics for grade {grade}"
        docs = retriever.get_relevant_documents(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        return context

    def run(self, query: Dict[str, Any]) -> str:
        subject = query.get("subject")
        grade = query.get("grade")
        topic = query.get("topic", None)
        num_questions = query.get("num_questions", 10)
        exam_type = query.get("exam_type", "final")

        if not subject or not grade:
            return "❌ 'subject' and 'grade' are required."

        topic_clause = f"Focus on the topic: {topic}." if topic else ""
        context_clause = ""

        if self.with_context:
            context = self.retrieve_context(subject, grade, topic)
            if context:
                context_clause = (
                    f"Use the following context for inspiration:\n\n{context}"
                )
            else:
                context_clause = (
                    "No context available from database. Use general knowledge."
                )

        prompt = self.prompt_template.format(
            num_questions=num_questions,
            exam_type=exam_type,
            grade=grade,
            subject=subject,
            topic_clause=topic_clause,
            context_clause=context_clause,
        )

        response = self.llm.predict(prompt)
        return response.strip()
