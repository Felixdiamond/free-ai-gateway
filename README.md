# Free AI Gateway

## Overview

Why pay for AI APIs when you can self-host free access?

This project provides a unified RESTful API interface to interact with multiple AI providers (ChatGPT, Gemini, Grok) through browser automation. It enables programmatic access without requiring API keys or paid subscriptions.

Powered by [zendriver](https://github.com/cdpdriver/zendriver).

## Features

-   **Multiple Providers**: Support for ChatGPT, Google Gemini, and Grok.
-   **Unified API**: OpenAI-compatible `chat/completions` endpoint.
-   **Browser Automation**: Uses `zendriver` for stealthy and efficient automation.
-   **Concurrent Requests**: Smart tab management with per-tab locks for true parallelism.
-   **Session Persistence**: Use session IDs to maintain conversation context across requests.
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
    uv sync
    ```
    or
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
    docker compose up -d --build
    ```

2.  The API will be available at `http://localhost:8000`.

3.  **Notes:**
    - This image uses Xvfb (`DISPLAY=:99`) to provide a virtual display for Chromium.
    - Shared memory is increased (`shm_size: 2gb`) to keep Chromium stable.
    - Currently only works with `HEADLESS=False`

4.  **Configuration:**
    Ensure you have a `.env` file created (copy from `.env.example`) before running the container.

## Configuration

1.  Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
2.  Edit `.env` to configure your settings.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HEADLESS` | `False` | Run browser in headless mode |
| `BROWSER_PATH` | auto | Path to Chromium binary |
| `CHATGPT_URL` | `https://chatgpt.com` | ChatGPT URL |
| `GEMINI_URL` | `https://gemini.google.com/app` | Gemini URL |
| `GROK_URL` | `https://grok.com` | Grok URL |
| `TIMEOUT_INPUT` | `10` | Wait time for input fields (seconds) |
| `TIMEOUT_BUTTON` | `5` | Wait time for buttons (seconds) |
| `TIMEOUT_RESPONSE` | `120` | Max wait for AI response (seconds) |
| `TIMEOUT_STABLE_CONTENT` | `30` | Wait for response to stabilize |
| `TAB_INACTIVE_MINUTES` | `10` | Close tabs inactive for this duration |
| `TAB_POOL_SIZE` | `3` | Max anonymous tabs per provider |
| `TAB_CLEANUP_INTERVAL` | `60` | Seconds between cleanup runs |

## Usage

Start the server:

```bash
uvicorn app.main:app
```

The API will be available at `http://localhost:8000`.

## API Endpoints

### POST /v1/chat/completions

Fully compatible with OpenAI's chat completion format.

**Request Body:**

```json
{
    "model": "gpt",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing"}
    ],
    "session_id": "a1b2c3d4e5f6",
    "new_chat": false
}
```

**Supported Models:**

The API uses keyword matching to route requests to the correct provider. You can use any model name containing these keywords:

-   **ChatGPT**: Any model name with `gpt` (e.g., `gpt-5-mini`, `gpt-4o`, `chatgpt-free`)
-   **Gemini**: Any model name with `gemini` (e.g., `gemini-3-flash`, `gemini-pro`)
-   **Grok**: Any model name with `grok` (e.g., `grok-3-mini`, `grok-beta`)

**Parameters:**

-   `model` (required): The ID of the model to use.
-   `messages` (required): A list of messages comprising the conversation so far.
-   `session_id` (optional): Hex string (8-32 chars) to persist conversation across requests. Same session_id = same browser tab = continued conversation.
-   `new_chat` (optional): Set to `true` to force a fresh conversation (reloads the tab).

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
```

### GET /v1/models

List available models.

### POST /v1/providers/{provider_name}/reset

Reset all tabs for a specific provider.

```bash
curl -X POST http://localhost:8000/v1/providers/chatgpt/reset
```

### GET /v1/sessions/{session_id}/status

Check the status of a session's tabs across all providers.

```bash
curl http://localhost:8000/v1/sessions/a1b2c3d4e5f6/status
```

### DELETE /v1/sessions/{session_id}

Close all tabs for a specific session.

```bash
curl -X DELETE http://localhost:8000/v1/sessions/a1b2c3d4e5f6
```

### GET /health

Health check with tab statistics.

```bash
curl http://localhost:8000/health
```

## Session Management

The gateway supports **session-based tab persistence** for multi-user scenarios:

### How It Works

1. **Anonymous Requests**: Without a `session_id`, requests use a shared pool of tabs (first-come-first-served).

2. **Session Requests**: With a `session_id`, you get a dedicated tab that persists your conversation:
   ```bash
   # First message - creates a new tab
   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "gpt", "messages": [{"role": "user", "content": "My name is Alice"}], "session_id": "abc123def456"}'
   
   # Follow-up - same tab, AI remembers context
   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "gpt", "messages": [{"role": "user", "content": "What is my name?"}], "session_id": "abc123def456"}'
   ```

3. **Concurrent Users**: Multiple users with different session IDs can use the gateway simultaneously - each gets their own tab with per-tab locking.

4. **Cleanup**: Inactive session tabs are automatically closed after `TAB_INACTIVE_MINUTES`.

### Session ID Format

- Must be a **hexadecimal string** (0-9, a-f)
- Must be **8-32 characters** long
- Examples: `a1b2c3d4`, `deadbeef12345678`, `abc123def456789012345678`

## Troubleshooting

-   **Browser Issues**: If the browser gets stuck or behaves unexpectedly, use the `/v1/providers/{name}/reset` endpoint or restart the server.
-   **Slow Responses**: Increase timeout values in `.env` for slower networks.
-   **Stale Responses**: The gateway tracks message counts to ensure fresh responses. If issues persist, use `new_chat: true`.

## Architecture

The project is structured as follows:

-   `app/main.py`: FastAPI application entry point.
-   `app/core/browser.py`: Manages the `zendriver` browser instance.
-   `app/core/tab_manager.py`: Smart tab management with session support and pooling.
-   `app/core/config.py`: Configuration via environment variables.
-   `app/providers/`: Contains provider-specific logic (ChatGPT, Gemini, Grok).
-   `app/models.py`: Pydantic models for API requests and responses.

## Disclaimer

This project is for educational purposes only. Automating third-party services may violate their Terms of Service. Use responsibly.
