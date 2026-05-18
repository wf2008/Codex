"""Configuration for WfAgent Pro Streamlit"""
import os

# GitHub URL where Kaggle pushes the tunnel URL
GITHUB_RAW_URL = os.getenv(
    "GITHUB_URL",
    "https://raw.githubusercontent.com/wf2008/Codex/main/frontend/ollama_url.txt"
)

# Polling interval (seconds)
URL_POLL_INTERVAL = 10

# Workspace for code execution
WORKSPACE = os.path.join(os.path.dirname(__file__), "workspace")
os.makedirs(WORKSPACE, exist_ok=True)

# Agent settings
MAX_AGENT_STEPS = 10
AGENT_TIMEOUT = 300  # seconds

# Model endpoint (read dynamically from GitHub)
OLLAMA_URL = ""  # populated at runtime

# Tools
ENABLE_BASH = True
ENABLE_PYTHON = True
ENABLE_PLAYWRIGHT = True
ENABLE_WEB_SEARCH = True
ENABLE_WEB_SCRAPER = True
ENABLE_HTML_PREVIEW = True
ENABLE_DATA_VIZ = True

# Security
MAX_EXECUTION_TIME = 60  # seconds
MAX_MEMORY_MB = 100
MAX_OUTPUT_LENGTH = 5000

# UI
APP_TITLE = "🤖 WfAgent Pro"
APP_ICON = "🚀"
