# 📡 NodaBot (NB)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Local LLM](https://img.shields.io/badge/LLM-Local--First-emerald.svg)](#core-philosophy)

NodaBot (NB) is a lightweight, high-precision autonomous agent designed specifically for **local execution**. Built on the philosophy that a "Node" is a fundamental point of intelligence, NodaBot acts as the central orchestrator for your local tools, files, and system events.

---

## 🌟 Key Features

- **⚡ Low-Latency Reasoning**: Optimized for small, fast models (7B - 14B parameters).
- **🛠 Modular Toolset**: Dynamically discoverable tools for shell execution, file management, web searching, and vision analysis.
- **🖥 Real-time UI**: A modern Web Interface (NodaBot Central) built with Flask and SocketIO for interactive debugging and session tracking.
- **📱 Telegram Integration**: Full 2-way sync with Telegram for on-the-go control, complete with live status typing and truncated log outputs.
- **🧠 Expert Skill System**: Inject specialized knowledge instantly (React, Docker, Data Science, etc.) using `SKILL.md` persona files to guide the agent's workflows.
- **📦 Sandboxed Execution**: Run Python scripts safely inside dynamically generated Virtual Environments (`venv`) to prevent polluting your global host.
- **🛑 Human-in-the-Loop Security**: Safely intercepts potentially destructive terminal commands (like `rm`, `mv`, or `git`) and requires explicit approval via the Web UI or Telegram before execution.
- **🔍 Advanced Web Search**: Powered by Tavily API (with DuckDuckGo fallback) to extract clean, structured AI-ready data from the web.
- **🤖 Swarm Delegation**: Built-in orchestration to spawn independent child agents (Researchers, Coders, Writers) for complex, multi-step tasks.
- **🛡 Resilience & State Management**: Automatic workspace snapshots before risky operations, allowing for easy rollbacks and autonomous error recovery.

---

## 🏗 Architecture

The system is designed with strict separation of concerns:

- **`core/`**: The engine of the agent. Handles the reasoning loop, message history, and LLM provider abstractions.
- **`tools/`**: A library of surgical capabilities (File, Shell, Vision, Search, etc.).
- **`utils/`**: Decoupled managers for system snapshots, watchers, and tool discovery.
- **`config.py`**: Centralized configuration using environment variables (`.env`).

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- A local LLM provider (e.g., [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.ai/)).

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/motextur3/nodabot.git
cd nodabot

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Copy the example environment file:
```bash
cp .env.example .env
```
Update your local model details in `.env`.

### 4. Run NodaBot
```bash
python app.py
```
Open your browser and navigate to `http://127.0.0.1:5001`.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
