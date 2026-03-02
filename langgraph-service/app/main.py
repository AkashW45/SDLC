from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


from .sdlc_api import router as sdlc_router

# 1️⃣ Create app FIRST
app = FastAPI()

# 2️⃣ Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3️⃣ Register routers
app.include_router(sdlc_router)

