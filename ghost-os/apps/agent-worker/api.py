"""GhostAgent FastAPI — Full SaaS backend.

Routes:
  Auth:     POST /auth/register, POST /auth/login, GET /auth/me
  Accounts: GET/POST /accounts, PUT /accounts/{id}/session
  Campaigns:GET/POST /campaigns, GET/PUT /campaigns/{id}
  Prospects:GET /campaigns/{id}/prospects, POST .../upload
  Queue:    GET /queue, POST /queue/{id}/approve|reject, POST /queue/bulk
  Stats:    GET /stats
  Agent:    POST /agent/start, POST /agent/stop, GET /agent/status/{id}
  Pipeline: GET /pipeline
  WS:       /ws/agent (live view + control)
"""

import os
import io
import csv
import json
import time
import signal
import asyncio
import redis.asyncio as aioredis
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

import db
from worker import broker, run_campaign_task, stop_campaign_task, login_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    await broker.startup()
    yield
    await broker.shutdown()


app = FastAPI(title="GhostAgent API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
JWT_SECRET = os.environ.get("JWT_SECRET", "ghost-os-dev-secret-change-in-prod")
JWT_ALGO = "HS256"
JWT_EXPIRY_DAYS = 30

security = HTTPBearer()


# ─── Auth Helpers ─────────────────────────────────────────────────────────────

def _make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def _verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    user_id = _verify_token(creds.credentials)
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user


# ─── Auth Routes ──────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/auth/register")
def register(req: RegisterRequest):
    existing = db.get_user_by_email(req.email)
    if existing:
        raise HTTPException(409, "Email already registered")
    pw_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    user = db.create_user(req.email, pw_hash, req.name)
    token = _make_token(user["id"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}

@app.post("/auth/login")
def login(req: LoginRequest):
    user = db.get_user_by_email(req.email)
    if not user or not bcrypt.checkpw(req.password.encode(), user["passwordHash"].encode()):
        raise HTTPException(401, "Invalid credentials")
    token = _make_token(user["id"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}

@app.get("/auth/me")
def me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


# ─── LinkedIn Accounts ────────────────────────────────────────────────────────

@app.get("/accounts")
def list_accounts(user: dict = Depends(get_current_user)):
    return db.get_accounts_for_user(user["id"])

@app.post("/accounts")
def create_account(user: dict = Depends(get_current_user)):
    return db.create_account(user["id"])

class SessionUpdate(BaseModel):
    liAt: str
    jsessionId: str

@app.put("/accounts/{account_id}/session")
def update_session(account_id: str, req: SessionUpdate, user: dict = Depends(get_current_user)):
    account = db.get_account(account_id)
    if not account or account["userId"] != user["id"]:
        raise HTTPException(404, "Account not found")
    db.update_account_session(account_id, req.liAt, req.jsessionId)
    return {"status": "ok"}

@app.post("/accounts/{account_id}/connect-linkedin")
async def connect_linkedin(account_id: str, user: dict = Depends(get_current_user)):
    """Spawn a login browser for this account. Dashboard shows it live."""
    account = db.get_account(account_id)
    if not account or account["userId"] != user["id"]:
        raise HTTPException(404, "Account not found")
    task = await login_task.kiq(account_id=account_id)
    return {"status": "started", "task_id": task.task_id}

@app.get("/accounts/{account_id}/stats")
def account_stats(account_id: str, user: dict = Depends(get_current_user)):
    account = db.get_account(account_id)
    if not account or account["userId"] != user["id"]:
        raise HTTPException(404, "Account not found")
    return db.get_daily_stats(account_id)


# ─── Campaigns ────────────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    linkedInAccountId: str
    name: str
    goal: str
    dailyConnectionLimit: Optional[int] = 15
    dailyMessageLimit: Optional[int] = 30
    activeHoursStart: Optional[int] = 9
    activeHoursEnd: Optional[int] = 18
    timezone: Optional[str] = "Asia/Kolkata"
    autoApprove: Optional[bool] = False
    personaTone: Optional[str] = "professional"
    personaSample: Optional[str] = None

@app.get("/campaigns")
def list_campaigns(user: dict = Depends(get_current_user)):
    return db.get_campaigns_for_user(user["id"])

@app.post("/campaigns")
def create_campaign(req: CampaignCreate, user: dict = Depends(get_current_user)):
    account = db.get_account(req.linkedInAccountId)
    if not account or account["userId"] != user["id"]:
        raise HTTPException(404, "LinkedIn account not found")
    return db.create_campaign(
        user["id"], req.linkedInAccountId, req.name, req.goal,
        dailyConnectionLimit=req.dailyConnectionLimit,
        dailyMessageLimit=req.dailyMessageLimit,
        activeHoursStart=req.activeHoursStart,
        activeHoursEnd=req.activeHoursEnd,
        timezone=req.timezone,
        autoApprove=req.autoApprove,
        personaTone=req.personaTone,
        personaSample=req.personaSample,
    )

@app.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, user: dict = Depends(get_current_user)):
    campaign = db.get_campaign(campaign_id)
    if not campaign or campaign["userId"] != user["id"]:
        raise HTTPException(404, "Campaign not found")
    return campaign

class CampaignStatusUpdate(BaseModel):
    status: str  # ACTIVE, PAUSED, COMPLETED

@app.put("/campaigns/{campaign_id}/status")
def update_campaign_status(campaign_id: str, req: CampaignStatusUpdate, user: dict = Depends(get_current_user)):
    campaign = db.get_campaign(campaign_id)
    if not campaign or campaign["userId"] != user["id"]:
        raise HTTPException(404, "Campaign not found")
    db.update_campaign_status(campaign_id, req.status)
    return {"status": "ok"}

@app.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, user: dict = Depends(get_current_user)):
    campaign = db.get_campaign(campaign_id)
    if not campaign or campaign["userId"] != user["id"]:
        raise HTTPException(404, "Campaign not found")
    db.delete_campaign(campaign_id)
    return {"status": "ok"}


# ─── Prospects ────────────────────────────────────────────────────────────────

@app.get("/campaigns/{campaign_id}/prospects")
def list_prospects(campaign_id: str, limit: int = 50, offset: int = 0,
                   user: dict = Depends(get_current_user)):
    campaign = db.get_campaign(campaign_id)
    if not campaign or campaign["userId"] != user["id"]:
        raise HTTPException(404, "Campaign not found")
    return db.get_prospects_for_campaign(campaign_id, limit, offset)

@app.post("/campaigns/{campaign_id}/prospects/upload")
async def upload_prospects(campaign_id: str, file: UploadFile = File(...),
                           user: dict = Depends(get_current_user)):
    campaign = db.get_campaign(campaign_id)
    if not campaign or campaign["userId"] != user["id"]:
        raise HTTPException(404, "Campaign not found")

    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    prospects = []
    for row in reader:
        # Accept flexible column names
        url = (row.get("linkedInUrl") or row.get("linkedin_url") or
               row.get("LinkedIn URL") or row.get("url") or "").strip()
        if not url:
            continue
        prospects.append({
            "linkedInUrl": url,
            "name": (row.get("name") or row.get("Name") or "").strip() or None,
            "headline": (row.get("headline") or row.get("Headline") or "").strip() or None,
            "company": (row.get("company") or row.get("Company") or "").strip() or None,
            "notes": (row.get("notes") or row.get("Notes") or "").strip() or None,
        })

    count = db.bulk_create_prospects(campaign_id, prospects)
    return {"imported": count, "total_rows": len(prospects)}

class ProspectAdd(BaseModel):
    linkedInUrl: str
    name: Optional[str] = None
    headline: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None

@app.post("/campaigns/{campaign_id}/prospects")
def add_prospect(campaign_id: str, req: ProspectAdd, user: dict = Depends(get_current_user)):
    campaign = db.get_campaign(campaign_id)
    if not campaign or campaign["userId"] != user["id"]:
        raise HTTPException(404, "Campaign not found")
    prospect_id = db.create_prospect(
        campaign_id, req.linkedInUrl, req.name, req.headline, req.company, req.notes
    )
    return {"id": prospect_id}


# ─── Approval Queue ───────────────────────────────────────────────────────────

def _get_account_for_user(account_id: str, user_id: str) -> dict:
    account = db.get_account(account_id)
    if not account or account["userId"] != user_id:
        raise HTTPException(404, "Account not found")
    return account

@app.get("/queue")
def get_queue(account_id: str, user: dict = Depends(get_current_user)):
    _get_account_for_user(account_id, user["id"])
    messages = db.get_pending_messages(account_id, limit=30)
    stats = db.get_queue_stats(account_id)
    return {"messages": messages, "stats": stats}

class ApproveRequest(BaseModel):
    editedContent: Optional[str] = None

@app.post("/queue/{message_id}/approve")
def approve_message(message_id: str, req: ApproveRequest, user: dict = Depends(get_current_user)):
    db.approve_message(message_id, req.editedContent)
    return {"status": "ok"}

@app.post("/queue/{message_id}/reject")
def reject_message(message_id: str, user: dict = Depends(get_current_user)):
    db.reject_message(message_id)
    return {"status": "ok"}

class BulkQueueAction(BaseModel):
    action: str  # "approve" or "reject"
    account_id: str

@app.post("/queue/bulk")
def bulk_queue_action(req: BulkQueueAction, user: dict = Depends(get_current_user)):
    _get_account_for_user(req.account_id, user["id"])
    count = db.bulk_update_messages(req.account_id, req.action)
    return {"updated": count}


# ─── Pipeline ────────────────────────────────────────────────────────────────

@app.get("/pipeline")
def get_pipeline(account_id: str, user: dict = Depends(get_current_user)):
    _get_account_for_user(account_id, user["id"])
    prospects = db.get_pipeline_prospects(account_id)
    stats = db.get_pipeline_stats(account_id)
    return {"prospects": prospects, "stats": stats}


# ─── Stats ────────────────────────────────────────────────────────────────────

@app.get("/stats")
def get_stats(account_id: str, user: dict = Depends(get_current_user)):
    _get_account_for_user(account_id, user["id"])
    return db.get_daily_stats(account_id)


# ─── Agent Control ────────────────────────────────────────────────────────────

class AgentStart(BaseModel):
    account_id: str
    continuous: bool = True
    skip_warmup: bool = False
    task_id: Optional[str] = None

class AgentStop(BaseModel):
    account_id: str

@app.post("/agent/start")
async def start_agent(req: AgentStart, user: dict = Depends(get_current_user)):
    account = _get_account_for_user(req.account_id, user["id"])
    if account["agentStatus"] == "RUNNING":
        raise HTTPException(409, "Agent already running for this account")
    # Mark as RUNNING immediately to prevent double-start race condition
    db.update_account_status(req.account_id, "RUNNING")
    if req.skip_warmup and account.get("warmupStatus") != "COMPLETED":
        db.update_warmup_state(req.account_id, "COMPLETED")
    # Validate task ownership if provided
    if req.task_id:
        task = db.get_agent_task(req.task_id)
        if not task or task["userId"] != user["id"]:
            raise HTTPException(404, "Task not found")
    task = await run_campaign_task.kiq(
        account_id=req.account_id,
        continuous=req.continuous,
        skip_warmup=req.skip_warmup,
        task_id=req.task_id,
    )
    return {"status": "started", "task_id": task.task_id}

@app.post("/agent/stop")
async def stop_agent(req: AgentStop, user: dict = Depends(get_current_user)):
    _get_account_for_user(req.account_id, user["id"])
    r = aioredis.from_url(REDIS_URL)
    try:
        pid_bytes = await r.get(f"ghost_os_pid_{req.account_id}")
        if pid_bytes:
            pid = int(pid_bytes)
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            await r.delete(f"ghost_os_pid_{req.account_id}")
        db.update_account_status(req.account_id, "IDLE")
        return {"status": "stopped"}
    finally:
        await r.aclose()

@app.get("/agent/status/{account_id}")
def agent_status(account_id: str, user: dict = Depends(get_current_user)):
    _get_account_for_user(account_id, user["id"])
    account = db.get_account(account_id)
    sessions = db.get_recent_sessions(account_id, limit=5)
    return {
        "agentStatus": account["agentStatus"],
        "sessionStatus": account["sessionStatus"],
        "warmupStatus": account["warmupStatus"],
        "lastSessionAt": account["lastSessionAt"],
        "recentSessions": sessions,
    }


# ─── Agent Tasks ─────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    linkedInAccountId: str
    title: str
    instruction: str

@app.get("/tasks")
def list_tasks(user: dict = Depends(get_current_user)):
    return db.get_tasks_for_user(user["id"])

@app.post("/tasks")
def create_task(req: TaskCreate, user: dict = Depends(get_current_user)):
    account = db.get_account(req.linkedInAccountId)
    if not account or account["userId"] != user["id"]:
        raise HTTPException(404, "LinkedIn account not found")
    return db.create_agent_task(user["id"], req.linkedInAccountId, req.title, req.instruction)

@app.get("/tasks/{task_id}")
def get_task(task_id: str, user: dict = Depends(get_current_user)):
    task = db.get_agent_task(task_id)
    if not task or task["userId"] != user["id"]:
        raise HTTPException(404, "Task not found")
    return task

@app.post("/tasks/{task_id}/run")
async def run_task(task_id: str, user: dict = Depends(get_current_user)):
    task = db.get_agent_task(task_id)
    if not task or task["userId"] != user["id"]:
        raise HTTPException(404, "Task not found")
    account = _get_account_for_user(task["linkedInAccountId"], user["id"])
    if account["agentStatus"] == "RUNNING":
        raise HTTPException(409, "Agent already running for this account")
    db.update_account_status(task["linkedInAccountId"], "RUNNING")
    queued = await run_campaign_task.kiq(
        account_id=task["linkedInAccountId"],
        continuous=False,
        skip_warmup=True,
        task_id=task_id,
    )
    return {"status": "started", "task_id": queued.task_id}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    task = db.get_agent_task(task_id)
    if not task or task["userId"] != user["id"]:
        raise HTTPException(404, "Task not found")
    db.delete_agent_task(task_id)
    return {"status": "ok"}


# ─── WebSocket Live View ──────────────────────────────────────────────────────

@app.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket):
    """Unified WebSocket: live screen stream + agent status + dashboard control."""
    await websocket.accept()
    r = aioredis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe("live_view", "agent_status")

    async def broadcast_task():
        async for message in pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"].decode()
                data = message["data"].decode() if isinstance(message["data"], bytes) else message["data"]
                msg_type = "screen" if channel == "live_view" else "status"
                await websocket.send_json({"type": msg_type, "data": data})

    async def input_task():
        while True:
            data = await websocket.receive_json()
            await r.publish("agent_input", json.dumps(data))

    tasks = [asyncio.ensure_future(broadcast_task()), asyncio.ensure_future(input_task())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for t in pending:
            t.cancel()
        for t in done:
            t.exception()  # surface any non-disconnect exceptions
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        for t in tasks:
            t.cancel()
        await pubsub.unsubscribe("live_view", "agent_status")
        await r.aclose()

@app.websocket("/ws/live/{account_id}")
async def ws_live(websocket: WebSocket, account_id: str):
    """Per-account live view stream for multi-user support."""
    await websocket.accept()
    r = aioredis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"live_view_{account_id}", f"agent_status_{account_id}")

    async def broadcast_task():
        async for message in pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"].decode()
                data = message["data"].decode() if isinstance(message["data"], bytes) else message["data"]
                msg_type = "screen" if "live_view" in channel else "status"
                await websocket.send_json({"type": msg_type, "data": data})

    async def input_task():
        while True:
            data = await websocket.receive_json()
            await r.publish(f"agent_input_{account_id}", json.dumps(data))

    tasks = [asyncio.ensure_future(broadcast_task()), asyncio.ensure_future(input_task())]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for t in pending:
            t.cancel()
        for t in done:
            t.exception()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        for t in tasks:
            t.cancel()
        await pubsub.unsubscribe(f"live_view_{account_id}", f"agent_status_{account_id}")
        await r.aclose()


# ─── Legacy endpoint (backward compat with old dashboard) ────────────────────

class LegacyCampaignRequest(BaseModel):
    prospects: str

@app.post("/start-campaign")
async def legacy_start_campaign(req: LegacyCampaignRequest):
    """Kept for backward compatibility. Use /agent/start for new code."""
    prospects_list = [p.strip() for p in req.prospects.split("\n") if p.strip()]
    task = await run_campaign_task.kiq(account_id=None, continuous=False, legacy_prospects=prospects_list)
    return {"status": "success", "task_id": task.task_id}

@app.post("/stop-campaign")
async def legacy_stop_campaign():
    task = await stop_campaign_task.kiq(account_id=None)
    return {"status": "success", "message": "Stop signal sent"}
