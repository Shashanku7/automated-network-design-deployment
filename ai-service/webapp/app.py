"""FastAPI webapp – Network Automation Multi-Agent Workflow."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from webapp.routes import router, kafka_mgr, process_kafka_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    await kafka_mgr.start()
    asyncio.create_task(kafka_mgr.consume_tasks(process_kafka_task))
    yield
    await kafka_mgr.stop()


app = FastAPI(title="Network Automation Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
