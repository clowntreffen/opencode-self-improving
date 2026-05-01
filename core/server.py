"""MCP Server - defines all tools for the self-improving agent."""

import json
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from core.learning_engine import LearningEngine, TASK_TYPES
from storage import get_storage
from integrations.perplexity import PerplexityClient
from integrations.vikunja import VikunjaClient
from config import config


def create_server() -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("opencode-self-improving")
    
    storage = get_storage()
    engine = LearningEngine(storage)
    perplexity = PerplexityClient()
    vikunja = VikunjaClient()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="validate_response",
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
                name="learn_error",
                description="Learn from an error so it won't repeat. Stores the error pattern + solution for future predictions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string", "description": "Type: " + ", ".join(TASK_TYPES)},
                        "error_pattern": {"type": "string", "description": "Short error pattern (e.g. 'permission_denied', 'timeout')"},
                        "root_cause": {"type": "string", "description": "Root cause of the error"},
                        "solution": {"type": "string", "description": "Solution that worked"},
                        "context": {"type": "object", "description": "Additional context (optional)"},
                    },
                    "required": ["task_type", "error_pattern", "root_cause", "solution"],
                },
            ),
            Tool(
                name="predict_approach",
                description="Predict the best approach for a task based on learned lessons. Call this BEFORE attempting a task.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string", "description": "Type of task to predict approach for"},
                        "context": {"type": "object", "description": "Context for the prediction (optional)"},
                    },
                    "required": ["task_type"],
                },
            ),
            Tool(
                name="get_lessons",
                description="Get all learned lessons, optionally filtered by task type.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string", "description": "Filter by task type (optional)"},
                    },
                },
            ),
            Tool(
                name="retry_with_fallback",
                description="Get retry suggestion based on error and learned lessons. Returns alternative approach or Perplexity suggestion.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string", "description": "Task type"},
                        "error": {"type": "string", "description": "Error encountered"},
                        "original_approach": {"type": "string", "description": "What was tried originally"},
                    },
                    "required": ["task_type", "error"],
                },
            ),
            Tool(
                name="analyze_with_perplexity",
                description="Analyze an error using Perplexity AI for a suggested fix.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "error_type": {"type": "string", "description": "Type of error"},
                        "error_message": {"type": "string", "description": "Error message"},
                        "context": {"type": "string", "description": "Additional context (optional)"},
                    },
                    "required": ["error_type", "error_message"],
                },
            ),
            Tool(
                name="log_to_vikunja",
                description="Log a lesson or session summary to Vikunja for tracking.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "integer", "description": "Vikunja project ID"},
                        "title": {"type": "string", "description": "Task title"},
                        "description": {"type": "string", "description": "Task description"},
                    },
                    "required": ["project_id", "title", "description"],
                },
            ),
            Tool(
                name="get_session_summary",
                description="Get a summary of the current session - lessons learned, errors, stats.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
        if name == "validate_response":
            response_str = arguments.get("response", "")
            expected = arguments.get("expected")
            
            try:
                response_data = json.loads(response_str)
            except (json.JSONDecodeError, TypeError):
                response_data = response_str
            
            result = engine.validate_response(response_data, expected)
            engine.save_session_event("validation", result)
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "learn_error":
            lesson = engine.learn(
                task_type=arguments["task_type"],
                error_pattern=arguments["error_pattern"],
                root_cause=arguments["root_cause"],
                solution=arguments["solution"],
                context=arguments.get("context"),
            )
            engine.save_session_event("learn", {"lesson_id": lesson["id"]})
            
            return [TextContent(type="text", text=json.dumps({
                "status": "learned",
                "lesson_id": lesson["id"],
                "task_type": lesson["task_type"],
                "solution": lesson["solution"],
            }, indent=2))]

        elif name == "predict_approach":
            prediction = engine.predict(
                task_type=arguments["task_type"],
                context=arguments.get("context"),
            )
            engine.save_session_event("predict", {"task_type": arguments["task_type"]})
            
            if prediction:
                return [TextContent(type="text", text=json.dumps({
                    "status": "prediction_found",
                    **prediction,
                }, indent=2))]
            else:
                return [TextContent(type="text", text=json.dumps({
                    "status": "no_prediction",
                    "message": "No lessons found for this task type",
                }, indent=2))]

        elif name == "get_lessons":
            lessons = engine.get_all_lessons(arguments.get("task_type"))
            return [TextContent(type="text", text=json.dumps({
                "count": len(lessons),
                "lessons": lessons,
            }, indent=2))]

        elif name == "retry_with_fallback":
            task_type = arguments["task_type"]
            error = arguments["error"]
            original = arguments.get("original_approach", "")
            
            # Check lessons first
            prediction = engine.predict(task_type)
            
            if prediction:
                result = {
                    "status": "fallback_from_lessons",
                    "suggested_approach": prediction["suggested_solution"],
                    "confidence": prediction["confidence"],
                }
            else:
                # Try Perplexity
                fix = perplexity.analyze_error(task_type, error, original)
                if fix:
                    result = {
                        "status": "fallback_from_perplexity",
                        "suggested_approach": fix,
                    }
                    # Auto-learn this
                    engine.learn(task_type, "auto_detected", error, fix)
                else:
                    result = {
                        "status": "no_fallback",
                        "message": "No lessons or Perplexity suggestion available",
                    }
            
            engine.save_session_event("retry", result)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "analyze_with_perplexity":
            fix = perplexity.analyze_error(
                error_type=arguments["error_type"],
                error_message=arguments["error_message"],
                context=arguments.get("context", ""),
            )
            
            if fix:
                engine.save_session_event("perplexity_analysis", {"fix": fix[:100]})
                return [TextContent(type="text", text=json.dumps({
                    "status": "analysis_complete",
                    "suggested_fix": fix,
                }, indent=2))]
            else:
                return [TextContent(type="text", text=json.dumps({
                    "status": "analysis_failed",
                    "message": "Perplexity unavailable or no suggestion",
                }, indent=2))]

        elif name == "log_to_vikunja":
            result = vikunja.create_lesson_task(
                project_id=arguments["project_id"],
                title=arguments["title"],
                description=arguments["description"],
            )
            
            if result:
                return [TextContent(type="text", text=json.dumps({
                    "status": "logged",
                    "task_id": result.get("id"),
                }, indent=2))]
            else:
                return [TextContent(type="text", text=json.dumps({
                    "status": "failed",
                    "message": "Vikunja unavailable or not configured",
                }, indent=2))]

        elif name == "get_session_summary":
            stats = engine.get_stats()
            storage_stats = storage.get_stats() if hasattr(storage, 'get_stats') else {}
            perplexity_status = perplexity.status()
            vikunja_status = vikunja.status()
            sessions = storage.get_sessions(limit=50) if storage else []
            
            return [TextContent(type="text", text=json.dumps({
                "learning_stats": stats,
                "storage_stats": storage_stats,
                "sessions_count": len(sessions),
                "perplexity": perplexity_status,
                "vikunja": vikunja_status,
            }, indent=2))]

        return [TextContent(type="text", text="Unknown tool")]

    return server
