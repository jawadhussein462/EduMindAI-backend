from pathlib import Path
from typing import Dict, Any, Optional

from langchain_community.vectorstores.chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA

from api.constants import OPENAI_API_KEY
from api.agents.base_agent import BaseAgent


class ExamRetrieverAgent(BaseAgent):
    def __init__(
        self,
        base_vector_dir: Path,
        model_name: str = "gpt-4",
        k: int = 10,
    ):
        self.base_vector_dir = Path(base_vector_dir)
        self.k = k
        self.llm = ChatOpenAI(model_name=model_name, api_key=OPENAI_API_KEY)
        self.embedding_model = OpenAIEmbeddings(api_key=OPENAI_API_KEY)

    def load_vectorstore(self, subject: str, grade: str) -> Optional[Chroma]:
        collection = f"{subject}_{grade}".lower().replace(" ", "_")
        path = self.base_vector_dir / collection
        if not path.exists():
            print(f"⚠️ No vector store found at {path}")
            return None

        return Chroma(
            persist_directory=str(path),
            collection_name=collection,
            embedding_function=self.embedding_model,
        )

    def run(self, query: Dict[str, Any]) -> str:
        subject = query.get("subject")
        grade = query.get("grade")
        exam_type = query.get("exam_type", "any")  # optional

        if not subject or not grade:
            return "❌ Missing subject or grade."

        vs = self.load_vectorstore(subject, grade)
        if not vs:
            return f"No data available for {subject}, {grade}"

        retriever = vs.as_retriever(search_kwargs={"k": self.k})

        system_prompt = (
            "You are a helpful assistant that retrieves exams from a database. "
            "Use only the retrieved context to present a relevant exam or exam fragments."
        )

        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            retriever=retriever,
            chain_type="stuff",
            chain_type_kwargs={"prompt": None},  # default prompt
            return_source_documents=True,
        )

        question = f"Retrieve a complete {exam_type} exam in {subject} for {grade}."
        result = qa_chain(question)

        return result["result"]


if __name__ == "__main__":

    agent = ExamRetrieverAgent(base_vector_dir="outputs/chroma_store")

    query = {"subject": "math", "grade": "grade_9", "exam_type": "final"}

    response = agent.run(query)
    print("\n Retrieved Exam:\n")
    print(response)
