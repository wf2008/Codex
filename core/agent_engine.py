"""Agent orchestration engine for autonomous multi-step tasks"""
import json
import time
from typing import List, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.ollama_client import chat_completion
from tools.web_search import web_search
from tools.web_scraper import web_scraper
from tools.bash_executor import execute_bash
from tools.python_executor import run_python
from tools.playwright_runner import run_playwright_script
from tools.html_preview import preview_html


class AgentStep:
    def __init__(self, step_type: str, description: str, tool: str = None, args: Dict = None):
        self.step_type = step_type  # "research", "code", "test", "verify", "synthesize"
        self.description = description
        self.tool = tool
        self.args = args or {}
        self.result = None
        self.status = "pending"  # pending, running, completed, failed
        self.error = None
        self.start_time = None
        self.end_time = None


class AgentTask:
    def __init__(self, goal: str, max_steps: int = 10):
        self.goal = goal
        self.max_steps = max_steps
        self.steps: List[AgentStep] = []
        self.current_step = 0
        self.status = "planning"  # planning, executing, completed, failed
        self.created_at = time.time()
        self.completed_at = None
        self.context = {}  # Shared context across steps

    def add_step(self, step: AgentStep):
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "status": self.status,
            "steps": [
                {
                    "type": s.step_type,
                    "description": s.description,
                    "tool": s.tool,
                    "status": s.status,
                    "result": str(s.result)[:500] if s.result else None,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "current_step": self.current_step,
        }


# Tool registry for agents
AGENT_TOOLS = {
    "web_search": web_search,
    "web_scraper": web_scraper,
    "run_bash_command": execute_bash,
    "run_python_code": run_python,
    "run_playwright_script": run_playwright_script,
    "preview_html": preview_html,
}


def create_plan(endpoint: str, goal: str, history: List[Dict]) -> List[AgentStep]:
    """Ask the AI to create an execution plan"""
    plan_prompt = f"""You are an autonomous agent planner. The user has given you this goal:

GOAL: {goal}

Create a step-by-step plan to accomplish this goal. You have these tools available:
- web_search: Search the internet for information
- web_scraper: Extract content from specific URLs
- run_bash_command: Execute bash commands
- run_python_code: Execute Python code
- run_playwright_script: Automate browser tasks
- preview_html: Render HTML/CSS/JS

Return ONLY a JSON array of steps like this:
[
  {{"step_type": "research", "description": "Search for X", "tool": "web_search", "args": {{"query": "X"}}}},
  {{"step_type": "code", "description": "Write Python to process data", "tool": "run_python_code", "args": {{"code": "..."}}}},
  {{"step_type": "test", "description": "Verify the result", "tool": "run_bash_command", "args": {{"command": "..."}}}},
  {{"step_type": "synthesize", "description": "Combine results and present", "tool": null, "args": {{}}}}
]

Each step must have: step_type (research|code|test|verify|synthesize), description, tool (or null), and args.
"""
    messages = history + [{"role": "user", "content": plan_prompt}]
    try:
        resp = chat_completion(endpoint, messages, max_tokens=2048)
        content = resp["choices"][0]["message"]["content"]
        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        plan = json.loads(content.strip())
        steps = []
        for p in plan:
            steps.append(AgentStep(
                step_type=p.get("step_type", "code"),
                description=p.get("description", ""),
                tool=p.get("tool"),
                args=p.get("args", {}),
            ))
        return steps
    except Exception as e:
        # Fallback plan
        return [
            AgentStep("research", f"Search for information about: {goal}", "web_search", {"query": goal}),
            AgentStep("synthesize", "Present findings", None, {}),
        ]


def execute_step(step: AgentStep, context: Dict) -> str:
    """Execute a single agent step"""
    step.status = "running"
    step.start_time = time.time()

    try:
        if step.tool and step.tool in AGENT_TOOLS:
            # Substitute context variables in args
            args = step.args.copy()
            for key, val in args.items():
                if isinstance(val, str) and "{{" in val:
                    for ctx_key, ctx_val in context.items():
                        val = val.replace(f"{{{ctx_key}}}", str(ctx_val)[:1000])
                    args[key] = val

            result = AGENT_TOOLS[step.tool](**args)
            step.result = result
            step.status = "completed"
            return result
        else:
            step.result = step.description
            step.status = "completed"
            return step.description
    except Exception as e:
        step.error = str(e)
        step.status = "failed"
        return f"Error: {e}"
    finally:
        step.end_time = time.time()


def run_agent(endpoint: str, goal: str, history: List[Dict], max_steps: int = 10) -> AgentTask:
    """Run the full agent loop"""
    task = AgentTask(goal, max_steps)
    task.status = "planning"

    # Create plan
    plan_steps = create_plan(endpoint, goal, history)
    for step in plan_steps[:max_steps]:
        task.add_step(step)

    task.status = "executing"

    # Execute steps - some can be parallel
    for i, step in enumerate(task.steps):
        task.current_step = i
        result = execute_step(step, task.context)

        # Store result in context for later steps
        task.context[f"step_{i}_result"] = result

        # If step failed, try to recover with debug step
        if step.status == "failed" and i < len(task.steps) - 1:
            debug_step = AgentStep(
                "verify",
                f"Debug failed step: {step.error}",
                "run_python_code",
                {"code": f"print('Debug: {step.error}')"},
            )
            task.steps.insert(i + 1, debug_step)

    task.status = "completed"
    task.completed_at = time.time()
    return task


def run_parallel_agents(endpoint: str, goals: List[str], history: List[Dict]) -> List[AgentTask]:
    """Run multiple agents in parallel for different sub-goals"""
    tasks = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(run_agent, endpoint, goal, history): goal for goal in goals}
        for future in as_completed(futures):
            goal = futures[future]
            try:
                task = future.result()
                tasks.append(task)
            except Exception as e:
                task = AgentTask(goal)
                task.status = "failed"
                task.steps.append(AgentStep("synthesize", f"Failed: {e}", None, {}))
                tasks.append(task)
    return tasks
