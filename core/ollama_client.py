"""Ollama API client with streaming support"""
import requests
import json
from typing import Iterator, Dict, Any, List


def chat_completion(
    endpoint: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict] = None,
    stream: bool = False,
    temperature: float = 0.4,
    max_tokens: int = 4096,
) -> Dict[str, Any]:
    """Send chat completion request to Ollama/Ollama-compatible endpoint"""
    payload = {
        "model": "wf-agent-model",
        "messages": messages,
        "stream": stream,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools

    url = endpoint.rstrip("/") + "/v1/chat/completions"
    resp = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=180,
        stream=stream,
    )
    resp.raise_for_status()

    if stream:
        return resp
    return resp.json()


def stream_chat(endpoint: str, messages: List[Dict], **kwargs) -> Iterator[str]:
    """Stream tokens from the model"""
    payload = {
        "model": "wf-agent-model",
        "messages": messages,
        "stream": True,
        "temperature": kwargs.get("temperature", 0.4),
        "max_tokens": kwargs.get("max_tokens", 4096),
    }
    if kwargs.get("tools"):
        payload["tools"] = kwargs["tools"]

    url = endpoint.rstrip("/") + "/v1/chat/completions"
    resp = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=180,
        stream=True,
    )
    resp.raise_for_status()

    for line in resp.iter_lines():
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
