from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.connection import close_pool
from routers.chat import router as chat_router
from routers.simulate import router as simulate_router
from routers.stats import router as stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pool()


app = FastAPI(title="AptChat API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(simulate_router)
app.include_router(stats_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
