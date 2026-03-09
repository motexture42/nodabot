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
- **🛡 Resilience & Debugger Mode**: Built-in "Debugger Agent" that automatically diagnoses persistent tool failures and suggests architectural pivots.
- **🔄 State Management & Undo**: Automatic workspace snapshots before risky operations, allowing for easy rollbacks.
- **🧠 Knowledge Base**: Integrated RAG-lite system using ChromaDB to remember past interactions and user preferences.

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
