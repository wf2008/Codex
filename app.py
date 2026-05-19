"""WfAgent Pro - Advanced AI Agent Interface for Render

Features:
- Chat Mode & Agent Mode toggle
- Multi-engine web search (DuckDuckGo + SearXNG)
- Sandboxed code execution (bash, python, playwright)
- File upload with smart processing
- Live HTML preview
- Web scraping
- Session management
- Code copy buttons
- Dark theme
"""

import streamlit as st
import time
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import WORKSPACE, MAX_AGENT_STEPS, AGENT_TIMEOUT
from core.url_fetcher import start_url_updater, get_current_url, fetch_tunnel_url
from core.ollama_client import chat_completion, stream_chat
from core.session_manager import (
    get_chat_history, add_message, clear_history, export_history,
    get_sessions, create_session, switch_session, delete_session,
    save_current_session, CURRENT_SESSION_KEY
)
from core.agent_engine import run_agent, run_parallel_agents, AgentTask
from tools.web_search import web_search
from tools.web_scraper import web_scraper
from tools.bash_executor import execute_bash
from tools.python_executor import run_python
from tools.playwright_runner import run_playwright_script
from tools.html_preview import preview_html
from tools.file_handler import process_uploaded_file, list_workspace_files, save_to_workspace
from tools.data_viz import auto_visualize
from utils.formatters import render_code_block, extract_code_blocks
from utils.security import sanitize_input
from utils.helpers import truncate_text, format_duration, generate_id

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="WfAgent Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load custom CSS
css_path = Path(__file__).parent / "assets" / "custom.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ============================================================
# INITIALIZATION
# ============================================================
@st.cache_resource
def init_url_fetcher():
    """Start background URL fetcher once"""
    return start_url_updater()

init_url_fetcher()

# Session state defaults
if "mode" not in st.session_state:
    st.session_state.mode = "chat"  # chat or agent
if "stop_flag" not in st.session_state:
    st.session_state.stop_flag = False
if "current_task" not in st.session_state:
    st.session_state.current_task = None
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("# 🤖 WfAgent Pro")
    st.markdown("---")

    # Mode Toggle
    st.markdown("### 🎛️ Mode")
    mode = st.segmented_control(
        "Select Mode",
        options=["💬 Chat", "🤖 Agent"],
        default="💬 Chat" if st.session_state.mode == "chat" else "🤖 Agent",
    )
    st.session_state.mode = "chat" if mode == "💬 Chat" else "agent"

    st.markdown("---")

    # URL Status
    st.markdown("### 🔗 Tunnel Status")
    current_url = get_current_url()
    if current_url:
        st.success(f"✅ Connected")
        st.caption(f"URL: {current_url[:50]}...")
    else:
        st.warning("⏳ Waiting for tunnel URL...")
        if st.button("🔄 Refresh URL"):
            fetch_tunnel_url()
            st.rerun()

    st.markdown("---")

    # Sessions
    st.markdown("### 📁 Sessions")
    sessions = get_sessions()
    if sessions:
        session_names = {sid: s.get("name", sid) for sid, s in sessions.items()}
        current = st.session_state.get(CURRENT_SESSION_KEY, "default")
        selected = st.selectbox(
            "Switch Session",
            options=list(session_names.keys()),
            format_func=lambda x: session_names.get(x, x),
            index=list(session_names.keys()).index(current) if current in session_names else 0,
        )
        if selected != current:
            save_current_session()
            switch_session(selected)
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ New", use_container_width=True):
            create_session(f"Session {len(sessions) + 1}")
            st.rerun()
    with col2:
        if st.button("🗑️ Delete", use_container_width=True):
            current = st.session_state.get(CURRENT_SESSION_KEY, "default")
            if current != "default" and current in sessions:
                delete_session(current)
                st.rerun()

    st.markdown("---")

    # Workspace
    st.markdown("### 📂 Workspace")
    files = list_workspace_files()
    if files:
        for f in files[:10]:
            st.caption(f"📄 {f}")
        if len(files) > 10:
            st.caption(f"... and {len(files) - 10} more")
    else:
        st.caption("Empty workspace")

    st.markdown("---")

    # Export/Import
    st.markdown("### 💾 Data")
    if st.button("📥 Export Chat", use_container_width=True):
        data = export_history()
        st.download_button(
            "Download JSON",
            data,
            file_name=f"chat_export_{generate_id()}.json",
            mime="application/json",
            use_container_width=True,
        )

    st.markdown("---")
    st.caption("v2.0.0 | Render Edition")

# ============================================================
# MAIN AREA
# ============================================================
# Header
st.markdown("# 🤖 WfAgent Pro")
st.caption("Autonomous AI Agent with Multi-Engine Search, Code Execution & Live Preview")

# Status bar
status_cols = st.columns([1, 1, 1, 1])
with status_cols[0]:
    if current_url:
        st.markdown("<span class='agent-badge completed'>🟢 Online</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='agent-badge planning'>🟡 Connecting...</span>", unsafe_allow_html=True)
