# 🤖 WfAgent Pro - Streamlit Edition

Advanced AI agent interface with autonomous capabilities, multi-engine search, code execution, and live previews.

## Features

- **Agent Mode**: Autonomous multi-step task execution with planning, execution, and verification
- **Chat Mode**: Standard conversational interface with tool calling
- **Multi-Engine Search**: DuckDuckGo + SearXNG fallback (no API keys required)
- **Code Execution**: Sandboxed bash, Python, and Playwright execution
- **File Upload**: Support for any file type with smart processing
- **Live HTML Preview**: Render HTML/CSS/JS in real-time
- **Web Scraping**: Extract content from any URL
- **Data Visualization**: Auto-generate charts from CSV/JSON
- **Session Management**: Multiple chat sessions with local storage
- **Code Copy Buttons**: One-click copy on all code blocks

## Deployment on Render

1. Push this repo to GitHub
2. Connect to Render via Blueprint (`render.yaml`)
3. Or manually create a Web Service with Docker runtime
4. Set environment variables if needed

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_URL` | Raw URL to tunnel file | `https://raw.githubusercontent.com/wf2008/Codex/main/frontend/ollama_url.txt` |
| `MAX_AGENT_STEPS` | Max autonomous steps | 10 |
| `MAX_EXECUTION_TIME` | Code execution timeout | 60 |

## Architecture

```
GitHub Actions → Kaggle Notebook → Cloudflare Tunnel → GitHub (URL file)
                                                        ↓ (polls every 10s)
                                                Render (Streamlit App)
                                                        ↓
                                                User Chat Interface
```

## File Structure

```
wfagent-render/
├── app.py                 # Main Streamlit application
├── config.py              # Configuration
├── core/                  # Core modules
│   ├── url_fetcher.py     # Background URL polling
│   ├── ollama_client.py   # AI API client
│   ├── session_manager.py # Chat history
│   └── agent_engine.py    # Agent orchestration
├── tools/                 # Tool implementations
│   ├── web_search.py      # Multi-engine search
│   ├── web_scraper.py     # URL content extraction
│   ├── bash_executor.py   # Bash execution
│   ├── python_executor.py # Python execution
│   ├── playwright_runner.py # Browser automation
│   ├── html_preview.py    # Live HTML rendering
│   ├── file_handler.py    # Smart file processing
│   └── data_viz.py        # Auto visualization
├── utils/                 # Utilities
├── assets/                # CSS and static files
└── workspace/             # Persistent file storage
```

## Usage

1. Start your Kaggle notebook (GitHub Actions triggers it)
2. Wait for tunnel URL to be committed to your repo
3. Open the Render app
4. Toggle between Chat Mode and Agent Mode
5. Upload files, run code, search the web, and more!
