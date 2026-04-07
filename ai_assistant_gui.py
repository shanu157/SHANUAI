import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import speech_recognition as sr
import pyttsx3
import webbrowser
import subprocess
import datetime
import threading
import queue
import re
import json
import google.generativeai as genai
from difflib import get_close_matches

# ========== 1. CONFIGURATION (defaults) ==========
DEFAULT_WAKE_WORD = "jarvis"
DEFAULT_API_KEY = ""  # User must set this in GUI

# ========== 2. GLOBAL VARIABLES ==========
recognizer = sr.Recognizer()
microphone = sr.Microphone()
task_queue = queue.Queue()
assistant_running = True
wake_word = DEFAULT_WAKE_WORD
api_key = DEFAULT_API_KEY
model = None
engine = None

# Default command map
COMMANDS = {
    "open chrome": lambda: webbrowser.open("https://www.google.com"),
    "open calculator": lambda: subprocess.Popen("calc.exe" if os.name == "nt" else "gnome-calculator"),
    "open notepad": lambda: subprocess.Popen("notepad.exe" if os.name == "nt" else "gedit"),
    "search google": lambda query=None: webbrowser.open(f"https://www.google.com/search?q={query}") if query else None,
    "search youtube": lambda query=None: webbrowser.open(f"https://www.youtube.com/results?search_query={query}") if query else None,
    "what time is it": lambda: speak(f"The time is {datetime.datetime.now().strftime('%I:%M %p')}"),
    "what is the date today": lambda: speak(f"Today's date is {datetime.datetime.now().strftime('%B %d, %Y')}"),
}

# ========== 3. HELPER FUNCTIONS ==========
def speak(text):
    """Text-to-speech output"""
    if engine:
        engine.say(text)
        engine.runAndWait()

def log_message(area, msg):
    """Append message to the GUI log area"""
    area.insert(tk.END, f"{datetime.datetime.now().strftime('%H:%M:%S')} - {msg}\n")
    area.see(tk.END)

def init_tts():
    global engine
    engine = pyttsx3.init()
    engine.setProperty('rate', 180)
    engine.setProperty('volume', 0.9)

def init_ai():
    global model
    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        return True
    return False

def listen_for_wake_word(log_area):
    """Continuously listen for wake word (runs in thread)"""
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
    while assistant_running:
        try:
            with microphone as source:
                audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
            text = recognizer.recognize_google(audio).lower()
            if wake_word in text:
                log_message(log_area, f"Wake word detected: '{wake_word}'")
                return True
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            log_message(log_area, "Speech recognition service error")
        except sr.WaitTimeoutError:
            pass
    return False

def listen_for_command(log_area):
    """Listen for a single command"""
    try:
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        command = recognizer.recognize_google(audio).lower()
        log_message(log_area, f"Command: {command}")
        return command
    except sr.UnknownValueError:
        log_message(log_area, "Could not understand command")
        return None
    except sr.RequestError:
        log_message(log_area, "Speech recognition service error")
        return None
    except sr.WaitTimeoutError:
        return None

def parse_with_ai(command, log_area):
    """Use Gemini AI to parse intent"""
    if not model:
        log_message(log_area, "AI model not initialized. Set API key in Settings.")
        return None
    prompt = f"""
    Parse the following user command into intent and entities.
    Command: "{command}"
    Return JSON: {{"intent": "open_app|search_web|check_time|ask_question|other", "entities": {{"app_name": "", "query": "", "question": ""}} }}
    """
    try:
        response = model.generate_content(prompt)
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return None
    except Exception as e:
        log_message(log_area, f"AI parsing error: {e}")
        return None

def execute_action(intent_data, command_text, log_area):
    """Execute action based on parsed intent"""
    if not intent_data:
        # fallback: try direct command match
        matches = get_close_matches(command_text, COMMANDS.keys(), n=1, cutoff=0.6)
        if matches:
            COMMANDS[matches[0]]()
        elif model:
            response = model.generate_content(command_text).text
            speak(response[:200])
        else:
            speak("I don't understand that command.")
        return

    intent = intent_data.get("intent", "")
    entities = intent_data.get("entities", {})

    if intent == "open_app":
        app_name = entities.get("app_name", "")
        matches = get_close_matches(app_name, COMMANDS.keys(), n=1, cutoff=0.6)
        if matches:
            COMMANDS[matches[0]]()
        else:
            speak(f"Sorry, I don't know how to open {app_name}")
    elif intent == "search_web":
        query = entities.get("query", "")
        if query:
            COMMANDS["search google"](query)
        else:
            speak("What would you like to search for?")
    elif intent == "check_time":
        COMMANDS["what time is it"]()
    elif intent == "ask_question":
        question = entities.get("question", "")
        if question and model:
            answer = model.generate_content(question).text
            speak(answer[:200])
        else:
            speak("I didn't catch your question.")
    else:
        # fallback to AI chat
        if model:
            response = model.generate_content(command_text).text
            speak(response[:200])
        else:
            speak("Command not recognized.")

