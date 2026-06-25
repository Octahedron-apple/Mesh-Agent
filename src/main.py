import json
import os
import shutil
import subprocess
import sys
import threading
import pty
import select
import fcntl
import termios
import struct
import time

from flask import Flask, jsonify, render_template, request, send_file
from flask_socketio import SocketIO, emit

sys.path.insert(0, "/app")

try:
    from LineRun.linerun.main import Code_Runner
except ImportError:

    class Code_Runner:
        def __init__(self, Path, Venv_Path):
            self.Path = Path
            self.Venv_Path = Venv_Path
            self.Commit_Hashes = []

        def Add_Module(self, package):
            return f"Mock installed {package}"

        def Commit(self, msg):
            import hashlib

            h = hashlib.sha1(msg.encode()).hexdigest()[:7]
            self.Commit_Hashes.append({"hash": h, "message": msg})

        def Reset(self, h):
            return f"Mock reset to {h}"


from agent import AI_Agent

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "mesh-agent-secret")

# Use threading mode — safe with our existing background agent thread and
# requires no extra dependencies (no eventlet/gevent needed).
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

WORKSPACE_DIR = "/app/agent_workspace"
AGENT_VENV = "/app/agent_venv"

if os.path.exists(WORKSPACE_DIR):
    shutil.rmtree(WORKSPACE_DIR)
os.makedirs(WORKSPACE_DIR, exist_ok=True)

runner = Code_Runner(Path=WORKSPACE_DIR, Venv_Path=AGENT_VENV)
agent = AI_Agent(Runner=runner)

# ---------------------------------------------------------------------------
# PTY Terminal manager
# ---------------------------------------------------------------------------
terminal_fd = None
terminal_child = None

def set_pty_size(fd, rows, cols):
    size = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, size)

def start_persistent_terminal():
    global terminal_fd, terminal_child
    if terminal_child is not None and terminal_child.poll() is None:
        return
        
    master_fd, slave_fd = pty.openpty()
    
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    
    terminal_child = subprocess.Popen(
        ["bash"],
        preexec_fn=os.setsid,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=WORKSPACE_DIR,
        env=env
    )
    
    os.close(slave_fd)
    terminal_fd = master_fd
    
    # Default window size
    try:
        set_pty_size(terminal_fd, 24, 80)
    except Exception:
        pass
        
    threading.Thread(target=read_terminal_output, daemon=True).start()

def read_terminal_output():
    global terminal_fd, terminal_child
    while True:
        if terminal_fd is None:
            time.sleep(0.1)
            continue
        try:
            r, w, x = select.select([terminal_fd], [], [], 1.0)
            if terminal_fd in r:
                data = os.read(terminal_fd, 1024)
                if not data:
                    break
                socketio.emit("terminal_output", {"output": data.decode("utf-8", errors="ignore")})
        except (IOError, OSError):
            break
        except Exception as e:
            print(f"[Terminal] Error: {e}")
            break
            
    print("[Terminal] Shell exited. Restarting in 1s...")
    terminal_fd = None
    terminal_child = None
    time.sleep(1)
    start_persistent_terminal()

start_persistent_terminal()


# ---------------------------------------------------------------------------
# SocketIO helpers
# ---------------------------------------------------------------------------

def _build_status_payload():
    return {
        "running": agent.Running,
        "thinking": agent.Is_Thinking,
        "configured": bool(agent.Api_Key and agent.Model),
        "pending_hitl": agent.Pending_Action is not None,
    }


def _build_messages_payload():
    return {"messages": agent.Messages}


def _build_hitl_payload():
    if agent.Pending_Action is not None:
        return {"pending": True, "action": agent.Pending_Action}
    return {"pending": False}


def _emit_state():
    """Push all current state to every connected client.
    Called from agent.On_State_Change (background thread) — use socketio.emit
    which is thread-safe.
    """
    socketio.emit("status_update", _build_status_payload())
    socketio.emit("messages_update", _build_messages_payload())
    socketio.emit("hitl_pending", _build_hitl_payload())


# Wire the agent callback so every state change triggers a push.
agent.On_State_Change = _emit_state


# ---------------------------------------------------------------------------
# Start agent event loop in a background thread
# ---------------------------------------------------------------------------

import asyncio


def start_agent_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    agent.Start(loop)
    loop.run_forever()


threading.Thread(target=start_agent_loop, daemon=True).start()


# ---------------------------------------------------------------------------
# SocketIO event handlers
# ---------------------------------------------------------------------------

@socketio.on("connect")
def on_connect():
    """Send full current state to a newly connected client immediately."""
    emit("status_update", _build_status_payload())
    emit("messages_update", _build_messages_payload())
    emit("hitl_pending", _build_hitl_payload())


@socketio.on("request_state")
def on_request_state():
    """Client can ask for a full state refresh at any time (e.g. on page focus)."""
    emit("status_update", _build_status_payload())
    emit("messages_update", _build_messages_payload())
    emit("hitl_pending", _build_hitl_payload())


@socketio.on("terminal_input")
def on_terminal_input(data):
    global terminal_fd
    input_str = data.get("input", "")
    if terminal_fd is not None and input_str:
        try:
            os.write(terminal_fd, input_str.encode("utf-8"))
        except Exception as e:
            print(f"[Terminal] Input error: {e}")


