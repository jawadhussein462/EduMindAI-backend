from pathlib import Path
from typing import Dict, Any

from langchain.prompts import PromptTemplate
from langchain_community.vectorstores.chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from api.constants import OPENAI_API_KEY
from api.agents.base_agent import BaseAgent


class ClarifierAgent(BaseAgent):
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
You are a helpful tutor who explains educational concepts clearly to students.

Explain the following in a simple, clear, and accurate way.

{context_clause}

Clarification request:
{query}

Explanation:
        """
        )

    def retrieve_context(self, subject: str, grade: str, query: str, k: int = 4) -> str:
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
        docs = retriever.get_relevant_documents(query)
        context = "\n\n".join([doc.page_content for doc in docs])
        return context

    def run(self, query: Dict[str, Any]) -> str:
        subject = query.get("subject")
        grade = query.get("grade")
        clarification = query.get("query")

        if not subject or not grade or not clarification:
            return "❌ 'subject', 'grade', and 'query' are required for clarification."

        context_clause = ""
        if self.with_context:
            context = self.retrieve_context(subject, grade, clarification)
            if context:
                context_clause = f"Use this context for explanation:\n\n{context}"
            else:
                context_clause = "No relevant context found. Use general knowledge."

        prompt = self.prompt_template.format(
            context_clause=context_clause, query=clarification
        )

        response = self.llm.predict(prompt)
        return response.strip()
