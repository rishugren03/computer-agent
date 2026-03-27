import os
import json
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from worker import broker, run_campaign_task, stop_campaign_task

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

@app.middleware("http")
async def log_requests(request, call_next):
    print(f"[{request.method}] {request.url}")
    print(request.headers)
    response = await call_next(request)
    return response

@app.post("/start-campaign")
async def start_campaign(req: CampaignRequest):
    """Parses a list of names/URLs and drops them onto the Redis loop."""
    prospects_list = [p.strip() for p in req.prospects.split("\n") if p.strip()]
    await broker.startup()
    task = await run_campaign_task.kiq(prospects=prospects_list, continuous=False)
    await broker.shutdown()
    return {"status": "success", "task_id": task.task_id}

@app.post("/stop-campaign")
async def stop_campaign():
    """Triggers the worker to natively kill the active campaign process."""
    await broker.startup()
    task = await stop_campaign_task.kiq()
    await broker.shutdown()
    return {"status": "success", "message": "Stop signal sent, execution aborted."}

@app.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    """Unified WebSocket for Ghost-OS: handles live view, status updates, and dashboard inputs."""
    # Debug: Log incoming WebSocket headers to identify origin issues
    print(f"[WS] Connection attempt from: {websocket.client}")
    print(f"[WS] Headers: {websocket.headers}")
    
    # Accept the connection explicitly
    await websocket.accept()
    print("[WS] Connection accepted")
    r = redis.from_url(redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe("live_view", "agent_status")
    
    # Task to handle server-to-client broadcasts
    async def broadcast_task():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"].decode("utf-8")
                    data = message["data"].decode("utf-8") if isinstance(message["data"], bytes) else message["data"]
                    
                    msg_type = "screen" if channel == "live_view" else "status"
                    await websocket.send_json({"type": msg_type, "data": data})
        except Exception as e:
            print(f"[WS] Broadcast error: {e}")

    # Task to handle client-to-server inputs
    async def input_task():
        try:
            while True:
                data = await websocket.receive_json()
                # Publish dashboard interaction to Redis for the agent process
                await r.publish("agent_input", json.dumps(data))
        except WebSocketDisconnect:
            raise
        except Exception as e:
            print(f"[WS] Input error: {e}")

    import asyncio
    try:
        # Run both tasks concurrently
        await asyncio.gather(broadcast_task(), input_task())
    except WebSocketDisconnect:
        print("[WS] Dashboard disconnected")
    except Exception as e:
        print(f"[WS] Unified WebSocket error: {e}")
    finally:
        await pubsub.unsubscribe("live_view", "agent_status")
        await r.aclose()
