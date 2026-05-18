"""Sandboxed bash command execution"""
import subprocess
import re
import os
from config import WORKSPACE, MAX_EXECUTION_TIME

DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+0\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    r"\bsudo\b",
    r"\bchown\s+-R\s+/\b",
    r"\bchmod\s+-R\s+777\s+/\b",
    r"\bmount\b",
    r"\bumount\b",
    r"\buseradd\b",
    r"\bpasswd\b",
    r"\bcurl\s+.*\|\s*bash",
    r"\bwget\s+.*\|\s*bash",
]


def is_command_safe(command: str):
    compact = " ".join(command.strip().split())
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, compact, re.IGNORECASE):
            return False, f"Blocked dangerous pattern: {pattern}"
    return True, ""


def execute_bash(command: str) -> str:
    command = command.strip()
    if not command:
        return "Please enter a command."

    ok, reason = is_command_safe(command)
    if not ok:
        return f"🛡️ Security Block: {reason}"

    try:
        result = subprocess.run(
            command,
            shell=True,
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
        return f"Command timed out after {MAX_EXECUTION_TIME} seconds."
    except Exception as e:
        return f"Execution error: {e}"
