# Free AI Gateway

## Overview

Why pay for AI APIs when you can self-host free access?

This project provides a unified RESTful API interface to interact with multiple AI providers (ChatGPT, Gemini, Grok) through browser automation. It enables programmatic access without requiring API keys or paid subscriptions.

Powered by [nodriver](https://github.com/ultrafunkamsterdam/nodriver) for next-generation async browser automation.

## Features

-   **Multiple Providers**: Support for ChatGPT (GPT-4o-mini), Google Gemini, and Grok.
-   **Unified API**: OpenAI-compatible `chat/completions` endpoint.
-   **Browser Automation**: Uses `nodriver` for stealthy and efficient automation.
-   **Docker Ready**: Easy deployment with Docker Compose.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Felixdiamond/free-ai-gateway
    cd free-ai-gateway
    ```

2.  **Install dependencies:**
    Using `uv` (recommended):
    ```bash
    uv pip install -r requirements.txt
    ```
    Or standard pip:
    ```bash
    pip install -r requirements.txt
    ```

    *Note: Requires Python 3.10+*

## Docker Deployment

1.  **Build and run with Docker Compose:**
    ```bash
    docker-compose up -d --build
    ```

2.  The API will be available at `http://localhost:8000`.

3.  **Configuration:**
    Ensure you have a `.env` file created (copy from `.env.example`) before running the container.

## Configuration

1.  Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
2.  Edit `.env` to configure your settings (e.g., browser path, headless mode).

## Usage

Start the server:

```bash
uvicorn app.main:app
```

The API will be available at `http://localhost:8000`.

## API Endpoints

### POST /v1/chat/completions

Compatible with OpenAI's chat completion format.

**Request Body:**

```json
{
    "prompt": "Explain quantum computing",
    "system_prompt": "You are a helpful physics teacher",
    "provider": "chatgpt", 
    "timeout": 300,
    "new_chat": false
}
```

**Parameters:**

-   `prompt` (required): The main prompt text.
-   `system_prompt` (optional): System-level instructions.
-   `provider` (optional): The AI provider to use. Options: `"chatgpt"` (default), `"gemini"`, `"grok"`.
-   `timeout` (optional): Maximum wait time in seconds (30-600).
-   `new_chat` (optional): Force start a new chat session.

**Response:**

```json
{
    "id": "chatcmpl-uuid",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "chatgpt-free",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Quantum computing is..."
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 25,
        "completion_tokens": 100,
        "total_tokens": 125
    }
}

### GET /v1/models

List available models.

### POST /v1/providers/{provider_name}/reset

Reset a specific provider's browser session if it gets stuck.

```bash
curl -X POST http://localhost:8000/v1/providers/chatgpt/reset
```

## Troubleshooting

-   **Browser Issues**: If the browser gets stuck or behaves unexpectedly, use the `/reset` endpoint or restart the server.
-   **Headless Mode**: By default, the browser runs in headless mode. Set `HEADLESS=false` in `.env` to see the browser window for debugging.

## Architecture

The project is structured as follows:

-   `app/main.py`: FastAPI application entry point.
-   `app/core/browser.py`: Manages the `nodriver` browser instance.
-   `app/providers/`: Contains provider-specific logic (ChatGPT, Gemini, Grok).
-   `app/models.py`: Pydantic models for API requests and responses.

## Disclaimer

This project is for educational purposes only. Automating third-party services may violate their Terms of Service. Use responsibly.
