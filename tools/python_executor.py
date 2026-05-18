"""Sandboxed Python code execution"""
import subprocess
import os
import time
from pathlib import Path
from config import WORKSPACE, MAX_EXECUTION_TIME


def run_python(code: str) -> str:
    code = code.strip()
    if not code:
        return "Please provide Python code."

    try:
        temp_file = Path(WORKSPACE) / f"python_exec_{int(time.time() * 1000)}.py"
        temp_file.write_text(code, encoding="utf-8")
        result = subprocess.run(
            ["python3", str(temp_file)],
            capture_output=True,
            text=True,
            timeout=MAX_EXECUTION_TIME,
            cwd=WORKSPACE,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            return f"Exit code: {result.returncode}\nSTDERR:\n{stderr or '(empty)'}\n\nSTDOUT:\n{stdout or '(empty)'}"
        return stdout or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Python execution timed out after {MAX_EXECUTION_TIME} seconds."
    except Exception as e:
        return f"Python execution error: {e}"
    finally:
        try:
            temp_file.unlink()
        except:
            pass
