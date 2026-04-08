import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from typing import Dict, List

# ---------- Config ----------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

app = FastAPI(title="AI Voice Assistant Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Admin Command Store (in-memory for demo, use Supabase later) ----------
admin_commands: Dict[str, str] = {
    "greet": "print('Hello from admin')",
    "open google": "webbrowser.open('https://google.com')",
    "tell time": "print(datetime.datetime.now())"
}

# ---------- WebSocket Manager ----------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# ---------- Command Processor ----------
def process_command(command: str) -> str:
    # 1. Check admin commands
    if command in admin_commands:
        try:
            # WARNING: exec is unsafe; use with caution. Better to map to safe functions.
            exec(admin_commands[command])
            return f"Executed admin command: {command}"
        except Exception as e:
            return f"Error executing admin command: {str(e)}"

    # 2. Use Gemini AI
    try:
        response = model.generate_content(command)
        return response.text
    except Exception as e:
        return f"AI error: {str(e)}"

# ---------- WebSocket Endpoint ----------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                cmd_json = json.loads(data)
                command = cmd_json.get("command", "")
            except:
                command = data
            result = process_command(command)
            await websocket.send_text(json.dumps({"result": result}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ---------- REST Admin API ----------
class CommandUpdate(BaseModel):
    code: str

@app.get("/admin/commands")
def get_commands():
    return admin_commands

@app.post("/admin/commands/{name}")
def update_command(name: str, update: CommandUpdate):
    admin_commands[name] = update.code
    return {"status": "updated", "command": name}

@app.delete("/admin/commands/{name}")
def delete_command(name: str):
    if name in admin_commands:
        del admin_commands[name]
    return {"status": "deleted"}

# ---------- Health Check ----------
@app.get("/")
def health():
    return {"status": "alive"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