@socketio.on("terminal_connect")
def on_terminal_connect():
    global terminal_fd
    if terminal_fd is not None:
        try:
            # Send Ctrl-L to clear and redraw prompt
            os.write(terminal_fd, b"\x0c")
        except Exception:
            pass


@socketio.on("terminal_resize")
def on_terminal_resize(data):
    global terminal_fd
    rows = data.get("rows")
    cols = data.get("cols")
    if terminal_fd is not None and rows and cols:
        try:
            set_pty_size(terminal_fd, rows, cols)
        except Exception as e:
            print(f"[Terminal] Resize error: {e}")


# ---------------------------------------------------------------------------
# Theme helpers
# ---------------------------------------------------------------------------

def get_theme():
    try:
        with open(os.path.join(os.path.dirname(__file__), "theme.json"), "r") as f:
            return json.load(f).get("dark", False)
    except Exception:
        return False


@app.context_processor
def inject_theme():
    return dict(dark_mode=get_theme())


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/api/theme", methods=["POST"])
def update_theme():
    dark = request.json.get("dark", False)
    try:
        with open(os.path.join(os.path.dirname(__file__), "theme.json"), "w") as f:
            json.dump({"dark": dark}, f)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def chat_page():
    return render_template("chat.html")


@app.route("/terminal")
def terminal_page():
    return render_template("terminal.html")


@app.route("/config")
def config_page():
    return render_template("config.html")


@app.route("/workspace")
def workspace_page():
    return render_template("workspace.html")


# ---------------------------------------------------------------------------
# REST API routes (preserved — also serve as HTTP fallbacks)
# ---------------------------------------------------------------------------

@app.route("/api/config", methods=["GET", "POST"])
def config():
    if request.method == "GET":
        return jsonify({
            "api_key": agent.Api_Key,
            "model": agent.Model,
            "system_prompt": agent.System_Prompt
        })
    data = request.json
    api_key = data.get("api_key")
    model = data.get("model")
    system_prompt = data.get("system_prompt")
    if api_key and model:
        agent.Set_Config(api_key, model, system_prompt)
        return jsonify({"status": "ok"})
    return jsonify({"error": "Missing key or model"}), 400


@app.route("/api/prompt", methods=["POST"])
def prompt():
    data = request.json
    text = data.get("text")
    if text:
        agent.Add_User_Message(text)
        # Notify immediately so the user message appears before the agent responds.
        _emit_state()
        return jsonify({"status": "ok"})
    return jsonify({"error": "No text"}), 400


@app.route("/api/messages", methods=["GET"])
def messages():
    return jsonify(_build_messages_payload())


@app.route("/api/terminal", methods=["POST"])
def terminal():
    data = request.json
    cmd = data.get("command")
    if not cmd:
        return jsonify({"error": "No command provided"}), 400
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=WORKSPACE_DIR, capture_output=True, text=True
        )
        return jsonify({"output": result.stdout + result.stderr})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/install", methods=["POST"])
def install():
    data = request.json
    pkg = data.get("package")
    if not pkg:
        return jsonify({"error": "No package provided"}), 400
    try:
        res = runner.Add_Module(pkg)
        return jsonify({"result": str(res)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status", methods=["GET"])
def agent_status():
    return jsonify(_build_status_payload())


@app.route("/api/state", methods=["GET"])
def state():
    try:
        hashes = getattr(runner, "Commit_Hashes", [])
        return jsonify({"hashes": hashes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rollback", methods=["POST"])
def rollback():
    data = request.json
    h = data.get("hash")
    if not h:
        return jsonify({"error": "No hash provided"}), 400
    try:
        res = runner.Reset(h)
        return jsonify({"result": str(res)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/files", methods=["GET"])
def list_files():
    try:
        files = os.listdir(WORKSPACE_DIR)
        files = [f for f in files if not f.startswith(".")]
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download", methods=["GET"])
def download_workspace():
    import tempfile

    from flask import after_this_request

    zip_path = os.path.join(tempfile.gettempdir(), "workspace")
    shutil.make_archive(zip_path, "zip", WORKSPACE_DIR)

    @after_this_request
    def remove_file(response):
        try:
            os.remove(zip_path + ".zip")
        except Exception:
            pass
        return response

    return send_file(
        zip_path + ".zip", as_attachment=True, download_name="workspace.zip"
    )


@app.route("/api/download/<path:filename>", methods=["GET"])
def download_file(filename):
    from flask import send_from_directory
    try:
        return send_from_directory(WORKSPACE_DIR, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/hitl/pending", methods=["GET"])
def hitl_pending():
    return jsonify(_build_hitl_payload())


@app.route("/api/hitl/respond", methods=["POST"])
def hitl_respond():
    data = request.json
    approved = data.get("approved", False)
    reason = data.get("reason", "")

    agent.Hitl_Response = {"approved": approved, "reason": reason}

    if agent.Loop and agent.Hitl_Event:
        agent.Loop.call_soon_threadsafe(agent.Hitl_Event.set)

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
