"""opencode-self-improving - Self-improving agent for opencode."""

import json
import os
from datetime import datetime

import gradio as gr

from config import config
from storage import get_storage
from core.learning_engine import LearningEngine, TASK_TYPES
from integrations.perplexity import PerplexityClient
from integrations.vikunja import VikunjaClient


storage = get_storage()
engine = LearningEngine(storage)
perplexity = PerplexityClient()
vikunja = VikunjaClient()


def get_dashboard_data():
    stats = engine.get_stats()
    storage_stats = storage.get_stats() if hasattr(storage, 'get_stats') else {}
    perplexity_status = perplexity.status()
    vikunja_status = vikunja.status()
    
    lines = [
        "## System Status\n",
        "| Component | Status |",
        "|-----------|--------|",
        "| Learning Engine | Active |",
        "| Storage | {} ({} lessons) |".format(config.BUCKET_TYPE.upper(), storage_stats.get('lessons_count', 0)),
        "| Perplexity | {} |".format(perplexity_status.get('status', 'unknown')),
        "| Vikunja | {} |".format(vikunja_status.get('status', 'disabled')),
        "",
        "## Learning Stats\n",
        "- **Total Lessons:** {}".format(stats.get('total_lessons', 0)),
    ]
    
    for tt, count in stats.get("by_type", {}).items():
        lines.append("  - {}: {}".format(tt, count))
    
    return "\n".join(lines)


def get_lessons_table(task_type="all"):
    tt = task_type if task_type != "all" else None
    lessons = engine.get_all_lessons(tt)
    
    if not lessons:
        return "No lessons learned yet."
    
    lines = [
        "## Lessons ({})\n".format(len(lessons)),
        "| Type | Error Pattern | Solution | Successes | Last Used |",
        "|------|--------------|----------|-----------|-----------|",
    ]
    
    for l in lessons[:50]:
        solution = l.get("solution", "")[:40]
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                l.get('task_type', ''),
                l.get('error_pattern', ''),
                solution,
                l.get('success_count', 0),
                l.get('last_used', '')[:10],
            )
        )
    
    return "\n".join(lines)


def get_sessions_table():
    sessions = storage.get_sessions(limit=50)
    
    if not sessions:
        return "No sessions recorded yet."
    
    lines = [
        "## Recent Sessions ({})\n".format(len(sessions)),
        "| Time | Event | Details |",
        "|------|-------|---------|",
    ]
    
    for s in sessions[:50]:
        ts = s.get("timestamp", "")[:19]
        event = s.get("event_type", "")
        data = json.dumps(s.get("data", {}))[:60]
        lines.append("| {} | {} | {} |".format(ts, event, data))
    
    return "\n".join(lines)


def debug_validate(response, expected):
    """
    Validate an API/LLM response for actual content, not just HTTP status.
    
    Args:
        response: The response text or JSON to validate
        expected: Expected value to check for (optional)
    
    Returns:
        JSON with valid flag and list of issues
    """
    try:
        response_data = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        response_data = response
    
    result = engine.validate_response(response_data, expected if expected else None)
    engine.save_session_event("validation", result)
    return json.dumps(result, indent=2)


def debug_learn(task_type, error_pattern, root_cause, solution):
    """
    Learn from an error so it won't repeat in the future.
    
    Args:
        task_type: Type of task (file_operations, api_call, tool_execution, etc.)
        error_pattern: Short error pattern (e.g. permission_denied, timeout)
        root_cause: Root cause of the error
        solution: Solution that worked
    
    Returns:
        JSON with lesson ID and status
    """
    lesson = engine.learn(task_type, error_pattern, root_cause, solution)
    engine.save_session_event("learn", {"lesson_id": lesson["id"], "task_type": task_type})
    return json.dumps({
        "status": "learned",
        "lesson_id": lesson["id"],
        "task_type": task_type,
        "solution": solution,
    }, indent=2)


def debug_predict(task_type, context_json):
    """
    Predict the best approach for a task based on learned lessons.
    
    Args:
        task_type: Type of task to predict approach for
        context_json: Additional context as JSON (optional)
    
    Returns:
        JSON with predicted approach or no_prediction status
    """
    try:
        context = json.loads(context_json) if context_json else None
    except json.JSONDecodeError:
        context = {"raw": context_json}
    
    prediction = engine.predict(task_type, context)
    engine.save_session_event("predict", {"task_type": task_type})
    
    if prediction:
        return json.dumps({
            "status": "prediction_found",
            "suggested_solution": prediction["suggested_solution"],
            "confidence": prediction["confidence"],
            "based_on_lessons": prediction["based_on_lessons"],
        }, indent=2)
    return json.dumps({"status": "no_prediction", "message": "No lessons found for this task type"}, indent=2)