def worker(log_area):
    """Background thread that processes commands from queue"""
    while assistant_running:
        try:
            task = task_queue.get(timeout=0.5)
            if task is None:
                break
            command_text, intent_data = task
            execute_action(intent_data, command_text, log_area)
            task_queue.task_done()
        except queue.Empty:
            continue

def assistant_loop(log_area):
    """Main assistant loop running in a separate thread"""
    init_tts()
    speak("Hello, I am your AI assistant. Say '{}' to activate me.".format(wake_word))
    while assistant_running:
        if listen_for_wake_word(log_area):
            speak("Yes?")
            command = listen_for_command(log_area)
            if command:
                # Parse with AI (non-blocking, put in queue)
                intent = parse_with_ai(command, log_area)
                task_queue.put((command, intent))
            else:
                speak("Please say your command again.")

# ========== 4. GUI APPLICATION ==========
class AIAssistantGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Assistant - Voice Control with GUI")
        self.root.geometry("900x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Create notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Voice Control
        self.voice_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.voice_tab, text="🎤 Voice Control")
        self.setup_voice_tab()

        # Tab 2: Command Map
        self.cmd_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.cmd_tab, text="📋 Command Map")
        self.setup_command_tab()

        # Tab 3: Settings
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="⚙️ Settings")
        self.setup_settings_tab()

        # Tab 4: Task Queue
        self.queue_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.queue_tab, text="📌 Task Queue")
        self.setup_queue_tab()

        # Start assistant threads
        self.assistant_thread = None
        self.worker_thread = None
        self.start_assistant()

        # Periodically update task queue display
        self.update_queue_display()

    def setup_voice_tab(self):
        # Log area
        self.log_area = scrolledtext.ScrolledText(self.voice_tab, wrap=tk.WORD, height=20)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Control buttons frame
        btn_frame = ttk.Frame(self.voice_tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Test Microphone", command=self.test_microphone).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Stop Assistant", command=self.stop_assistant).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Start Assistant", command=self.start_assistant).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear Log", command=lambda: self.log_area.delete(1.0, tk.END)).pack(side=tk.LEFT, padx=5)

    def setup_command_tab(self):
        # Treeview for commands
        columns = ("Command Phrase", "Action Description")
        self.tree = ttk.Treeview(self.cmd_tab, columns=columns, show="headings")
        self.tree.heading("Command Phrase", text="Command Phrase")
        self.tree.heading("Action Description", text="Action Description")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add/remove commands frame
        frame = ttk.Frame(self.cmd_tab)
        frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(frame, text="New Phrase:").grid(row=0, column=0, padx=5)
        self.new_phrase = ttk.Entry(frame, width=20)
        self.new_phrase.grid(row=0, column=1, padx=5)

        ttk.Label(frame, text="Action (Python code):").grid(row=0, column=2, padx=5)
        self.new_action = ttk.Entry(frame, width=40)
        self.new_action.grid(row=0, column=3, padx=5)

        ttk.Button(frame, text="Add Command", command=self.add_command).grid(row=0, column=4, padx=5)
        ttk.Button(frame, text="Remove Selected", command=self.remove_command).grid(row=0, column=5, padx=5)

        self.refresh_command_list()

    def setup_settings_tab(self):
        frame = ttk.Frame(self.settings_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Wake Word:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.wake_word_var = tk.StringVar(value=wake_word)
        ttk.Entry(frame, textvariable=self.wake_word_var, width=20).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Google Gemini API Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar(value=api_key)
        ttk.Entry(frame, textvariable=self.api_key_var, width=50, show="*").grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Voice Rate (words/min):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.rate_var = tk.IntVar(value=180)
        ttk.Scale(frame, from_=100, to=300, variable=self.rate_var, orient=tk.HORIZONTAL).grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Label(frame, textvariable=self.rate_var).grid(row=2, column=2, padx=5)

        ttk.Button(frame, text="Save Settings", command=self.save_settings).grid(row=3, column=0, columnspan=2, pady=20)

        # Info label
        info = "Note: Changing settings requires restarting the assistant (Stop then Start)."
        ttk.Label(frame, text=info, foreground="gray").grid(row=4, column=0, columnspan=3, pady=10)

    def setup_queue_tab(self):
        self.queue_listbox = tk.Listbox(self.queue_tab, height=15)
        self.queue_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Label(self.queue_tab, text="Pending tasks (commands waiting to be processed)").pack()

    # ----- Command Map Methods -----
    def refresh_command_list(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for cmd in COMMANDS.keys():
            self.tree.insert("", tk.END, values=(cmd, "Custom action"))

    def add_command(self):
        phrase = self.new_phrase.get().strip().lower()
        action_code = self.new_action.get().strip()
        if not phrase or not action_code:
            messagebox.showerror("Error", "Both phrase and action code are required.")
            return
        try:
            # Compile the action code into a lambda
            # WARNING: eval is dangerous; this is for demonstration. Use with trusted input only.
            action = eval(f"lambda: {action_code}")
            COMMANDS[phrase] = action
            self.refresh_command_list()
            self.new_phrase.delete(0, tk.END)
            self.new_action.delete(0, tk.END)
            log_message(self.log_area, f"Added command: '{phrase}'")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid action code: {e}")

    def remove_command(self):
        selected = self.tree.selection()
        if not selected:
            return
        phrase = self.tree.item(selected[0])['values'][0]
        if phrase in COMMANDS:
            del COMMANDS[phrase]
            self.refresh_command_list()
            log_message(self.log_area, f"Removed command: '{phrase}'")

    # ----- Settings -----
    def save_settings(self):
        global wake_word, api_key, model
        wake_word = self.wake_word_var.get().strip().lower()
        api_key = self.api_key_var.get().strip()
        # Update TTS rate
        if engine:
            engine.setProperty('rate', self.rate_var.get())
        # Re-initialize AI
        if api_key:
            success = init_ai()
            if success:
                log_message(self.log_area, "AI model initialized with new API key.")
            else:
                log_message(self.log_area, "Failed to initialize AI. Check API key.")
        else:
            model = None
        messagebox.showinfo("Settings", "Settings saved. Restart assistant to apply wake word change.")

    # ----- Assistant Control -----
    def start_assistant(self):
        global assistant_running, model
        if hasattr(self, 'assistant_thread') and self.assistant_thread and self.assistant_thread.is_alive():
            log_message(self.log_area, "Assistant already running.")
            return
        assistant_running = True
        # Re-init AI if API key changed
        if api_key:
            init_ai()
        else:
            model = None
        # Start threads
        self.assistant_thread = threading.Thread(target=assistant_loop, args=(self.log_area,), daemon=True)
        self.worker_thread = threading.Thread(target=worker, args=(self.log_area,), daemon=True)
        self.assistant_thread.start()
        self.worker_thread.start()
        log_message(self.log_area, f"Assistant started. Wake word: '{wake_word}'")

    def stop_assistant(self):
        global assistant_running
        assistant_running = False
        # Clear queue and add poison pill
        while not task_queue.empty():
            try:
                task_queue.get_nowait()
                task_queue.task_done()
            except queue.Empty:
                break
        task_queue.put(None)  # Signal worker to exit
        log_message(self.log_area, "Assistant stopped.")

    def test_microphone(self):
        try:
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                log_message(self.log_area, "Testing microphone... say something")
                audio = recognizer.listen(source, timeout=3)
                text = recognizer.recognize_google(audio)
                log_message(self.log_area, f"Microphone works! You said: {text}")
        except Exception as e:
            log_message(self.log_area, f"Microphone test failed: {e}")

    def update_queue_display(self):
        """Refresh task queue listbox every second"""
        self.queue_listbox.delete(0, tk.END)
        # Show pending tasks (approximate, since queue items are tuples)
        pending = list(task_queue.queue)
        for item in pending:
            if isinstance(item, tuple) and len(item) >= 1:
                self.queue_listbox.insert(tk.END, f"Command: {item[0][:50]}")
        self.root.after(1000, self.update_queue_display)

    def on_closing(self):
        self.stop_assistant()
        self.root.destroy()

# ========== 5. MAIN ENTRY POINT ==========
if __name__ == "__main__":
    import os
    root = tk.Tk()
    app = AIAssistantGUI(root)
    root.mainloop()