with status_cols[1]:
    mode_badge = "💬 Chat" if st.session_state.mode == "chat" else "🤖 Agent"
    st.markdown(f"<span class='agent-badge executing'>{mode_badge}</span>", unsafe_allow_html=True)
with status_cols[2]:
    history = get_chat_history()
    st.markdown(f"<span class='agent-badge'>{len(history)} messages</span>", unsafe_allow_html=True)
with status_cols[3]:
    if st.session_state.current_task:
        st.markdown("<span class='agent-badge executing pulse'>⚡ Running...</span>", unsafe_allow_html=True)

st.markdown("---")

# ============================================================
# CHAT DISPLAY
# ============================================================
history = get_chat_history()

for msg in history:
    role = msg.get("role", "user")
    content = msg.get("content", "")
    metadata = msg.get("metadata", {})

    with st.chat_message(role, avatar="🧑" if role == "user" else "🤖"):
        # Render content
        if isinstance(content, str):
            # Check for HTML preview in metadata
            if metadata.get("html_preview"):
                st.markdown(content)
                st.components.v1.html(metadata["html_preview"], height=400)
            else:
                st.markdown(content)

            # Extract and render code blocks with copy buttons
            code_blocks = extract_code_blocks(content)
            for block in code_blocks:
                st.markdown(render_code_block(block["code"], block["language"]), unsafe_allow_html=True)
        else:
            st.write(content)

        # Show tool metadata
        if metadata.get("tool_calls"):
            with st.expander("🔧 Tool Calls", expanded=False):
                for tc in metadata["tool_calls"]:
                    st.json(tc)

        # Show execution time
        if metadata.get("execution_time"):
            st.caption(f"⏱️ {format_duration(metadata['execution_time'])}")

# ============================================================
# AGENT TASK DISPLAY
# ============================================================
if st.session_state.current_task and st.session_state.mode == "agent":
    task = st.session_state.current_task
    with st.status(f"🤖 Agent: {task.goal[:60]}...", expanded=True) as status:
        for i, step in enumerate(task.steps):
            icon = "⏳" if step.status == "pending" else "🔄" if step.status == "running" else "✅" if step.status == "completed" else "❌"
            st.markdown(f"{icon} **Step {i+1}**: {step.description} (`{step.status}`)")
            if step.result and step.status == "completed":
                with st.expander("Result", expanded=False):
                    st.text(truncate_text(str(step.result), 1000))
            if step.error:
                st.error(f"Error: {step.error}")

# ============================================================
# FILE UPLOAD AREA
# ============================================================
with st.expander("📎 Attach Files", expanded=False):
    uploaded = st.file_uploader(
        "Upload any file (code, data, images, documents)",
        accept_multiple_files=True,
        key="file_uploader",
    )
    if uploaded:
        for file in uploaded:
            if file.name not in [f.name for f in st.session_state.uploaded_files]:
                st.session_state.uploaded_files.append(file)
                result = process_uploaded_file(file, file.name)
                add_message("system", f"📎 File uploaded: {result}", {"file_name": file.name})
                st.success(f"✅ {file.name} processed")

    if st.session_state.uploaded_files:
        if st.button("🗑️ Clear All Files"):
            st.session_state.uploaded_files = []
            st.rerun()

# ============================================================
# INPUT AREA
# ============================================================
# Stop button
if st.session_state.current_task:
    if st.button("⏹️ Stop Agent", type="secondary", use_container_width=True):
        st.session_state.stop_flag = True
        st.session_state.current_task = None
        add_message("assistant", "⏹️ Agent stopped by user.")
        st.rerun()

# Chat input
prompt = st.chat_input(
    "Ask me to search, run code, build a website, or upload a file...",
    key="chat_input",
)