def debug_perplexity(error_type, error_message):
    """
    Analyze an error using Perplexity AI for a suggested fix.
    
    Args:
        error_type: Type of error
        error_message: Error message or description
    
    Returns:
        JSON with suggested fix from Perplexity
    """
    fix = perplexity.analyze_error(error_type, error_message)
    if fix:
        engine.save_session_event("perplexity_analysis", {"fix": fix[:100]})
        return json.dumps({"status": "analysis_complete", "suggested_fix": fix}, indent=2)
    return json.dumps({"status": "analysis_failed", "message": "Perplexity unavailable or no suggestion"}, indent=2)


def get_session_summary_api():
    """
    Get a summary of the current session - lessons learned, errors, stats.
    
    Returns:
        JSON with session summary
    """
    stats = engine.get_stats()
    storage_stats = storage.get_stats() if hasattr(storage, 'get_stats') else {}
    return json.dumps({
        "learning_stats": stats,
        "storage_stats": storage_stats,
        "perplexity": perplexity.status(),
        "vikunja": vikunja.status(),
    }, indent=2)


with gr.Blocks(title="opencode-self-improving") as demo:
    gr.Markdown("# opencode-self-improving\nSelf-improving agent that learns from errors.")
    
    with gr.Tabs():
        with gr.Tab("Dashboard"):
            dashboard_out = gr.Markdown(get_dashboard_data())
            gr.Button("Refresh").click(fn=get_dashboard_data, outputs=dashboard_out)
        
        with gr.Tab("Lessons"):
            lesson_filter = gr.Dropdown(
                choices=["all"] + TASK_TYPES,
                value="all",
                label="Filter by Task Type",
            )
            lessons_out = gr.Markdown(get_lessons_table())
            lesson_filter.change(fn=get_lessons_table, inputs=lesson_filter, outputs=lessons_out)
            gr.Button("Refresh").click(fn=get_lessons_table, inputs=lesson_filter, outputs=lessons_out)
        
        with gr.Tab("Sessions"):
            sessions_out = gr.Markdown(get_sessions_table())
            gr.Button("Refresh").click(fn=get_sessions_table, outputs=sessions_out)
        
        with gr.Tab("Debug"):
            gr.Markdown("### Validate Response")
            with gr.Row():
                val_input = gr.Textbox(label="Response", placeholder="Enter response text or JSON")
                val_expected = gr.Textbox(label="Expected (optional)", placeholder="e.g. '2'")
            val_btn = gr.Button("Validate")
            val_out = gr.JSON(label="Result")
            val_btn.click(fn=debug_validate, inputs=[val_input, val_expected], outputs=val_out)
            
            gr.Markdown("---\n### Predict Approach")
            with gr.Row():
                pred_type = gr.Dropdown(choices=TASK_TYPES, label="Task Type")
                pred_ctx = gr.Textbox(label="Context JSON (optional)", placeholder='{"path": "/etc/..."}')
            pred_btn = gr.Button("Predict")
            pred_out = gr.JSON(label="Result")
            pred_btn.click(fn=debug_predict, inputs=[pred_type, pred_ctx], outputs=pred_out)
            
            gr.Markdown("---\n### Learn Error")
            with gr.Row():
                learn_type = gr.Dropdown(choices=TASK_TYPES, label="Task Type")
                learn_error = gr.Textbox(label="Error Pattern", placeholder="e.g. permission_denied")
            with gr.Row():
                learn_cause = gr.Textbox(label="Root Cause")
                learn_solution = gr.Textbox(label="Solution")
            learn_btn = gr.Button("Learn")
            learn_out = gr.JSON(label="Result")
            learn_btn.click(
                fn=debug_learn,
                inputs=[learn_type, learn_error, learn_cause, learn_solution],
                outputs=learn_out,
            )
            
            gr.Markdown("---\n### Perplexity Analysis")
            with gr.Row():
                px_type = gr.Textbox(label="Error Type")
                px_msg = gr.Textbox(label="Error Message")
            px_btn = gr.Button("Analyze")
            px_out = gr.JSON(label="Result")
            px_btn.click(fn=debug_perplexity, inputs=[px_type, px_msg], outputs=px_out)
        
        with gr.Tab("Settings"):
            gr.Markdown("### Configuration\n")
            gr.JSON(value={
                "bucket_type": config.BUCKET_TYPE,
                "perplexity_enabled": config.PERPLEXITY_ENABLED,
                "perplexity_status": perplexity.status(),
                "vikunja_enabled": config.VIKUNJA_ENABLED,
                "vikunja_status": vikunja.status(),
                "debug": config.DEBUG,
            })


import os
os.environ.pop("GRADIO_MCP_SERVER", None)

from core.mcp_sse import mount_mcp
app, _, _ = demo.launch(server_name="0.0.0.0", server_port=7860, prevent_thread_lock=True)
mount_mcp(app)

import time
while True:
    time.sleep(3600)
