from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from config_loader import load_config, AppConfig
from chatbot.chatbot import ExamQuestionAgent
from loguru import logger

# Load configuration
config: AppConfig = load_config()

# Initialize FastAPI app
app = FastAPI(title="EduMind AI Chatbot")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize chatbot
chatbot = ExamQuestionAgent(config)


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    error: Optional[str] = None


class ClarificationRequest(BaseModel):
    message: str


class ClarificationResponse(BaseModel):
    clarification_needed: bool
    clarification: str


@app.get("/")
async def root():
    return {"message": "Welcome to the EduMind AI Chatbot API"}


@app.get("/api/chat")
async def chat_get_endpoint(message: str):
    try:
        response = await chatbot.send_message(message)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat_post_endpoint(chat_message: ChatMessage):
    try:
        response = await chatbot.send_message(chat_message.message)
        return ChatResponse(response=response)
    except Exception as e:
        return ChatResponse(response="", error=str(e))
 

@app.post("/api/clarify", response_model=ClarificationResponse)
async def clarify_endpoint(clarification_request: ClarificationRequest):
    try:
        result = await chatbot.ask_for_clarification(clarification_request.message)
        return ClarificationResponse(**result)
    except Exception as e:
        return ClarificationResponse(
            clarification_needed=False,
            clarification=f"Error: {str(e)}"
        )
