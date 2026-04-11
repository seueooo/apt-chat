from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.simulate import router as simulate_router
from api.stats import router as stats_router
from config import CORS_ORIGINS
from db.connection import close_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pool()


app = FastAPI(title="AptChat API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(simulate_router)
app.include_router(stats_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
