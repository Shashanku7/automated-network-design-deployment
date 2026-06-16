import sys
from pathlib import Path
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add parent to path for global config/search imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.config import STATIC_DIR
from webapp.routes import router
from webapp.kafka_provider import kafka_provider
from webapp.routes import process_kafka_task

app = FastAPI(title="Network Automation Assistant")

@app.on_event("startup")
async def startup_event():
    await kafka_provider.start()
    asyncio.create_task(kafka_provider.listen_tasks(process_kafka_task))

@app.on_event("shutdown")
async def shutdown_event():
    await kafka_provider.stop()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
