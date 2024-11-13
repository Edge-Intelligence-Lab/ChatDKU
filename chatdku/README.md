# ChatDKU

## Overview

- `chatdku.core`: Core agent and RAG logic.
  - `chatdku.core.agent`: The main agent logic. You can directly execute it for a simple CLI that asks you for a query and gives a response.
  - `chatdku.core.compile`: (WIP) Uses DSPy for automatic prompt optimization.
  - `chatdku.core.llamaindex_tools`: The vector retriever uses LlamaIndex and ChromaDB, while the keyword retriever directly uses Redis (should consider putting it into a separate module).
  - `chatdku.core.dspy_common`: Helpers for interacting with DSPy.
  - `chatdku.core.dspy_patch`: Patches the internals of DSPy to adapt it to our project.
  - `chatdku.core.utils`: Utility functions.

- `chatdku/frontend`: The HTML, CSS, and JavaScript web frontend.

- `chatdku.backend`: Backend Flask apps.
  - `chatdku.backend.agent_app`: The main backend app that uses `chatdku.core.agent`.
  - `chatdku.backend.save_feedback`: The backend app that saves user feedback.


## Usage

All commands are assumed to be executed in the current directory (`project_root/chatdku`).

Install dependencies in a virtual environment:
```bash
pip install -e .
```

For the sake of easy monitoring and long-term running, the commands will all be executed with "nohup".

### Frontend

First, we need to turn this folder into a Python server so that users can see the index.html file when they access the corresponding port.
```bash
nohup python -u -m http.server 9011 -d chatdku/frontend > ./logs/python_server_logs.txt &
disown -h
```
### Backend (`agent_app.py`)

Next, start the `agent_app.py` service. This is the agent interface.(agent_app use port 9012 now)
```bash
nohup python -u chatdku/backend/agent_app.py > ./logs/agent_logs.txt &
disown -h
```

### Backend (`save_feedback.py`)

Finally, start the `save_feedback.py` service. (Using port 9013 now)
```bash
nohup python -u chatdku/backend/save_feedback.py > ./logs/save_fb_logs.txt &
disown -h
```

You can use this to check if ther are running.
```bash
ps -aux | grep python
```
