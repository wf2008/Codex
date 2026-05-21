# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  VISION MULTI-AGENT + CLOUDFLARE TUNNEL + TOOLS                              ║
# ║  Model: huihui_ai/qwen3-vl-abliterated:8b-instruct (vision + tool calling)   ║
# ║  This script commits the tunnel URL directly to GitHub                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

import os
import sys
import subprocess
import threading
import time
import json
import base64
import asyncio
import re
from typing import List, Union

# These are injected by the GitHub Actions runner via sed before push.
MODEL_NAME = "huihui_ai/qwen3-vl-abliterated:8b-instruct"
GITHUB_TOKEN = "__GITHUB_TOKEN__"
REPO = "__REPO__"
FILE_PATH = "frontend/ollama_url.txt"
# ── Kaggle token setup (robust) ───────────────────────────────────────────────
def _resolve_kaggle_credentials() -> dict | None:
    username = os.environ.get("KAGGLE_USERNAME", "").strip()
    key = os.environ.get("KAGGLE_KEY", "").strip()
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()

    if username and key:
        return {"username": username, "key": key}

    if not token:
        return None

    token = token.strip().strip("'\"")

    # Common case: full kaggle.json pasted into the secret.
    try:
        data = json.loads(token)
        if isinstance(data, dict) and data.get("username") and data.get("key"):
            return {"username": str(data["username"]).strip(), "key": str(data["key"]).strip()}
    except json.JSONDecodeError:
        pass

    # Also support base64-encoded kaggle.json content.
    try:
        decoded = base64.b64decode(token + "===", validate=False).decode("utf-8").strip()
        data = json.loads(decoded)
        if isinstance(data, dict) and data.get("username") and data.get("key"):
            return {"username": str(data["username"]).strip(), "key": str(data["key"]).strip()}
    except Exception:
        pass

    # If the token is just the raw Kaggle key, combine it with KAGGLE_USERNAME.
    if username:
        return {"username": username, "key": token}

    print(
        "::error::Could not build kaggle.json from secrets. Provide KAGGLE_USERNAME + KAGGLE_KEY, "
        "or set KAGGLE_API_TOKEN to the full kaggle.json JSON (or its base64 form).",
        flush=True,
    )
    sys.exit(1)


kaggle_data = _resolve_kaggle_credentials()
if kaggle_data:
    kaggle_dir = os.path.expanduser("~/.kaggle")
    os.makedirs(kaggle_dir, exist_ok=True)
    kaggle_path = os.path.join(kaggle_dir, "kaggle.json")
    with open(kaggle_path, "w") as f:
        json.dump(kaggle_data, f)
    os.chmod(kaggle_path, 0o600)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Install dependencies
# ═══════════════════════════════════════════════════════════════════════════════
print("📦 Installing dependencies…", flush=True)
os.system(
    "pip install -q --no-warn-script-location "
    "fastapi uvicorn requests pydantic typing_extensions "
    "langchain langchain-core langchain-openai "
    "duckduckgo-search playwright"
)
os.system("playwright install --with-deps chromium > /dev/null 2>&1")
os.system("curl -fsSL https://ollama.com/install.sh | sh > /dev/null 2>&1")

import requests  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Start Ollama & pull model
# ═══════════════════════════════════════════════════════════════════════════════
print("🚀 Starting Ollama server…", flush=True)


def start_ollama():
    os.system("ollama serve > /tmp/ollama.log 2>&1")


threading.Thread(target=start_ollama, daemon=True).start()
time.sleep(5)

