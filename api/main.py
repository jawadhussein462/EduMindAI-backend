from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI

from api.agents.router import RouterAgent


app = FastAPI(
    title="EduMindAI", description="Multi-agent RAG system for exams", version="1.0.0"
)

# Load your router agent once
router_agent = RouterAgent(base_vector_dir=Path(".chroma_db/"))


class QueryRequest(BaseModel):
    query: str | None = None
    intent: str | None = None
    subject: str | None = None
    grade: str | None = None
    topic: str | None = None
    question: str | None = None
    exam_type: str | None = None
    num_questions: int | None = None
    question_type: str | None = None


@app.post("/agent/")
async def route_agent(request: QueryRequest):
    query_dict = request.dict(exclude_none=True)

    if not query_dict:
        return {"error": "No input provided"}

    try:
        result = router_agent.run(query_dict)
        return {"response": result}
    except Exception as e:
        return {"error": str(e)}


#### SIMPLE TEST  ####
# open http://127.0.0.1:8000/docs
# curl -X POST http://127.0.0.1:8000/agent/ \
#  -H "Content-Type: application/json" \
#  -d '{
#    "intent": "generate_questions",
#    "subject": "math",
#    "grade": "grade_8",
#    "topic": "fractions",
#    "num_questions": 3
#  }'
