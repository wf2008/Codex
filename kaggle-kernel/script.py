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
from typing import TypedDict, List, Literal, Union
from typing_extensions import Annotated
import operator

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
    "langchain langchain-core langchain-openai langgraph "
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
# PHASE 4 — Build the multi-agent orchestrator
# ═══════════════════════════════════════════════════════════════════════════════
from langchain_openai import ChatOpenAI  # noqa: E402
from langgraph.graph import StateGraph, END  # noqa: E402
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage  # noqa: E402

llm = ChatOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    model=MODEL_NAME,
    temperature=0,
)

research_llm = llm.bind_tools(
    [web_search, read_article, download_file, run_playwright,
     capture_screenshot, encode_image_file, monitor_network_traffic]
)
code_llm = llm.bind_tools(
    [run_python, run_bash, run_playwright, download_file,
     capture_screenshot, encode_image_file, monitor_network_traffic]
)
test_llm = llm.bind_tools(
    [run_playwright, capture_screenshot, run_bash, run_python, encode_image_file]
)

research_system = (
    "You are a Vision-enabled Research Agent. Search the web, read articles, take screenshots, "
    "analyze images, and monitor network traffic to find hidden APIs. "
    "Describe what you see in detail. Return factual findings; do not write final code."
)

code_system = (
    "You are a Vision-enabled Code Agent. Write and execute Python/bash scripts. "
    "Use run_python to execute any Python code, run_bash for shell commands. "
    "You can take screenshots, analyze images, and monitor network traffic. "
    "Return the final working code and summary."
)

test_system = (
    "You are a Vision-enabled Test Agent. Validate outputs using Playwright and bash. "
    "Use run_python to run test scripts. Take screenshots and visually inspect them. "
    "Report findings with image evidence."
)

TOOL_REGISTRY = {
    tool.name: tool
    for tool in [
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
}
MAX_AGENT_TOOL_ROUNDS = 8


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


async def _execute_tool_call(tool_call: dict) -> ToolMessage:
    tool_name = tool_call["name"]
    tool_obj = TOOL_REGISTRY.get(tool_name)
    try:
        if tool_obj is None:
            result = f"Tool not found: {tool_name}"
        else:
            result = await tool_obj.ainvoke(tool_call.get("args", {}))
            if result is None or result == "":
                result = "done"
    except Exception as e:
        result = f"Tool error: {str(e)}"
    return ToolMessage(
        content=_coerce_text_content(result),
        tool_call_id=tool_call["id"],
        name=tool_name,
    )


async def _run_agent_with_tools(agent_llm, system_prompt: str, state):
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    emitted_messages = []

    for _ in range(MAX_AGENT_TOOL_ROUNDS):
        ai_msg = await agent_llm.ainvoke(messages)
        emitted_messages.append(ai_msg)
        messages.append(ai_msg)

        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        if not tool_calls:
            return {"messages": emitted_messages}

        for tool_call in tool_calls:
            tool_msg = await _execute_tool_call(tool_call)
            emitted_messages.append(tool_msg)
            messages.append(tool_msg)

    emitted_messages.append(
        AIMessage(content="Agent stopped after reaching the tool-call limit without producing a final text response.")
    )
    return {"messages": emitted_messages}


async def research_node(state):
    return await _run_agent_with_tools(research_llm, research_system, state)


async def code_node(state):
    return await _run_agent_with_tools(code_llm, code_system, state)


async def test_node(state):
    return await _run_agent_with_tools(test_llm, test_system, state)


def synthesis_node(state):
    history = state["messages"]
    prompt = SystemMessage(content=(
        "You are the final summariser. Based on the entire conversation above, "
        "write a clear, concise answer to the user's original request. "
        "Include the results from research, code, and tests. Do NOT call any tools."
    ))
    synthesis_llm = ChatOpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model=MODEL_NAME,
        temperature=0,
    )
    response = synthesis_llm.invoke([prompt] + history)
    return {"messages": [response]}


class SupervisorDecision(BaseModel):
    next_agent: Literal["research", "code", "test", "synthesis", "FINISH"] = Field(
        description="Next agent: 'research', 'code', 'test', 'synthesis', or 'FINISH' if final summary already generated."
    )
    reason: str = Field(description="Why this agent is being called.")


