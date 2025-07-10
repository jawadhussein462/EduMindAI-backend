# EduMindAI-backend

EduMindAI-backend is a Retrieval-Augmented Generation (RAG) chatbot API specialized in exam preparation. It leverages state-of-the-art language models (LLMs) and a vector store to provide contextually relevant answers based on a large collection of exam documents. The backend is built with FastAPI and is designed for extensibility and robust educational support.

## Features
- **Retrieval-Augmented Generation (RAG)**: Combines LLMs with a vector store for context-aware answers.
- **Exam Preparation**: Specialized in answering questions and retrieving content from a large set of exam documents.
- **REST API**: Built with FastAPI for high performance and easy integration.
- **Search & Chat Endpoints**: Interactive Q&A and semantic search over exam data.
- **Document Pipeline**: Automated parsing, chunking, and embedding of exam files.
- **Docker Support**: Easy deployment with Docker.

## Installation

### Prerequisites
- Python 3.9+
- [pip](https://pip.pypa.io/en/stable/)

### Clone the Repository
```bash
git clone <repo-url>
cd EduMindAI-backend
```

### Install Dependencies
```bash
pip install -r api/requirements.txt
```

### (Optional) Run with Docker
```bash
docker build -t edumindai-backend .
docker run -p 80:80 edumindai-backend
```

## Configuration

Edit `api/config.yaml` to set your API keys and model parameters:
- `openai_api_key`: Your OpenAI API key
- `azure_formrecognizer_key` and `azure_formrecognizer_endpoint`: For Azure Form Recognizer (optional)
- `exams_path`: Path to the folder containing exam documents

## Usage

### Run Locally
```bash
uvicorn api.main:app --reload
```
The API will be available at `http://127.0.0.1:8000/`.

### Main Endpoints
- `GET /` — Health check, returns welcome message.
- `POST /api/chat` — Chat with the AI. `{ "message": "..." }`
- `GET /api/chat` — Chat via GET. `?message=...`
- `POST /api/search` — Search exam content. `{ "query": "...", "subject": "...", "k": 5 }`
- `GET /api/search` — Search via GET. `?query=...&subject=...&k=5`
- `GET /api/subjects` — List available exam subjects.
- `POST /api/clear` — Clear chat history.
- `GET /api/context` — Get relevant context for a message.

## Development
- Main app: `api/main.py`
- Chatbot logic: `api/chatbot.py`
- Exam data pipeline: `api/rag/exam_data_pipeline.py`
- Requirements: `api/requirements.txt`

### Linting & Formatting
You may use tools like `black` and `flake8` for code quality.

## License

This project is licensed under the MIT License.
