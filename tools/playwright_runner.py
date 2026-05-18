"""Playwright browser automation execution"""
import subprocess
import os
import time
from pathlib import Path
from config import WORKSPACE

PLAYWRIGHT_TEMPLATE = '''
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
{body}
    browser.close()
'''


def run_playwright_script(script: str) -> str:
    script = script.strip()
    if not script:
        return "Please provide Playwright Python body code."

    indented = "\n".join("    " + line for line in script.splitlines())
    wrapped = PLAYWRIGHT_TEMPLATE.format(body=indented)

    try:
        temp_file = Path(WORKSPACE) / f"playwright_exec_{int(time.time() * 1000)}.py"
        temp_file.write_text(wrapped, encoding="utf-8")
        result = subprocess.run(
            ["python3", str(temp_file)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=WORKSPACE,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            if "No module named 'playwright'" in stderr:
                return (
                    "Playwright is not installed. Run:\n"
                    "pip install playwright && playwright install chromium"
                )
            return f"Exit code: {result.returncode}\nSTDERR:\n{stderr or '(empty)'}\n\nSTDOUT:\n{stdout or '(empty)'}"
        return stdout or "(no output)"
    except subprocess.TimeoutExpired:
        return "Playwright script timed out after 120 seconds."
    except Exception as e:
        return f"Playwright execution error: {e}"
    finally:
        try:
            temp_file.unlink()
        except:
            pass
