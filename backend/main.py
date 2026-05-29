import os
import json
import asyncio
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
import google.generativeai as genai

# ===== CONFIG =====
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

app = FastAPI(title="SHANU AI - Jarvis Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ===== MEMORY STORE =====
memory_store: List[dict] = []
schedules: List[dict] = []
user_profile = {
    "name": "Shanu",
    "dream": "Professional Footballer",
    "favourite_player": "Cristiano Ronaldo"
}

# ===== JARVIS SYSTEM PROMPT =====
JARVIS_PROMPT = """You are SHANU AI, a Jarvis-like personal AI assistant for Shanu.
You are intelligent, helpful, and speak like Jarvis from Iron Man — professional but friendly.
You know:
- Shanu loves football and wants to be a professional footballer
- Shanu's favourite player is Cristiano Ronaldo (CR7)
- Shanu is learning Python and building AI systems
- You are running on a cloud server, accessible from any device worldwide

You can help with:
- General questions and conversation
- Weather (tell user to ask "weather in [city]")
- Time and date
- Motivational quotes
- Football news and facts
- Programming help
- Scheduling reminders
- Device commands (open apps, make calls - tell user these work via the app)

Keep responses concise and smart. Use emojis occasionally.
When user says "schedule" or "remind", acknowledge and confirm the schedule.
When user asks for time, give current time.
Always address the user as "Shanu" occasionally.
"""

# ===== WEBSOCKET MANAGER =====
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        print(f"Client connected. Total: {len(self.active)}")
    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
    async def broadcast(self, msg: str):
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except:
                pass

manager = ConnectionManager()

# ===== COMMAND PROCESSOR =====
async def process_command(command: str) -> str:
    command_lower = command.lower().strip()

    # TIME
    if any(w in command_lower for w in ["time", "what time", "current time"]):
        now = datetime.datetime.now().strftime("%I:%M %p")
        date = datetime.datetime.now().strftime("%A, %B %d %Y")
        return f"⏰ Current time: {now}\n📅 Date: {date}"

    # SCHEDULE
    if any(w in command_lower for w in ["remind", "schedule", "set alarm", "set reminder"]):
        schedules.append({
            "task": command,
            "time": datetime.datetime.now().isoformat(),
            "status": "pending"
        })
        if model:
            try:
                r = model.generate_content(JARVIS_PROMPT + f"\nUser said: {command}\nRespond confirming you've noted this schedule/reminder.")
                return r.text
            except:
                pass
        return f"✅ Noted! I've scheduled: '{command}'"

    # MEMORY
    if command_lower.startswith("remember "):
        fact = command[9:]
        memory_store.append({"fact": fact, "time": datetime.datetime.now().isoformat()})
        return f"🧠 Memory saved: {fact}"

    if any(w in command_lower for w in ["what do you remember", "my memory", "show memory"]):
        if not memory_store:
            return "🧠 No memories saved yet. Say 'remember [something]' to save!"
        items = memory_store[-5:]
        return "🧠 I remember:\n" + "\n".join([f"• {m['fact']}" for m in items])

    # FOOTBALL
    if any(w in command_lower for w in ["football", "cr7", "ronaldo", "messi", "mbappe", "goal"]):
        if model:
            try:
                r = model.generate_content(JARVIS_PROMPT + f"\nUser asked about football: {command}\nGive an exciting football-related response!")
                return r.text
            except:
                pass
        return "⚽ Football is life! CR7 is the GOAT with 900+ goals! Keep training Shanu! 🔥"

    # MOTIVATION
    if any(w in command_lower for w in ["motivat", "inspire", "quote"]):
        quotes = [
            "💪 'Your talent is God's gift to you. What you do with it is your gift back to God.' — Leo Buscaglia",
            "🔥 'I am not talented, I am obsessed.' — Cristiano Ronaldo",
            "⚽ 'The more difficult the victory, the greater the happiness in winning.' — Pelé",
            "🌟 'Hard work beats talent when talent doesn't work hard.' — Tim Notke",
            "💎 'Dream big. Work hard. Stay focused.' — Keep going Shanu!"
        ]
        import random
        return random.choice(quotes)

    # GEMINI AI (fallback for everything else)
    if model:
        try:
            full_prompt = JARVIS_PROMPT + f"\n\nUser: {command}\nJarvis:"
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"⚠️ AI temporarily unavailable: {str(e)[:100]}"
    else:
        return "⚠️ AI model not loaded. Check API key and model availability."

# ===== ROUTES =====
@app.get("/")
async def root():
    return {
        "status": "alive",
        "model": str(model._model_name if model else "none"),
        "memories": len(memory_store),
        "schedules": len(schedules)
    }

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.datetime.now().isoformat()}

@app.get("/memory")
async def get_memory():
    return {"memory": memory_store}

@app.get("/schedules")
async def get_schedules():
    return {"schedules": schedules}

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
            if command:
                result = await process_command(command)
                await websocket.send_text(json.dumps({"result": result, "status": "ok"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# REST API for mobile apps
class CommandRequest(BaseModel):
    command: str

@app.post("/command")
async def rest_command(req: CommandRequest):
    result = await process_command(req.command)
    return {"result": result, "status": "ok"}
