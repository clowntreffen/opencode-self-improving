"""MCP Server using the official mcp library - proper protocol implementation."""

import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

from config import config
from storage import get_storage
from core.learning_engine import LearningEngine, TASK_TYPES
from integrations.perplexity import PerplexityClient
from integrations.vikunja import VikunjaClient


storage = get_storage()
engine = LearningEngine(storage)
perplexity = PerplexityClient()
vikunja = VikunjaClient()

server = Server("opencode-self-improving")
sse_transport = SseServerTransport("/gradio_api/mcp/messages")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="debug_validate",
            description="Validate an LLM/API response - checks for errors, empty responses, expected values. Use this after every API call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "response": {"type": "string", "description": "The response to validate (string or JSON string)"},
                    "expected": {"type": "string", "description": "Expected value to check for (optional)"},
                },
                "required": ["response"],
            },
        ),
        Tool(
            name="debug_learn",
            description="Learn from an error so it won't repeat. Stores error pattern + solution for future predictions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_type": {"type": "string", "description": "Type: " + ", ".join(TASK_TYPES)},
                    "error_pattern": {"type": "string", "description": "Short error pattern (e.g. 'permission_denied', 'timeout')"},
                    "root_cause": {"type": "string", "description": "Root cause of the error"},
                    "solution": {"type": "string", "description": "Solution that worked"},
                },
                "required": ["task_type", "error_pattern", "root_cause", "solution"],
            },
        ),
        Tool(
            name="debug_predict",
            description="Predict the best approach for a task based on learned lessons. Call BEFORE attempting a task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_type": {"type": "string", "description": "Task type to predict approach for"},
                    "context": {"type": "string", "description": "Additional context as JSON (optional)"},
                },
                "required": ["task_type"],
            },
        ),
        Tool(
            name="debug_perplexity",
            description="Analyze an error using Perplexity AI for a suggested fix.",
            inputSchema={
                "type": "object",
                "properties": {
                    "error_type": {"type": "string", "description": "Type of error"},
                    "error_message": {"type": "string", "description": "Error message or description"},
                },
                "required": ["error_type", "error_message"],
            },
        ),
        Tool(
            name="get_dashboard_data",
            description="Get session summary - lessons learned, errors, stats.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


def _call_tool(name: str, args: dict) -> list:
    if name == "debug_validate":
        response_str = args.get("response", "")
        expected = args.get("expected")
        try:
            response_data = json.loads(response_str)
        except (json.JSONDecodeError, TypeError):
            response_data = response_str
        result = engine.validate_response(response_data, expected)
        engine.save_session_event("validation", result)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "debug_learn":
        lesson = engine.learn(
            task_type=args["task_type"],
            error_pattern=args["error_pattern"],
            root_cause=args["root_cause"],
            solution=args["solution"],
        )
        engine.save_session_event("learn", {"lesson_id": lesson["id"]})
        return [TextContent(type="text", text=json.dumps({
            "status": "learned",
            "lesson_id": lesson["id"],
            "task_type": lesson["task_type"],
            "solution": lesson["solution"],
        }, indent=2))]

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
            return [TextContent(type="text", text=json.dumps({
                "status": "prediction_found",
                "suggested_solution": prediction["suggested_solution"],
                "confidence": prediction["confidence"],
                "based_on_lessons": prediction["based_on_lessons"],
            }, indent=2))]
        return [TextContent(type="text", text=json.dumps({
            "status": "no_prediction",
            "message": "No lessons found for this task type",
        }, indent=2))]

    elif name == "debug_perplexity":
        fix = perplexity.analyze_error(args["error_type"], args["error_message"])
        if fix:
            engine.save_session_event("perplexity_analysis", {"fix": fix[:100]})
            return [TextContent(type="text", text=json.dumps({
                "status": "analysis_complete",
                "suggested_fix": fix,
            }, indent=2))]
        return [TextContent(type="text", text=json.dumps({
            "status": "analysis_failed",
            "message": "Perplexity unavailable or no suggestion",
        }, indent=2))]

    elif name == "get_dashboard_data":
        stats = engine.get_stats()
        storage_stats = storage.get_stats() if hasattr(storage, "get_stats") else {}
        return [TextContent(type="text", text=json.dumps({
            "learning_stats": stats,
            "storage_stats": storage_stats,
            "perplexity": perplexity.status(),
            "vikunja": vikunja.status(),
        }, indent=2))]

    return [TextContent(type="text", text=json.dumps({"error": "Unknown tool: " + name}))]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    try:
        return _call_tool(name, arguments)
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


def mount_mcp(app):
    """Mount MCP SSE server using official mcp library."""
    from starlette.requests import Request
    from starlette.responses import Response

    async def handle_sse(request: Request):
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    async def handle_post(request: Request):
        await sse_transport.handle_post_message(request.scope, request.receive, request._send)

    app.add_route("/gradio_api/mcp/sse", handle_sse, methods=["GET"])
    app.add_route("/gradio_api/mcp/messages", handle_post, methods=["POST"])
    app.add_route("/gradio_api/mcp/sse", handle_post, methods=["POST"])
