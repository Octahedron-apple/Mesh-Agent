# Mesh-Agent

Mesh-Agent is a containerized, asynchronous AI Agent equipped with a Flask-based web backend and a Human-in-the-Loop (HITL) dashboard. It provides a robust, sandboxed environment for executing code, managing state, and interacting with AI models securely.

## Features

- **Containerized Architecture**: Fully dockerized for security and ease of deployment.
- **Sandboxed Execution**: Utilizes `LineRun` to execute generated code within isolated workspaces (`/app/agent_workspace`).
- **Human-in-the-Loop (HITL)**: A dedicated web UI for monitoring agent actions and manually approving or rejecting sensitive operations.
- **Web Dashboard**:
  - **Chat Interface**: Communicate directly with the agent.
  - **Terminal Access**: Monitor workspace terminal output.
  - **Workspace Management**: View files and download the entire workspace as a zip archive.
  - **Configuration**: Dynamically configure the AI provider, API keys, and models.
- **State Rollbacks**: Commit code changes and reset the sandbox to previous states.

## Getting Started

### Prerequisites
- Docker and Docker Compose (recommended)

### Installation & Execution

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Octahedron-apple/Mesh-Agent.git
   cd Mesh-Agent
   ```

2. **Run with Pre-built Docker Image (Recommended)**:
   ```bash
   docker pull ghcr.io/octahedron-apple/mesh-agent:main
   docker run -p 5000:5000 ghcr.io/octahedron-apple/mesh-agent:main
   ```

3. **Or Build from Source**:
   ```bash
   docker build -t mesh-agent -f main.dockerfile .
   docker run -p 5000:5000 mesh-agent
   ```
   *(Or use docker-compose if configured)*

3. **Access the Web Interface**:
   Open your browser and navigate to `http://localhost:5000/`.

## Architecture Overview

- `src/main.py`: The Flask server, managing routing, workspace directories, and the asyncio agent loop.
- `src/agent.py`: Contains the core `AI_Agent` class responsible for processing tasks, requesting tools, and handling HITL interrupts.
- `LineRun`: The isolated code runner handling module installation and code execution.
- `src/templates/`: Jinja2 templates for the UI components.

