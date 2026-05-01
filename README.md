# opencode-self-improving

A self-improving MCP agent for [opencode](https://opencode.ai) that learns from errors and applies lessons to avoid repeating mistakes.

## What It Does

- **Validates** API responses (not just HTTP 200 - checks actual content)
- **Learns** from errors so they don't repeat
- **Predicts** the best approach before attempting a task
- **Auto-retries** with fallback strategies
- **Integrates** with Perplexity AI for complex error analysis
- **Tracks** lessons in Vikunja for documentation

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Server (SSE)                      │
│   validate_response | learn | predict | retry | ...     │
└──────────────────────────┬──────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  Learning Engine    Integrations        Storage
  (learn/predict)    (optional)         (pluggable)
                    - Perplexity        - HF Bucket
                    - Vikunja           - In-Memory
```

## Quick Start

### Minimal (no integrations)

```bash
pip install -r requirements.txt
python app.py
```

### With HuggingFace Bucket

```bash
HF_TOKEN=your_token BUCKET_TYPE=hf python app.py
```

### Full Stack

```bash
HF_TOKEN=xxx \
PERPLEXITY_ENABLED=true \
PERPLEXITY_URL=https://your-perplexity-space.hf.space/sse \
VIKUNJA_ENABLED=true \
VIKUNJA_URL=http://dietpi:3457/sse \
BUCKET_TYPE=hf \
python app.py
```

## Integration with opencode

Add to your `opencode.json`:

```json
{
  "mcp": {
    "self-improving": {
      "type": "remote",
      "url": "https://your-space.hf.space/gradio_api/mcp/sse"
    }
  }
}
```

## MCP Tools

### `validate_response`
Validate an API/LLM response for actual content, not just HTTP status.

```
validate_response(response="2", expected="2")
```

### `learn_error`
Learn from an error so it won't repeat.

```
learn_error(
    task_type="file_operations",
    error_pattern="permission_denied",
    root_cause="Writing to /etc without sudo",
    solution="Use sudo -S bash -c 'command'"
)
```

### `predict_approach`
Get the best approach based on learned lessons. Call BEFORE attempting a task.

```
predict_approach(task_type="file_operations", context={"path": "/etc/init/"})
```

### `get_lessons`
List all learned lessons.

```
get_lessons(task_type="api_call")
```

### `retry_with_fallback`
Get a fallback strategy when something fails.

```
retry_with_fallback(
    task_type="api_call",
    error="403 upstream error",
    original_approach="grok-4.20-auto"
)
```

### `analyze_with_perplexity`
Ask Perplexity AI to analyze an error and suggest a fix.

```
analyze_with_perplexity(
    error_type="api_call",
    error_message="403 upstream error"
)
```

### `log_to_vikunja`
Log a lesson to Vikunja for tracking.

```
log_to_vikunja(
    project_id=12,
    title="Lesson: API 403 error",
    description="grok-4.20-auto returns 403, use grok-4.20-fast instead"
)
```

### `get_session_summary`
Get a summary of the current session.

```
get_session_summary()
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | - | HuggingFace token for bucket storage |
| `BUCKET_TYPE` | `memory` | Storage: `hf` or `memory` |
| `PERPLEXITY_ENABLED` | `true` | Enable Perplexity integration |
| `PERPLEXITY_URL` | - | Perplexity MCP URL |
| `VIKUNJA_ENABLED` | `true` | Enable Vikunja integration |
| `VIKUNJA_URL` | - | Vikunja MCP URL |
| `PORT` | `7860` | Server port |
| `DEBUG` | `false` | Debug mode |

## Task Types

- `file_operations` - File creation, editing, permissions
- `api_call` - HTTP requests, API calls
- `tool_execution` - Bash commands, tool calls
- `permission` - Permission/access errors
- `validation` - Input/output validation
- `configuration` - Config setup
- `network` - Network connectivity
- `general` - Everything else

## WebUI

The server includes a Gradio-based web interface with:

- **Dashboard** - System status and learning stats
- **Lessons** - Browse and filter learned lessons
- **Sessions** - View session history
- **Debug** - Test tools manually
- **Settings** - View configuration

## Security

- No passwords or API keys are ever logged or stored in lessons
- All sensitive data is automatically masked (`****`)
- Lessons only store error patterns and solutions, never credentials

## Deploy on HuggingFace Spaces

1. Create a new Space (Gradio SDK, private)
2. Upload all files
3. Set `HF_TOKEN` as a Space secret
4. Enable persistent storage in Space settings
5. Space will be available at `https://your-username-your-space.hf.space`

## License

MIT
