"""Message formatting utilities."""
import html as html_module
import json
import re


def format_message(content: str, role: str = "assistant") -> str:
    """Format message content for display."""
    if not content:
        return ""

    content = html_module.escape(content)
    content = content.replace("\n", "<br>")
    return content


def extract_code_blocks(text: str) -> list:
    """Extract code blocks from markdown text."""
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [{"language": lang, "code": code} for lang, code in matches]


def copy_button(code: str, button_id: str = None) -> str:
    """Generate HTML for a copy button."""
    if button_id is None:
        button_id = f"copy_{hash(code) % 100000}"

    js_code_literal = json.dumps(code)
    return f"""
    <button id="{button_id}" onclick="navigator.clipboard.writeText({js_code_literal});
        document.getElementById('{button_id}').innerText='✅ Copied!';
        setTimeout(()=>document.getElementById('{button_id}').innerText='📋 Copy', 2000);"
        style="float:right; background:#6366f1; color:white; border:none; border-radius:6px; padding:4px 12px; cursor:pointer; font-size:12px;">
        📋 Copy
    </button>
    """


def render_code_block(code: str, language: str = "") -> str:
    """Render a code block with copy button."""
    copy_btn = copy_button(code)
    return f"""
    <div style="position:relative; background:#1e1e2e; border-radius:10px; padding:16px; margin:8px 0;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="color:#94a3b8; font-size:12px; text-transform:uppercase;">{language or 'code'}</span>
            {copy_btn}
        </div>
        <pre style="margin:0; overflow-x:auto;"><code style="color:#e2e8f0; font-family:'Fira Code', monospace; font-size:13px;">{html_module.escape(code)}</code></pre>
    </div>
    """
