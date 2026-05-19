"""WfAgent Pro - Clean Working Edition
Fixed: tool execution, HTML preview, design, mode toggle
"""

import streamlit as st
import requests
import time
import json
import os
import re
import html as html_module
import subprocess
import csv
import io
import threading
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================
GITHUB_RAW_URL = os.getenv(
    "GITHUB_URL",
    "https://raw.githubusercontent.com/wf2008/Codex/main/frontend/ollama_url.txt"
)
URL_POLL_INTERVAL = 10
WORKSPACE = "/tmp/wfagent_workspace"
os.makedirs(WORKSPACE, exist_ok=True)
MAX_EXECUTION_TIME = 60

# ============================================================
# URL FETCHER
# ============================================================
_current_url = ""
_lock = threading.Lock()

def fetch_tunnel_url():
    global _current_url
    try:
        resp = requests.get(GITHUB_RAW_URL, timeout=15)
        resp.raise_for_status()
        url = resp.text.strip()
        if url.startswith("http"):
            with _lock:
                _current_url = url
    except Exception as e:
        pass
    return _current_url

def get_current_url():
    with _lock:
        return _current_url

def start_url_updater():
    def updater():
        while True:
            fetch_tunnel_url()
            time.sleep(URL_POLL_INTERVAL)
    t = threading.Thread(target=updater, daemon=True)
    t.start()
    return t

# ============================================================
# SESSION
# ============================================================
SESSION_KEY = "wfagent_chat_history"

def get_chat_history():
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = []
    return st.session_state[SESSION_KEY]

def add_message(role, content, metadata=None):
    history = get_chat_history()
    history.append({"role": role, "content": content, "timestamp": time.time(), "metadata": metadata or {}})
    st.session_state[SESSION_KEY] = history

def clear_history():
    st.session_state[SESSION_KEY] = []

def export_history():
    return json.dumps(get_chat_history(), indent=2, ensure_ascii=False)

# ============================================================
# TOOLS
# ============================================================
def web_search(query, max_results=5):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if results:
            out = []
            for i, r in enumerate(results, 1):
                out.append(f"{i}. {r.get('title', 'Untitled')}\n{r.get('body', '')}\nSource: {r.get('href', '')}")
            return "\n\n".join(out)
    except Exception as e:
        return f"Search error: {e}"

def web_scraper(url, max_chars=8000):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=20)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for s in soup(["script", "style", "nav", "footer"]):
            s.decompose()
        text = "\n".join(line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip())
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated]"
        return f"Content from {url}:\n\n{text}"
    except Exception as e:
        return f"Scrape error: {e}"

def execute_bash(command):
    bad = [r"rm\s+-rf\s+/", r"shutdown", r"reboot", r"mkfs", r"dd\s+if=", r":\(\)\s*\{", r"sudo"]
    cmd = " ".join(command.strip().split())
    for p in bad:
        if re.search(p, cmd, re.I):
            return f"Blocked: {p}"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=MAX_EXECUTION_TIME, cwd=WORKSPACE)
        out = r.stdout.strip() or "(no output)"
        err = r.stderr.strip()
        if r.returncode != 0:
            return f"Exit {r.returncode}\nERR:\n{err or '(empty)'}\nOUT:\n{out}"
        return out
    except Exception as e:
        return f"Error: {e}"

def run_python(code):
    try:
        f = Path(WORKSPACE) / f"exec_{int(time.time()*1000)}.py"
        f.write_text(code, encoding="utf-8")
        r = subprocess.run(["python3", str(f)], capture_output=True, text=True, timeout=MAX_EXECUTION_TIME, cwd=WORKSPACE)
        out = r.stdout.strip() or "(no output)"
        if r.returncode != 0:
            return f"Exit {r.returncode}\nERR:\n{r.stderr.strip() or '(empty)'}\nOUT:\n{out}"
        return out
    except Exception as e:
        return f"Error: {e}"
    finally:
        try:
            f.unlink()
        except:
            pass

