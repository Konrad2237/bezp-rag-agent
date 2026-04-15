from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

from routers import auth, quiz, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Uruchamiam backend...")
    yield
    print("Zamykam backend...")


app = FastAPI(
    title="BEZ PIERDOLENIA — AI Trener",
    version="0.1.0",
    lifespan=lifespan,
    swagger_ui_init_oauth={},
    openapi_tags=[
        {"name": "auth"},
        {"name": "quiz"},
        {"name": "chat"},
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])


@app.get("/health")
async def health():
    return {"status": "ok"}
