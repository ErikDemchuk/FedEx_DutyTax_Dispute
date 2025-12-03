import streamlit as st
import time
import subprocess
import json
import pandas as pd
from datetime import datetime
import os

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="FedEx Dispute Bot",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CLEAN THEME CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    :root {
        --background: #F7F7F4;
        --foreground: #26251E;
        --card: #FFFFFF;
        --primary: #d97757;
        --primary-foreground: #FFFFFF;
        --secondary: #E6E4DD;
        --muted-foreground: #8C8980;
        --border: #E6E4DD;
        --status-green: #519964;
        --status-red: #D95252;
        --radius: 0.5rem;
    }

    .stApp {
        background-color: var(--background);
        color: var(--foreground);
        font-family: 'Inter', sans-serif;
        font-size: 13px;
    }

    .stButton>button {
        background-color: #FFFFFF;
        color: var(--foreground);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        font-size: 14px;
        font-weight: 500;
        padding: 0.6rem 1.2rem;
        box-shadow: none !important;
        transition: all 0.1s;
    }
    .stButton>button:hover {
        background-color: var(--secondary);
        border-color: #d1d1d1;
    }

    button[kind="primary"] {
        background-color: var(--primary) !important;
        color: var(--primary-foreground) !important;
        border: 1px solid var(--primary) !important;
    }
    button[kind="primary"]:hover {
        background-color: #c66a4b !important;
        border-color: #c66a4b !important;
    }

    div[data-testid="stMetric"] {
        background-color: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 20px;
        box-shadow: none;
    }
    label[data-testid="stMetricLabel"] {
        font-size: 12px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--muted-foreground);
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 600;
        color: var(--foreground);
    }

    .stTextArea textarea {
        background-color: #1a1a2e !important;
        border: 1px solid #2d2d44 !important;
        color: #e0e0e0 !important;
        border-radius: var(--radius);
        font-family: 'Consolas', 'Monaco', monospace !important;
        font-size: 12px !important;
        line-height: 1.5 !important;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: var(--radius);
        background-color: #FFFFFF;
    }
    
    .status-badge {
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .status-running { background: #dcfce7; color: #166534; }
    .status-waiting { background: #fef3c7; color: #92400e; }
    .status-stopped { background: #fee2e2; color: #991b1b; }
    .status-idle { background: #f3f4f6; color: #6b7280; }
    .status-completed { background: #dbeafe; color: #1e40af; }

    hr {
        border-color: var(--border);
        margin: 1.5rem 0;
    }
    
    h1 {
        font-weight: 600 !important;
        font-size: 1.8rem !important;
    }
    
    </style>
""", unsafe_allow_html=True)

# --- FILE PATHS ---
STATE_FILE = "bot_state.json"
LOG_FILE = "bot_logs.json"

# --- HELPER FUNCTIONS ---
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
    return {"logs": [], "stats": {"disputed": 0, "skipped": 0, "errors": 0, "invoices_processed": 0, "total_invoices": 0}, "invoices": []}

def reset_files():
    for f in [STATE_FILE, LOG_FILE]:
        if os.path.exists(f):
            os.remove(f)

# --- SESSION STATE ---
if 'worker_process' not in st.session_state:
    st.session_state.worker_process = None

# --- LOAD CURRENT STATE ---
state = load_state()
logs_data = load_logs()
current_status = state.get("status", "idle")
stats = logs_data.get("stats", {})
logs = logs_data.get("logs", [])
invoices = logs_data.get("invoices", [])

# --- HEADER ---
st.markdown("# 📦 FedEx Dispute Bot")

# Status Badge
status_class = "status-idle"
status_text = current_status.upper().replace("_", " ")
if current_status in ["running", "processing"]: 
    status_class = "status-running"
elif current_status == "waiting_for_login": 
    status_class = "status-waiting"
    status_text = "WAITING FOR LOGIN"
elif current_status == "completed": 
    status_class = "status-completed"
elif current_status in ["stopped", "error"]: 
    status_class = "status-stopped"

st.markdown(f'<span class="status-badge {status_class}">{status_text}</span>', unsafe_allow_html=True)

st.markdown("---")

# --- STATS ROW ---
s1, s2, s3, s4 = st.columns(4)
with s1:
    st.metric("Disputed", stats.get("disputed", 0))
with s2:
    st.metric("Skipped", stats.get("skipped", 0))
with s3:
    st.metric("Total", stats.get("total_invoices", 0))
with s4:
    st.metric("Errors", stats.get("errors", 0))

# Progress Bar
progress = 0
total = stats.get("total_invoices", 0)
processed = stats.get("invoices_processed", 0)
if total > 0:
    progress = processed / total
    st.progress(progress)
    st.caption(f"Processing: {processed} / {total} invoices")

st.markdown("---")

# --- CONTROL BUTTONS ---
col1, col2, col3 = st.columns([2, 2, 4])

with col1:
    if current_status == "idle" and st.session_state.worker_process is None:
        if st.button("🚀 Launch Browser", type="primary", use_container_width=True):
            # Clean up old state files first
            reset_files()
            # Start the browser worker process in a new window
            st.session_state.worker_process = subprocess.Popen(
                ["cmd", "/c", "start", "cmd", "/k", "python", "browser_worker.py"],
                shell=True
            )
            time.sleep(2)
            st.rerun()

with col2:
    if current_status == "waiting_for_login":
        if st.button("▶️ Start Processing", type="primary", use_container_width=True):
            save_command("start")
            st.rerun()

with col3:
    if current_status in ["running", "processing", "waiting_for_login"]:
        if st.button("⏹️ Stop Bot", use_container_width=True):
            save_command("stop")
            st.session_state.worker_process = None
            st.rerun()
    
    if current_status in ["completed", "stopped"]:
        if st.button("🔄 Reset", use_container_width=True):
            reset_files()
            st.session_state.worker_process = None
            st.rerun()

# --- INSTRUCTIONS ---
if current_status == "idle" and st.session_state.worker_process is None:
    st.info("""
    **How to use:**
    1. Click **Launch Browser** - a Chrome window will open
    2. **Log in to FedEx** in that browser window
    3. Come back here and click **Start Processing**
    4. The bot will automatically process all Duty/Tax invoices
    """)

if current_status == "waiting_for_login":
    st.warning("⏳ **Waiting for you to log in to FedEx in the browser window.** Once logged in, click **Start Processing** above.")

st.markdown("---")

# --- MAIN CONTENT ---
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### 📋 Invoices Found")
    if invoices:
        df = pd.DataFrame(invoices)
        duty_count = len([i for i in invoices if i.get("type") == "Duty/Tax"])
        transport_count = len([i for i in invoices if i.get("type") == "Transportation"])
        disputed_count = len([i for i in invoices if i.get("type") == "Disputed"])
        
        st.markdown(f"**{duty_count}** Duty/Tax • **{transport_count}** Transportation • **{disputed_count}** Already Disputed")
        
        st.dataframe(
            df[["invoice", "type"]],
            column_config={
                "invoice": st.column_config.TextColumn("Invoice #", width="medium"),
                "type": st.column_config.TextColumn("Type", width="medium")
            },
            use_container_width=True,
            hide_index=True,
            height=400
        )
    else:
        st.caption("No invoices scanned yet. Start the bot to scan.")

with col_right:
    st.markdown("### 📜 Activity Log")
    log_text = "\n".join(logs) if logs else "Waiting for bot to start..."
    st.text_area("", value=log_text, height=450, key="log_area", label_visibility="collapsed")

# --- AUTO REFRESH ---
if current_status not in ["idle", "completed", "stopped"] or (st.session_state.worker_process is not None and current_status != "completed"):
    time.sleep(1.5)
    st.rerun()
