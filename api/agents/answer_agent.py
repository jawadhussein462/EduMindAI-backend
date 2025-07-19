from pathlib import Path
from typing import Dict, Any

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores.chroma import Chroma

from api.constants import OPENAI_API_KEY
from api.agents.base_agent import BaseAgent


class AnswerAgent(BaseAgent):
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
You are a helpful tutor AI that explains answers to exam questions.

Answer the following question(s) clearly and completely. If multiple, label them.

{context_clause}

Questions:
{question}

Answers:
        """
        )

    def retrieve_context(
        self, subject: str, grade: str, question: str, k: int = 4
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
        docs = retriever.get_relevant_documents(question)
        context = "\n\n".join([doc.page_content for doc in docs])
        return context

    def run(self, query: Dict[str, Any]) -> str:
        subject = query.get("subject")
        grade = query.get("grade")
        question = query.get("question")

        if not subject or not grade or not question:
            return "❌ 'subject', 'grade', and 'question' are required."

        context_clause = ""
        if self.with_context:
            context = self.retrieve_context(subject, grade, question)
            if context:
                context_clause = f"Use this context to help answer:\n\n{context}"
            else:
                context_clause = "No context found. Answer based on your knowledge."

        prompt = self.prompt_template.format(
            context_clause=context_clause, question=question
        )

        response = self.llm.predict(prompt)
        return response.strip()
