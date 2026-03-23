import os
import uvicorn
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config import DATA_DIR, SCREENSHOT_DIR

app = FastAPI(title="GhostAgent Audit Dashboard")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "dashboard")
AUDIT_LOG_FILE = os.path.join(DATA_DIR, "audit_logs.jsonl")

# Ensure directories exist
os.makedirs(DASHBOARD_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Mount screenshots directory so the UI can load them
app.mount("/screenshots", StaticFiles(directory=SCREENSHOT_DIR), name="screenshots")

@app.get("/api/logs")
def get_logs():
    """Read the JSONL audit file and return as a JSON array."""
    logs = []
    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        logs.append(json.loads(line))
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Failed to read logs: {str(e)}"})
    
    # Return newest first
    return JSONResponse(content=logs[::-1])

# Mount the static dashboard application files last (catch-all for HTML/JS/CSS)
app.mount("/", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")

if __name__ == "__main__":
    import json
    print("🚀 Starting GhostAgent Audit Dashboard...")
    print(f"📂 Serving dashboard from: {DASHBOARD_DIR}")
    print(f"📂 Serving screenshots from: {SCREENSHOT_DIR}")
    print(f"📊 Reading logs from: {AUDIT_LOG_FILE}")
    print("👉 Open http://localhost:8000 in your browser")
    uvicorn.run("dashboard:app", host="0.0.0.0", port=8000, reload=True)
