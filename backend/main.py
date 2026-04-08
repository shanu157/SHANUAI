from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import webbrowser
import subprocess
import json
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# AI setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

# Admin commands storage (editable via dashboard)
admin_commands = {
    "open chrome": "webbrowser.open('https://google.com')",
    "greet": "print('Hello from admin')"
}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for conn in self.active_connections:
            await conn.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            command = await websocket.receive_text()
            # Process command with AI or custom map
            result = process_command(command)
            await websocket.send_text(json.dumps({"result": result}))
    except:
        manager.disconnect(websocket)

def process_command(cmd):
    # Check admin commands first
    if cmd in admin_commands:
        exec(admin_commands[cmd])
        return f"Executed: {cmd}"
    # Fallback to Gemini AI
    response = model.generate_content(cmd)
    return response.text

# Admin REST endpoints
@app.get("/admin/commands")
def get_commands():
    return admin_commands

@app.post("/admin/commands")
def update_command(name: str, code: str):
    admin_commands[name] = code
    # Optionally push update to all connected clients
    return {"status": "updated"}

@app.delete("/admin/commands/{name}")
def delete_command(name: str):
    if name in admin_commands:
        del admin_commands[name]
    return {"status": "deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