supervisor_system = (
    "You are the Vision-enabled Orchestrator. You manage three worker agents (Research, Code, Test) "
    "and a Synthesis agent that writes the final answer. "
    "You can SEE images in the conversation. "
    "Break the task into sub-tasks and delegate. Start with Research if information is needed, "
    "then Code to build, then Test to validate. "
    "Once all work is done, route to 'synthesis' to create a final answer. "
    "After synthesis, respond with FINISH."
)


def supervisor_node(state):
    messages = [SystemMessage(content=supervisor_system)] + state["messages"]
    sup_llm = llm.bind_tools([SupervisorDecision])
    return {"messages": [sup_llm.invoke(messages)]}


def decide_next(state) -> str:
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc["name"] == "SupervisorDecision":
                decision = tc["args"].get("next_agent")
                if decision in ["research", "code", "test", "synthesis"]:
                    return decision
                elif decision == "FINISH":
                    return "finish"
    return "finish"


class AgentState(TypedDict):
    messages: Annotated[
        List[Union[HumanMessage, AIMessage, SystemMessage, ToolMessage]],
        operator.add,
    ]


workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("research", research_node)
workflow.add_node("code", code_node)
workflow.add_node("test", test_node)
workflow.add_node("synthesis", synthesis_node)
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges(
    "supervisor", decide_next,
    {
        "research": "research",
        "code": "code",
        "test": "test",
        "synthesis": "synthesis",
        "finish": END,
    },
)
workflow.add_edge("research", "supervisor")
workflow.add_edge("code", "supervisor")
workflow.add_edge("test", "supervisor")
workflow.add_edge("synthesis", END)

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

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
    thread_id = body.get("thread_id", "default")
    config = {"configurable": {"thread_id": thread_id}}
    if images:
        content_parts = [{"type": "text", "text": user_message}]
        for img in images:
            content_parts.append({"type": "image_url", "image_url": {"url": img}})
        human_msg = HumanMessage(content=content_parts)
    else:
        human_msg = HumanMessage(content=user_message)

    async def event_stream():
        final_output = ""
        try:
            inputs = {"messages": [human_msg]}
            async for event in graph.astream(inputs, config, stream_mode="values"):
                if "messages" not in event:
                    continue
                last_msg = event["messages"][-1]
                if isinstance(last_msg, AIMessage):
                    text = _coerce_text_content(last_msg.content).strip()
                    if text:
                        final_output = text
                        yield f"data: {json.dumps({'type': 'agent_output', 'content': text})}\n\n"
                elif isinstance(last_msg, ToolMessage):
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': last_msg.name, 'content': _coerce_text_content(last_msg.content)[:300]})}\n\n"
            if not final_output:
                final_output = "Agent completed, but no text response was generated."
            yield f"data: {json.dumps({'type': 'final', 'content': final_output})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/chat-with-image")
async def chat_with_image(
    message: str = Form(""),
    image: UploadFile = File(None),
    thread_id: str = Form("default"),
):
    config = {"configurable": {"thread_id": thread_id}}
    content_parts = [{"type": "text", "text": message}]
    if image and image.filename:
        img_bytes = await image.read()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        ext = os.path.splitext(image.filename)[1].lower()
        fmt_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
        fmt = fmt_map.get(ext, "png")
        data_uri = f"data:image/{fmt};base64,{b64}"
        content_parts.append({"type": "image_url", "image_url": {"url": data_uri}})
    human_msg = HumanMessage(content=content_parts if len(content_parts) > 1 else message)

    async def event_stream():
        final_output = ""
        try:
            inputs = {"messages": [human_msg]}
            async for event in graph.astream(inputs, config, stream_mode="values"):
                if "messages" not in event:
                    continue
                last_msg = event["messages"][-1]
                if isinstance(last_msg, AIMessage):
                    text = _coerce_text_content(last_msg.content).strip()
                    if text:
                        final_output = text
                        yield f"data: {json.dumps({'type': 'agent_output', 'content': text})}\n\n"
                elif isinstance(last_msg, ToolMessage):
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': last_msg.name, 'content': _coerce_text_content(last_msg.content)[:300]})}\n\n"
            if not final_output:
                final_output = "Agent completed, but no text response was generated."
            yield f"data: {json.dumps({'type': 'final', 'content': final_output})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "vision": True, "tools": 9, "agents": 5}


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
