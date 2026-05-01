"""Custom MCP SSE server - bypasses broken Gradio MCP."""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from config import config
from storage import get_storage
from core.learning_engine import LearningEngine, TASK_TYPES
from integrations.perplexity import PerplexityClient
from integrations.vikunja import VikunjaClient

storage = get_storage()
engine = LearningEngine(storage)
perplexity = PerplexityClient()
vikunja = VikunjaClient()


TOOLS = [
    {
        "name": "debug_validate",
        "description": "Validate an LLM/API response - checks for errors, empty responses, expected values. Use this after every API call to verify the response is actually valid, not just HTTP 200.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "response": {"type": "string", "description": "The response to validate (string or JSON string)"},
                "expected": {"type": "string", "description": "Expected value to check for (optional)"},
            },
            "required": ["response"],
        },
    },
    {
        "name": "debug_learn",
        "description": "Learn from an error so it won't repeat. Stores the error pattern + solution for future predictions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "description": "Type: " + ", ".join(TASK_TYPES)},
                "error_pattern": {"type": "string", "description": "Short error pattern (e.g. 'permission_denied', 'timeout')"},
                "root_cause": {"type": "string", "description": "Root cause of the error"},
                "solution": {"type": "string", "description": "Solution that worked"},
            },
            "required": ["task_type", "error_pattern", "root_cause", "solution"],
        },
    },
    {
        "name": "debug_predict",
        "description": "Predict the best approach for a task based on learned lessons. Call this BEFORE attempting a task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "description": "Type of task to predict approach for"},
                "context": {"type": "string", "description": "Additional context as JSON (optional)"},
            },
            "required": ["task_type"],
        },
    },
    {
        "name": "debug_perplexity",
        "description": "Analyze an error using Perplexity AI for a suggested fix.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_type": {"type": "string", "description": "Type of error"},
                "error_message": {"type": "string", "description": "Error message or description"},
            },
            "required": ["error_type", "error_message"],
        },
    },
    {
        "name": "get_dashboard_data",
        "description": "Get a summary of the current session - lessons learned, errors, stats.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "debug_validate":
        response_str = args.get("response", "")
        expected = args.get("expected")
        try:
            response_data = json.loads(response_str)
        except (json.JSONDecodeError, TypeError):
            response_data = response_str
        result = engine.validate_response(response_data, expected)
        engine.save_session_event("validation", result)
        return result

    elif name == "debug_learn":
        lesson = engine.learn(
            task_type=args["task_type"],
            error_pattern=args["error_pattern"],
            root_cause=args["root_cause"],
            solution=args["solution"],
        )
        engine.save_session_event("learn", {"lesson_id": lesson["id"], "task_type": args["task_type"]})
        return {
            "status": "learned",
            "lesson_id": lesson["id"],
            "task_type": lesson["task_type"],
            "solution": lesson["solution"],
        }

    elif name == "debug_predict":
        context = None
        ctx_str = args.get("context", "")
        if ctx_str:
            try:
                context = json.loads(ctx_str)
            except (json.JSONDecodeError, TypeError):
                context = {"raw": ctx_str}
        prediction = engine.predict(args["task_type"], context)
        engine.save_session_event("predict", {"task_type": args["task_type"]})
        if prediction:
            return {
                "status": "prediction_found",
                "suggested_solution": prediction["suggested_solution"],
                "confidence": prediction["confidence"],
                "based_on_lessons": prediction["based_on_lessons"],
            }
        return {"status": "no_prediction", "message": "No lessons found for this task type"}

    elif name == "debug_perplexity":
        fix = perplexity.analyze_error(args["error_type"], args["error_message"])
        if fix:
            engine.save_session_event("perplexity_analysis", {"fix": fix[:100]})
            return {"status": "analysis_complete", "suggested_fix": fix}
        return {"status": "analysis_failed", "message": "Perplexity unavailable or no suggestion"}

    elif name == "get_dashboard_data":
        stats = engine.get_stats()
        storage_stats = storage.get_stats() if hasattr(storage, "get_stats") else {}
        return {
            "learning_stats": stats,
            "storage_stats": storage_stats,
            "perplexity": perplexity.status(),
            "vikunja": vikunja.status(),
        }

    return {"error": "Unknown tool: " + name}


class SSEClient:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.id = str(uuid.uuid4())[:8]


_clients: Dict[str, SSEClient] = {}


async def _send_to_client(client: SSEClient, data: dict):
    await client.queue.put(data)


def _jsonrpc_response(request_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


async def handle_sse(request: Request) -> StreamingResponse:
    client = SSEClient()
    _clients[client.id] = client

    messages_url = str(request.url.replace(query=None)).replace("/sse", "/messages")

    async def event_stream():
        yield "event: endpoint\ndata: {}\n\n".format(messages_url)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(client.queue.get(), timeout=30)
                    yield "event: message\ndata: {}\n\n".format(json.dumps(msg))
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _clients.pop(client.id, None)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


async def handle_messages(request: Request) -> Response:
    body = await request.json()
    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "opencode-self-improving",
                "version": "1.0.0",
            },
        }
    elif method == "notifications/initialized":
        return Response(status_code=204)
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            tool_result = _call_tool(tool_name, tool_args)
            result = {
                "content": [{"type": "text", "text": json.dumps(tool_result)}],
                "isError": False,
            }
        except Exception as e:
            result = {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                "isError": True,
            }
    else:
        resp = _jsonrpc_error(req_id, -32601, "Method not found: " + method)
        return Response(content=json.dumps(resp), media_type="application/json")

    resp = _jsonrpc_response(req_id, result)

    for cid, cl in list(_clients.items()):
        await _send_to_client(cl, resp)

    return Response(content=json.dumps(resp), media_type="application/json")


def mount_mcp(app):
    """Mount custom MCP SSE endpoints on a FastAPI/Starlette app."""
    app.add_route("/gradio_api/mcp/sse", handle_sse, methods=["GET"])
    app.add_route("/gradio_api/mcp/messages", handle_messages, methods=["POST"])