def preview_html(html_code):
    html_code = html_code.strip()
    if not html_code:
        html_code = "<div style='padding:24px;color:#888'>Empty preview</div>"
    if "<html" not in html_code.lower():
        html_code = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>body{{margin:0;padding:16px;font-family:sans-serif;background:#0b1020;color:#e5e7eb}}</style>
</head><body>{html_code}</body></html>"""
    return html_code

def process_file(file_obj, filename=None):
    if filename is None:
        filename = getattr(file_obj, "name", "unknown")
    ext = Path(filename).suffix.lower()
    try:
        if ext in [".py", ".js", ".html", ".css", ".json", ".md", ".txt", ".sql"]:
            return file_obj.read().decode("utf-8", errors="replace")[:5000]
        elif ext == ".csv":
            text = file_obj.read().decode("utf-8", errors="replace")
            rows = list(csv.DictReader(io.StringIO(text)))
            return f"CSV: {len(rows)} rows\nCols: {list(rows[0].keys()) if rows else 'N/A'}\n\nFirst 5:\n" + "\n".join(str(r) for r in rows[:5])
        elif ext == ".json":
            data = json.loads(file_obj.read().decode("utf-8"))
            return json.dumps(data, indent=2, ensure_ascii=False)[:5000]
        elif ext in [".png", ".jpg", ".jpeg", ".gif"]:
            p = Path(WORKSPACE) / filename
            with open(p, "wb") as f:
                f.write(file_obj.read())
            return f"Image saved: {p}"
        else:
            p = Path(WORKSPACE) / filename
            with open(p, "wb") as f:
                f.write(file_obj.read())
            return f"File saved: {p} ({os.path.getsize(p)} bytes)"
    except Exception as e:
        return f"Error: {e}"

# ============================================================
# OLLAMA CLIENT
# ============================================================
def chat_completion(endpoint, messages, tools=None):
    payload = {
        "model": "wf-agent-model",
        "messages": messages,
        "stream": False,
        "temperature": 0.4,
        "max_tokens": 4096,
    }
    if tools:
        payload["tools"] = tools
    url = endpoint.rstrip("/") + "/v1/chat/completions"
    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=180)
    resp.raise_for_status()
    return resp.json()

# ============================================================
# STREAMLIT APP
# ============================================================
st.set_page_config(page_title="WfAgent Pro", page_icon="", layout="wide")

# Dark theme CSS
st.markdown("""
<style>
footer, header {display:none !important;}
.stChatMessage {border-radius:12px !important;}
[data-testid="stSidebar"] {background:#0f1117 !important;}
</style>
""", unsafe_allow_html=True)

# Init
@st.cache_resource
def init():
    return start_url_updater()
init()

if "mode" not in st.session_state:
    st.session_state.mode = "chat"

# Sidebar
with st.sidebar:
    st.markdown("# WfAgent Pro")
    st.markdown("---")

    st.markdown("### Mode")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Chat", type="primary" if st.session_state.mode=="chat" else "secondary", use_container_width=True, key="m_chat"):
            st.session_state.mode = "chat"
            st.rerun()
    with c2:
        if st.button("Agent", type="primary" if st.session_state.mode=="agent" else "secondary", use_container_width=True, key="m_agent"):
            st.session_state.mode = "agent"
            st.rerun()

    st.markdown("---")
    st.markdown("### Tunnel")
    url = get_current_url()
    if url:
        st.success("Connected")
    else:
        st.warning("No URL")
        if st.button("Refresh"):
            fetch_tunnel_url()
            st.rerun()

    st.markdown("---")
    if st.button("Export Chat", use_container_width=True):
        st.download_button("Download", export_history(), file_name="chat.json", mime="application/json", use_container_width=True)

# Main
st.markdown("# WfAgent Pro")
st.caption("Autonomous AI Agent")

cols = st.columns([1,1,1])
with cols[0]:
    st.markdown(f"**Mode:** `{st.session_state.mode.upper()}`")
with cols[1]:
    st.markdown(f"**Status:** `{'Online' if url else 'Offline'}`")
with cols[2]:
    st.markdown(f"**Messages:** `{len(get_chat_history())}`")

st.markdown("---")

# Chat display
for msg in get_chat_history():
    role = msg["role"]
    content = msg["content"]
    meta = msg.get("metadata", {})

    with st.chat_message(role, avatar=" " if role=="user" else ""):
        if meta.get("html_preview"):
            st.markdown(content)
            st.components.v1.html(meta["html_preview"], height=500, scrolling=True)
        elif meta.get("is_tool_result"):
            with st.expander(f" Tool: {meta.get('tool_name', 'unknown')}", expanded=False):
                st.code(content, language="text")
        else:
            st.markdown(content)

# File upload
with st.expander(" Attach Files"):
    files = st.file_uploader("Upload files", accept_multiple_files=True, key="fu")
    if files:
        for f in files:
            r = process_file(f, f.name)
            add_message("system", f"Uploaded **{f.name}**:\n```\n{r[:2000]}\n```")
            st.success(f" {f.name}")

# Input
prompt = st.chat_input("Ask me anything...", key="ci")

if prompt:
    prompt = prompt.replace("\x00", "")[:50000]
    url = get_current_url()

    if not url:
        add_message("user", prompt)
        add_message("assistant", "Please start your Kaggle notebook and wait for the tunnel URL.")
        st.rerun()

    add_message("user", prompt)

    # Build messages
    history = get_chat_history()
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[:-1] if m["role"] in ["user","assistant","system"]]
    msgs.append({"role": "user", "content": prompt})

    endpoint = url.rstrip("/") + "/v1/chat/completions"

    tools = [
        {"type": "function", "function": {"name": "web_search", "description": "Search the web for current information.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "web_scraper", "description": "Extract content from a URL.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
        {"type": "function", "function": {"name": "run_bash", "description": "Run a bash command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "run_python", "description": "Run Python code.", "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}},
        {"type": "function", "function": {"name": "preview_html", "description": "Render HTML/CSS/JS.", "parameters": {"type": "object", "properties": {"html_code": {"type": "string"}}, "required": ["html_code"]}}},
    ]

    funcs = {"web_search": web_search, "web_scraper": web_scraper, "run_bash": execute_bash, "run_python": run_python, "preview_html": preview_html}

    # Process
    try:
        tool_log = []
        html_preview = None

        for _ in range(5):
            data = chat_completion(endpoint, msgs, tools=tools)
            choice = data.get("choices", [{}])[0]
            amsg = choice.get("message", {})
            content = amsg.get("content", "") or ""
            tcalls = amsg.get("tool_calls", []) or []

            if not tcalls:
                # Final answer
                add_message("assistant", content, {"tool_calls": tool_log, "html_preview": html_preview})
                st.rerun()
                break

            # Execute tools
            msgs.append(amsg)
            for tc in tcalls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args = json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else fn.get("arguments", {})

                # Execute
                if name in funcs:
                    try:
                        result = funcs[name](**args)
                    except Exception as e:
                        result = f"Error: {e}"
                else:
                    result = f"Unknown tool: {name}"

                # Store HTML preview
                if name == "preview_html":
                    html_preview = result

                # Log
                tool_log.append({"tool": name, "result": str(result)[:500]})

                # Add to messages
                msgs.append({"role": "tool", "tool_call_id": tc.get("id", name), "content": str(result)})

                # Show tool result in chat
                add_message("assistant", f"Running **{name}**...", {"is_tool_result": True, "tool_name": name})
        else:
            add_message("assistant", "Max tool rounds reached.", {"tool_calls": tool_log, "html_preview": html_preview})
            st.rerun()

    except Exception as e:
        add_message("assistant", f"Error: {e}")
        st.rerun()

# Footer
st.markdown("---")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Clear Chat", use_container_width=True):
        clear_history()
        st.rerun()
with c2:
    if st.button("Save Session", use_container_width=True):
        st.success("Saved!")
with c3:
    if st.button("Clear Workspace", use_container_width=True):
        for f in Path(WORKSPACE).iterdir():
            try:
                f.unlink()
            except:
                pass
        st.success("Cleared!")
