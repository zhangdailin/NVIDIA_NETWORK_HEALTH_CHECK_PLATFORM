from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api import router
import os

app = FastAPI(title="NVIDIA Network Health Check Platform")

# CORS
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)

# Mount uploads directory to serve generated HTML files (like topo)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to NVIDIA Network Health Check Platform API"}

