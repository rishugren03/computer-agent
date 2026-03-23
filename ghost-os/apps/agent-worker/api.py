import os
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from worker import broker, run_campaign_task

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

class CampaignRequest(BaseModel):
    prospects: str

@app.post("/start-campaign")
async def start_campaign(req: CampaignRequest):
    """Parses a list of names/URLs and drops them onto the Redis loop."""
    prospects_list = [p.strip() for p in req.prospects.split("\n") if p.strip()]
    await broker.startup()
    task = await run_campaign_task.kiq(prospects=prospects_list, continuous=False)
    await broker.shutdown()
    return {"status": "success", "task_id": task.task_id}

@app.websocket("/ws/live")
async def websocket_live_view(websocket: WebSocket):
    """Pipes base64 screenshots from the Playwright background thread natively to the user dashboard."""
    await websocket.accept()
    r = redis.from_url(redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe("live_view")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                # Send the base64 string to the frontend
                await websocket.send_text(data.decode("utf-8") if isinstance(data, bytes) else data)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe("live_view")
        await r.aclose()