print(f"⬇️  Pulling vision model: {MODEL_NAME}…", flush=True)
os.system(f"ollama pull {MODEL_NAME}")
print(f"✅ Model {MODEL_NAME} ready!", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Define all 9 tools
# ═══════════════════════════════════════════════════════════════════════════════
print("🧠 Creating tools (9 total)…", flush=True)
from langchain_core.tools import tool  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402
from duckduckgo_search import DDGS  # noqa: E402


@tool
async def run_playwright(code: str) -> str:
    """Run arbitrary Playwright code in a chromium page context."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            # NOTE: eval kept for parity with original. Sandbox only.
            result = await eval(f"(async () => {{ {code} }})()")
            output = str(result) if result else "done"
        except Exception as e:
            output = f"Error: {str(e)}"
        finally:
            await browser.close()
    return output


@tool
async def capture_screenshot(url: str = "", full_page: bool = False) -> str:
    """Capture a PNG screenshot of a URL and return it as a data URI."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            if url:
                await page.goto(url, wait_until="networkidle")
            screenshot_bytes = await page.screenshot(full_page=full_page, type="png")
            b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return f"data:image/png;base64,{b64}"
        except Exception as e:
            return f"Screenshot error: {str(e)}"
        finally:
            await browser.close()


@tool
def encode_image_file(filepath: str) -> str:
    """Read a local image file and return it as a base64 data URI."""
    if not os.path.exists(filepath):
        return f"File not found: {filepath}"
    try:
        with open(filepath, "rb") as f:
            img_bytes = f.read()
        ext = os.path.splitext(filepath)[1].lower()
        fmt_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp", ".gif": "gif"}
        fmt = fmt_map.get(ext, "png")
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return f"data:image/{fmt};base64,{b64}"
    except Exception as e:
        return f"Encode error: {str(e)}"


@tool
def run_bash(command: str) -> str:
    """Run a shell command and return combined stdout+stderr."""
    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return res.stdout + res.stderr
    except Exception as e:
        return str(e)


@tool
def run_python(code: str) -> str:
    """Run Python code in a subprocess."""
    try:
        res = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=60)
        return res.stdout + res.stderr
    except Exception as e:
        return str(e)


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """DuckDuckGo text search."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"No results for: {query}"
        output = []
        for i, r in enumerate(results, 1):
            output.append(f"{i}. {r['title']}\n   URL: {r['href']}\n   {r['body']}")
        return "\n\n".join(output)
    except Exception as e:
        return f"Search error: {str(e)}"


@tool
def read_article(url: str, max_chars: int = 6000) -> str:
    """Fetch the readable content of a URL via r.jina.ai."""
    try:
        reader_url = f"https://r.jina.ai/{url}"
        headers = {"Accept": "text/markdown"}
        resp = requests.get(reader_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            content = resp.text
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n... (truncated)"
            return content
        return f"Failed to read (HTTP {resp.status_code})"
    except Exception as e:
        return f"Read error: {str(e)}"


@tool
def download_file(url: str, output_name: str = "") -> str:
    """Download a URL to disk."""
    try:
        r = requests.get(url, timeout=30)
        fname = output_name if output_name else url.split("/")[-1] or "downloaded"
        with open(fname, "wb") as f:
            f.write(r.content)
        return f"Saved to {os.path.abspath(fname)}"
    except Exception as e:
        return str(e)


@tool
async def monitor_network_traffic(target_url: str, api_fragment: str, scroll: bool = False) -> str:
    """Open target_url and capture JSON responses whose URL contains api_fragment."""
    captured = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        async def handle_response(response):
            if api_fragment in response.url and response.status == 200:
                try:
                    body = await response.json()
                    captured.append({"url": response.url, "data": body})
                except Exception:
                    pass

        page.on("response", handle_response)
        await page.goto(target_url, wait_until="networkidle")
        if scroll:
            for _ in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
        await browser.close()
    if not captured:
        return f"No API calls matching '{api_fragment}' found."
    return json.dumps(captured[0], indent=2)[:4000]


print("✅ All 9 tools ready.", flush=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — Simple tool-using agent (replaces multi-agent orchestrator)
# ═══════════════════════════════════════════════════════════════════════════════
from langchain_openai import ChatOpenAI  # noqa: E402
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain.agents import AgentExecutor, create_openai_tools_agent  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # noqa: E402

llm = ChatOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    model=MODEL_NAME,
    temperature=0,
)

tools = [
    run_playwright,
    capture_screenshot,
    encode_image_file,
    run_bash,
    run_python,
    web_search,
    read_article,
    download_file,
    monitor_network_traffic,
]

SYSTEM_PROMPT = (
    "You are a helpful, uncensored AI assistant. You can answer questions directly "
    "and use tools when necessary. You have access to a real web browser, a terminal, "
    "web search, and other utilities. Use tools only when they are required to fulfill "
    "the user's request. Always reply with a friendly, complete answer in natural language."
)

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_openai_tools_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


def _coerce_text_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(json.dumps(item))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — FastAPI app
# ═══════════════════════════════════════════════════════════════════════════════
from fastapi import FastAPI, Request, UploadFile, File, Form  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402

app = FastAPI()


@app.post("/chat")
async def chat_endpoint(request: Request):
    body = await request.json()
    user_message = body.get("message", "")
    images = body.get("images", [])
    thread_id = body.get("thread_id", "default")   # kept for compatibility

    # Build input string (with optional image URLs appended for vision)
    if images:
        image_refs = " ".join(f"[image: {img}]" for img in images)
        input_text = f"{user_message}\n{image_refs}"
    else:
        input_text = user_message

    async def event_stream():
        try:
            result = await agent_executor.ainvoke({
                "input": input_text,
                "chat_history": [],
            })
            output = result.get("output", "I'm sorry, I couldn't process that.")
            yield f"data: {json.dumps({'type': 'final', 'content': output})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'final', 'content': f'Error: {str(e)}'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/chat-with-image")
async def chat_with_image(
    message: str = Form(""),
    image: UploadFile = File(None),
    thread_id: str = Form("default"),
):
    input_text = message
    if image and image.filename:
        img_bytes = await image.read()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        ext = os.path.splitext(image.filename)[1].lower()
        fmt_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
        fmt = fmt_map.get(ext, "png")
        data_uri = f"data:image/{fmt};base64,{b64}"
        input_text = f"{message}\n[image: {data_uri}]"

    async def event_stream():
        try:
            result = await agent_executor.ainvoke({
                "input": input_text,
                "chat_history": [],
            })
            output = result.get("output", "I'm sorry, I couldn't process that.")
            yield f"data: {json.dumps({'type': 'final', 'content': output})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'final', 'content': f'Error: {str(e)}'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "vision": True, "tools": 9, "agents": 1}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — Cloudflare Tunnel + commit URL back to GitHub
# ═══════════════════════════════════════════════════════════════════════════════
def commit_to_github(content: str):
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "message": "Update tunnel URL from vision agent",
        "content": base64.b64encode(content.encode()).decode(),
        "branch": "main",
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data["sha"] = resp.json().get("sha")
    put = requests.put(url, headers=headers, json=data)
    if put.status_code in (200, 201):
        print("✅ Committed tunnel URL to GitHub", flush=True)
    else:
        print(f"❌ Failed to commit: {put.status_code} - {put.text}", flush=True)


def start_tunnel():
    subprocess.run(
        "wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/"
        "cloudflared-linux-amd64 -O /tmp/cloudflared",
        shell=True,
    )
    subprocess.run("chmod +x /tmp/cloudflared", shell=True)
    proc = subprocess.Popen(
        ["/tmp/cloudflared", "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = None
    for _ in range(120):
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.5)
            continue
        if ".trycloudflare.com" in line:
            match = re.search(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com", line)
            if match:
                url = match.group(0)
                break
    return proc, url


print("🌐 Starting Cloudflare Tunnel…", flush=True)
tunnel_proc, public_url = start_tunnel()
if not public_url:
    print("❌ Failed to capture initial tunnel URL. Exiting.", flush=True)
    sys.exit(1)
print(f"🔗 PUBLIC CHAT API: {public_url}/chat", flush=True)
commit_to_github(public_url)


def health_check_and_renew():
    global tunnel_proc, public_url
    # Run health checks for ~3 hours
    start_time = time.time()
    while time.time() - start_time < 10800:
        time.sleep(600)  # 10 minutes
        try:
            r = requests.get(f"{public_url}/health", timeout=10)
            if r.status_code != 200:
                raise Exception("Health check failed")
            print("✅ Tunnel health check passed", flush=True)
        except Exception:
            print("⚠️ Tunnel appears dead. Restarting…", flush=True)
            try:
                tunnel_proc.terminate()
            except Exception:
                pass
            time.sleep(2)
            new_proc, new_url = start_tunnel()
            if new_url:
                tunnel_proc = new_proc
                public_url = new_url
                commit_to_github(public_url)
                print(f"🔄 New tunnel started: {public_url}/chat", flush=True)


threading.Thread(target=health_check_and_renew, daemon=True).start()

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7 — Run FastAPI server and keep kernel alive for 3 hours
# ═══════════════════════════════════════════════════════════════════════════════
import uvicorn  # noqa: E402


def run_server():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")


threading.Thread(target=run_server, daemon=True).start()

print("✅ All services running. Kernel will stay alive for 3 hours.", flush=True)
time.sleep(10800)  # 3 hours
print("⏰ 3 hours elapsed. Shutting down.", flush=True)