if prompt:
    prompt = sanitize_input(prompt)
    add_message("user", prompt)

    current_url = fetch_tunnel_url() or get_current_url()
    if not current_url:
        add_message(
            "assistant",
            "⏳ Waiting for the AI tunnel URL from your GitHub repo (`frontend/ollama_url.txt`). Please start your Kaggle notebook via GitHub Actions, then click Refresh URL in the sidebar.",
        )
        save_current_session()
        st.rerun()

    endpoint = current_url.rstrip("/")
    if endpoint.endswith("/v1/chat/completions"):
        endpoint = endpoint[: -len("/v1/chat/completions")]

    history = get_chat_history()
    api_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
        if msg.get("role") in ["user", "assistant", "system"]
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web using DuckDuckGo/SearXNG for fresh information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "web_scraper",
                "description": "Extract text content from a specific URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "max_chars": {"type": "integer", "default": 8000}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_bash_command",
                "description": "Execute a bash command in the sandboxed workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"}
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_python_code",
                "description": "Execute Python code in the sandboxed workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"}
                    },
                    "required": ["code"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_playwright_script",
                "description": "Run a Playwright browser automation script.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "script": {"type": "string"}
                    },
                    "required": ["script"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "preview_html",
                "description": "Render HTML/CSS/JS in the live preview panel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "html_code": {"type": "string"}
                    },
                    "required": ["html_code"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "auto_visualize",
                "description": "Generate Plotly visualization code from CSV/JSON data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_text": {"type": "string"},
                        "chart_type": {"type": "string", "default": "auto"}
                    },
                    "required": ["data_text"]
                }
            }
        },
    ]

    available_functions = {
        "web_search": web_search,
        "web_scraper": web_scraper,
        "run_bash_command": execute_bash,
        "run_python_code": run_python,
        "run_playwright_script": run_playwright_script,
        "preview_html": preview_html,
        "auto_visualize": auto_visualize,
    }

    try:
        if st.session_state.mode == "agent":
            with st.spinner(f"🤖 Agent working on: {prompt[:50]}..."):
                task = run_agent(endpoint, prompt, api_messages[:-1], max_steps=MAX_AGENT_STEPS)

            response_parts = []
            for step in task.steps:
                if step.status == "completed" and step.result:
                    response_parts.append(f"**{step.description}**\n\n{truncate_text(str(step.result), 1500)}")
                elif step.error:
                    response_parts.append(f"**{step.description}**\n\n❌ {step.error}")

            final_response = "\n\n---\n\n".join(response_parts) if response_parts else "Agent completed all steps."
            add_message(
                "assistant",
                final_response,
                {
                    "status": "completed",
                    "task": task.to_dict(),
                    "execution_time": task.completed_at - task.created_at if task.completed_at else 0,
                },
            )
            st.session_state.current_task = None
        else:
            with st.spinner("🤔 Thinking..."):
                start_time = time.time()
                tool_log = []
                latest_html = None
                max_tool_rounds = 5
                final_content = None
                status_box = st.empty()

                for round_num in range(max_tool_rounds):
                    if st.session_state.stop_flag:
                        final_content = "⏹️ Request stopped by user."
                        break

                    data = chat_completion(endpoint, api_messages, tools=tools)
                    choice = data.get("choices", [{}])[0]
                    assistant_msg = choice.get("message", {})
                    content = assistant_msg.get("content", "") or ""
                    tool_calls = assistant_msg.get("tool_calls", []) or []

                    if not tool_calls:
                        final_content = content or "Done."
                        break

                    api_messages.append(assistant_msg)

                    for tc in tool_calls:
                        if st.session_state.stop_flag:
                            final_content = "⏹️ Request stopped by user."
                            break

                        func = tc.get("function", {})
                        func_name = func.get("name", "")
                        raw_args = func.get("arguments", "{}")

                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            args = {}

                        status_box.markdown(f"🔧 Running **{func_name}**...")

                        if func_name in available_functions:
                            try:
                                result = available_functions[func_name](**args)
                            except Exception as e:
                                result = f"Tool error: {e}"
                        else:
                            result = f"Unknown tool: {func_name}"

                        if func_name == "preview_html":
                            latest_html = result

                        tool_log.append(f"✅ **{func_name}**\n```\n{truncate_text(str(result), 1000)}\n```")
                        api_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", func_name),
                            "content": str(result),
                        })

                    if final_content:
                        break

                exec_time = time.time() - start_time
                status_box.empty()

                if final_content is None:
                    final_content = "\n\n".join(tool_log + ["⚠️ Max tool rounds reached. Here's what I found so far."])

                add_message(
                    "assistant",
                    final_content,
                    {
                        "execution_time": exec_time,
                        "tool_calls": tool_log,
                        "html_preview": latest_html,
                    },
                )
                st.session_state.stop_flag = False

        save_current_session()
        st.rerun()

    except Exception as e:
        add_message("assistant", f"❌ Error: {str(e)}", {"status": "error", "error": str(e)})
        st.session_state.current_task = None
        st.session_state.stop_flag = False
        save_current_session()
        st.rerun()

# ============================================================
# FOOTER CONTROLS
# ============================================================
st.markdown("---")
cols = st.columns([1, 1, 1, 1])
with cols[0]:
    if st.button("🗑️ Clear Chat", use_container_width=True):
        clear_history()
        st.rerun()
with cols[1]:
    if st.button("💾 Save Session", use_container_width=True):
        save_current_session()
        st.success("Session saved!")
with cols[2]:
    if st.button("📥 Export", use_container_width=True):
        data = export_history()
        st.download_button(
            "Download",
            data,
            file_name=f"chat_{generate_id()}.json",
            mime="application/json",
            use_container_width=True,
        )
with cols[3]:
    if st.button("🧹 Clear Workspace", use_container_width=True):
        for f in Path(WORKSPACE).iterdir():
            try:
                f.unlink()
            except:
                pass
        st.success("Workspace cleared!")
