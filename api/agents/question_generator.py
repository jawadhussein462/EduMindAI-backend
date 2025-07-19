from pathlib import Path
from typing import Dict, Any

from langchain_community.vectorstores.chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import PromptTemplate

from api.agents.base_agent import BaseAgent

from api.constants import OPENAI_API_KEY


class QuestionGeneratorAgent(BaseAgent):
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
You are a helpful assistant that creates exam questions for students.

Create {num_questions} {question_type} questions for grade {grade} in {subject} on the topic of "{topic}".

{context_clause}

Format the output as a clean numbered list.
        """
        )

    def retrieve_context(self, subject: str, grade: str, topic: str, k: int = 5) -> str:
        collection = f"{subject}_{grade}".lower().replace(" ", "_")
        path = self.base_vector_dir / collection

        if not path.exists():
            return ""

        vs = Chroma(
            persist_directory=str(path),
            collection_name=collection,
            embedding_function=self.embedding_model,
        )
        retriever = vs.as_retriever(search_kwargs={"k": k})
        docs = retriever.get_relevant_documents(topic)
        context = "\n\n".join([doc.page_content for doc in docs])
        return context

    def run(self, query: Dict[str, Any]) -> str:
        subject = query.get("subject")
        grade = query.get("grade")
        topic = query.get("topic")
        num_questions = query.get("num_questions", 5)
        question_type = query.get("question_type", "mixed")  # MCQ / short / open / etc.

        if not subject or not grade or not topic:
            return "❌ 'subject', 'grade', and 'topic' are required."

        context_clause = ""
        if self.with_context:
            context = self.retrieve_context(subject, grade, topic)
            if context:
                context_clause = (
                    f"Use this context to help craft the questions:\n\n{context}"
                )
            else:
                context_clause = "No context found. Use general knowledge."

        prompt = self.prompt_template.format(
            num_questions=num_questions,
            question_type=question_type,
            grade=grade,
            subject=subject,
            topic=topic,
            context_clause=context_clause,
        )

        response = self.llm.predict(prompt)
        return response.strip()
