# Free Unlimited GPT-4o mini API

## Overview

Why pay for GPT-3.5 API when you can just self host a GPT-4o-mini?

This is a FastAPI-based web service that provides a RESTful API interface to interact with GPT-4o-mini through browser automation. It enables programmatic access to GPT-4o-mini's capabilities without requiring an API key or paid subscription.

Web automation done with [nodriver](https://github.com/ultrafunkamsterdam/nodriver)

## API Documentation

### Endpoints

#### POST /v1/chat/completions  
Creates a chat completion request.

**Request Body:**
```json
{
    "prompt": "Your prompt here",
    "system_prompt": "Optional system prompt",
    "timeout": 300,
    "stream": false, // not yet available
    "new_chat": false
}
```

**Parameters:**
- `prompt` (required): The main prompt text
- `system_prompt` (optional): System-level instructions
- `timeout` (optional): Maximum wait time in seconds (30-600)
- `stream` (optional): Whether to stream responses (not yet available)
- `new_chat` (optional): Force start a new chat

**Response:**
```json
{
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1677610602,
    "model": "chatgpt-free",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Response content here"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30
    }
}
```

#### GET /health
Returns service health status.

**Response:**
```json
{
    "status": "idk what to put here",
    "last_reset": 1677610602,
    "request_count": 5,
    "last_error": null,
    "error_count": 0
}
```

Btw the usage and tokens don't mean anything, i'm just trying out an idea :)


## Setup

### Prerequisites

- Python 3.7 or later
- pip (Python package manager)
- A modern web browser

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Felixdiamond/free-unlimited-gpt4o-mini.git
cd free-unlimited-gpt4o-mini
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running the Server

1. Start the FastAPI server:
```bash
python server.py
```

The server will start at `http://localhost:8000`.

### Running through Terminal

For direct terminal interaction:
```bash
python main.py
```

## Limitations

- Doesn't work on headless mode currently
- Response times may vary
- Browser automation dependent

but hey, we have somewhat unlimited context now!

## Contributing

You can contribute if you see any meaning in this ¯_(ツ)_/¯

## License

This project is licensed under the terms of the LICENSE file included in the repository.
