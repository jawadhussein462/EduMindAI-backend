from pathlib import Path
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

from api.constants import OPENAI_API_KEY
from api.agents import (
    BaseAgent,
    ExamRetrieverAgent,
    ExamGeneratorAgent,
    QuestionGeneratorAgent,
    AnswerAgent,
    ClarifierAgent,
)


class RouterAgent(BaseAgent):
    def __init__(self, base_vector_dir: Path):
        self.base_vector_dir = Path(base_vector_dir)

        # Load agents
        self.exam_retriever = ExamRetrieverAgent(self.base_vector_dir)
        self.exam_generator = ExamGeneratorAgent(self.base_vector_dir)
        self.question_generator = QuestionGeneratorAgent(self.base_vector_dir)
        self.answer_agent = AnswerAgent(self.base_vector_dir)
        self.clarifier_agent = ClarifierAgent(self.base_vector_dir)

        # LLM for intent classification
        self.llm = ChatOpenAI(api_key=OPENAI_API_KEY)
        self.intent_prompt = PromptTemplate.from_template(
            """
You are an intent classifier for an exam assistant.
Classify the user's request into one of these intents:
- retrieve_exam
- generate_exam
- generate_questions
- answer_question
- clarify

Respond ONLY with the intent name, nothing else.

User message: {query}
        """
        )

        # from langchain.chains import LLMChain
        # self.intent_chain = LLMChain(llm=self.llm, prompt=self.intent_prompt)
        self.intent_chain = self.intent_prompt | self.llm

    def classify_intent(self, query: str) -> str:
        result = self.intent_chain.run(query)
        return result.strip().lower()

    def run(self, query: str | Dict[str, Any]) -> str:
        # Accept string input or dict
        if isinstance(query, str):
            intent = self.classify_intent(query)
            metadata = {}  # could use LLM to extract structured info
        elif isinstance(query, dict):
            intent = query.get("intent") or self.classify_intent(query["query"])
            metadata = query
        else:
            return "❌ Invalid input format."

        # Dispatch
        if intent == "retrieve_exam":
            return self.exam_retriever.run(metadata)

        elif intent == "generate_exam":
            return self.exam_generator.run(metadata)

        elif intent == "generate_questions":
            return self.question_generator.run(metadata)

        elif intent == "answer_question":
            return self.answer_agent.run(metadata)

        elif intent == "clarify":
            return self.clarifier_agent.run(metadata)

        else:
            return f"❓ Unknown intent: {intent}"


if __name__ == "__main__":
    router = RouterAgent(base_vector_dir="outputs/chroma_store")

    # Test Exam Retriever Agent
    queries = [
        "Can you show me a final exam in grade 9 math?",
        {
            "query": "I want to generate a new physics exam",
            "grade": "grade_10",
            "subject": "physics",
        },
        "Give me some questions on photosynthesis",
    ]

    for q in queries:
        print(f"\n Query: {q}")
        print(router.run(q))

    # Test Exam Generator Agent
    query = {
        "intent": "generate_exam",
        "subject": "biology",
        "grade": "grade_10",
        "topic": "photosynthesis",
        "num_questions": 5,
        "exam_type": "partial",
    }

    print(router.run(query))

    # Test Questions Generator Agent
    query = {
        "intent": "generate_questions",
        "subject": "physics",
        "grade": "grade_11",
        "topic": "Newton's laws of motion",
        "num_questions": 3,
        "question_type": "short answer",
    }

    print(router.run(query))

    # Test Answer Agent
    query = {
        "intent": "answer_question",
        "subject": "math",
        "grade": "grade_9",
        "question": "What is the area of a triangle with base 10cm and height 5cm?",
    }

    print(router.run(query))

    # Test Clarification Agent
    query = {
        "intent": "clarify",
        "subject": "biology",
        "grade": "grade_9",
        "query": "Can you explain the difference between mitosis and meiosis?",
    }

    print(router.run(query))
