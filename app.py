import json
import os
import subprocess
import time
import logging
from flask import Flask, render_template, jsonify, send_file, request, Response

# Suppress Werkzeug request logs (GET /status 200 etc)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# File paths
STATE_FILE = "bot_state.json"
LOG_FILE = "bot_logs.json"

# Global reference to worker process and latest frame
worker_process = None
latest_frame = None

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"command": "idle", "status": "idle"}

def save_command(command):
    state = load_state()
    state["command"] = command
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def load_logs():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"logs": [], "stats": {"disputed_month": 0, "total_disputed": 0, "disputed_session": 0, "errors": 0}}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_bot():
    global worker_process
    
    # Check if already running
    state = load_state()
    if state.get("status") in ["running", "processing", "waiting_for_login"]:
        return jsonify({"status": "already_running"})

    # Reset files - BUT KEEP HISTORY
    if os.path.exists(STATE_FILE): os.remove(STATE_FILE)
    
    # Clear logs and invoices for new session
    logs_data = {"logs": [], "stats": {"disputed": 0, "skipped": 0, "errors": 0, "invoices_processed": 0, "total_invoices": 0}, "invoices": []}
    with open(LOG_FILE, 'w') as f:
        json.dump(logs_data, f)
    
    # Start worker
    # We use Popen to start it as a separate independent process
    worker_process = subprocess.Popen(
        ["python", "browser_worker.py"],
        shell=True
    )
    
    # Give it a moment to initialize
    time.sleep(2)
    
    # Send start command immediately (worker waits for it after login, or we can let it wait)
    # Actually, the worker waits for "start" command after login. 
    # But for auto-login, we might want to send "start" automatically?
    # The user wants "one button". 
    # So we should probably write "start" to the state file after a delay or let the worker handle it.
    # In browser_worker.py, it waits for "start" command after login.
    # So we should write "start" to the state file.
    
    save_command("start")
    
    return jsonify({"status": "started"})

@app.route('/stop', methods=['POST'])
def stop_bot():
    save_command("stop")
    return jsonify({"status": "stopping"})

@app.route('/status')
def get_status():
    state = load_state()
    logs_data = load_logs()
    
    # Load persistent history
    stats_file = "stats.json"
    stats = {}
    if os.path.exists(stats_file):
        try:
            with open(stats_file, 'r') as f:
                stats = json.load(f)
        except:
            pass
            
    # Calculate stats
    current_month = time.strftime("%Y-%m")
    monthly_disputes = stats.get("monthly_disputes", {}).get(current_month, 0)
    total_disputes = stats.get("total_disputes", 0)
    
    # Session disputes (from current log file)
    # Note: browser_worker updates persistent stats when it updates session stats
    session_disputes = logs_data.get("stats", {}).get("disputed", 0)
    
    # Construct response
    response_stats = {
        "disputed_month": monthly_disputes,
        "total_disputed": total_disputes,
        "disputed_session": session_disputes,
        "errors": logs_data.get("stats", {}).get("errors", 0),
        "skipped": logs_data.get("stats", {}).get("skipped", 0)
    }
    
    return jsonify({
        "status": state.get("status", "idle"),
        "logs": logs_data.get("logs", []),
        "invoices": logs_data.get("invoices", []),
        "stats": response_stats
    })

@app.route('/update_frame', methods=['POST'])
def update_frame():
    global latest_frame
    latest_frame = request.data
    # print(f"Received frame: {len(latest_frame)} bytes") 
    return "ok"

def generate_frames():
    global latest_frame
    
    # Try to load a placeholder if no frame yet
    if latest_frame is None and os.path.exists("static/latest_view.png"):
        try:
            with open("static/latest_view.png", "rb") as f:
                latest_frame = f.read()
        except:
            pass

    while True:
        if latest_frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + latest_frame + b'\r\n')
        else:
            # If we still have nothing, just wait
            pass
            
        time.sleep(0.05)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/screenshot')
def get_screenshot():
    # Fallback for static image if needed
    if latest_frame:
         return Response(latest_frame, mimetype='image/jpeg')
    else:
        return "", 404

@app.route('/click', methods=['POST'])
def handle_click():
    data = request.json
    x = data.get('x')
    y = data.get('y')
    
    # Save the click command to the state so the worker can pick it up
    # Note: This is a simplified way. For real-time control, we'd need a more direct channel (e.g. socket)
    # But since the worker checks state frequently, we can write a "pending_click"
    
    # Since the worker is busy in a loop, we need a way to interrupt it or have it check often.
    # For now, we'll append to a click_queue.json file that the worker checks.
    
    try:
        with open("click_queue.json", "a") as f:
            f.write(json.dumps({"x": x, "y": y, "time": time.time()}) + "\n")
    except:
        pass
        
    return jsonify({"status": "clicked"})

if __name__ == '__main__':
    # Ensure static folder exists
    if not os.path.exists('static'):
        os.makedirs('static')
    
    # Reset state on startup to avoid "already running" ghost state
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except:
            pass

    # Clear logs on startup for fresh dashboard
    if os.path.exists(LOG_FILE):
        try:
            os.remove(LOG_FILE)
        except:
            pass
    
    # Create a clean idle state
    save_command("idle")
        
    print("Starting Flask server on http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=False)
