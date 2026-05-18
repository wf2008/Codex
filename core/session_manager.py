"""Local session-based chat history management"""
import json
import time
from typing import List, Dict, Any, Optional
import streamlit as st

SESSION_KEY = "wfagent_chat_history"
SESSIONS_KEY = "wfagent_sessions"
CURRENT_SESSION_KEY = "wfagent_current_session"


def get_chat_history() -> List[Dict[str, Any]]:
    """Get current session chat history"""
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = []
    return st.session_state[SESSION_KEY]


def add_message(role: str, content: str, metadata: Dict = None):
    """Add message to history"""
    history = get_chat_history()
    msg = {
        "role": role,
        "content": content,
        "timestamp": time.time(),
        "metadata": metadata or {},
    }
    history.append(msg)
    st.session_state[SESSION_KEY] = history


def clear_history():
    """Clear current session history"""
    st.session_state[SESSION_KEY] = []


def export_history() -> str:
    """Export chat history as JSON string"""
    return json.dumps(get_chat_history(), indent=2, ensure_ascii=False)


def import_history(data: str):
    """Import chat history from JSON string"""
    try:
        history = json.loads(data)
        st.session_state[SESSION_KEY] = history
        return True
    except json.JSONDecodeError:
        return False


def get_sessions() -> Dict[str, Any]:
    """Get all saved sessions"""
    if SESSIONS_KEY not in st.session_state:
        st.session_state[SESSIONS_KEY] = {}
    return st.session_state[SESSIONS_KEY]


def create_session(name: str) -> str:
    """Create a new chat session"""
    sessions = get_sessions()
    session_id = f"session_{int(time.time())}"
    sessions[session_id] = {
        "name": name,
        "created": time.time(),
        "messages": [],
    }
    st.session_state[SESSIONS_KEY] = sessions
    st.session_state[CURRENT_SESSION_KEY] = session_id
    st.session_state[SESSION_KEY] = []
    return session_id


def switch_session(session_id: str):
    """Switch to a different session"""
    sessions = get_sessions()
    if session_id in sessions:
        st.session_state[CURRENT_SESSION_KEY] = session_id
        st.session_state[SESSION_KEY] = sessions[session_id].get("messages", [])


def save_current_session():
    """Save current messages to the active session"""
    sessions = get_sessions()
    current = st.session_state.get(CURRENT_SESSION_KEY, "default")
    if current in sessions:
        sessions[current]["messages"] = get_chat_history()
        st.session_state[SESSIONS_KEY] = sessions


def delete_session(session_id: str):
    """Delete a session"""
    sessions = get_sessions()
    if session_id in sessions:
        del sessions[session_id]
        st.session_state[SESSIONS_KEY] = sessions
