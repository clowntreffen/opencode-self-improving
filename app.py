"""opencode-self-improving - Self-improving agent for opencode."""

import json
import os

import gradio as gr


def get_dashboard_data():
    return "## System Status\n\n| Component | Status |\n|-----------|--------|\n| App | Running |\n| Version | 0.1.0 |"


def get_lessons_table(task_type="all"):
    return "No lessons learned yet."


def get_sessions_table():
    return "No sessions recorded yet."


def debug_validate(response, expected):
    try:
        response_data = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        response_data = response
    
    result = {"valid": True, "issues": []}
    if not response:
        result["valid"] = False
        result["issues"].append("Empty response")
    if expected and expected.lower() not in str(response).lower():
        result["valid"] = False
        result["issues"].append("Expected '" + expected + "' not found")
    return json.dumps(result, indent=2)


def debug_learn(task_type, error_pattern, root_cause, solution):
    return json.dumps({"status": "learned", "task_type": task_type, "solution": solution}, indent=2)


def debug_predict(task_type, context_json):
    return json.dumps({"status": "no_prediction", "message": "No lessons found"}, indent=2)


def debug_perplexity(error_type, error_message):
    return json.dumps({"status": "ok", "suggested_fix": "Not connected yet"}, indent=2)


TASK_TYPES = [
    "file_operations", "api_call", "tool_execution",
    "permission", "validation", "configuration", "network", "general",
]


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
                val_input = gr.Textbox(label="Response")
                val_expected = gr.Textbox(label="Expected (optional)")
            val_btn = gr.Button("Validate")
            val_out = gr.JSON(label="Result")
            val_btn.click(fn=debug_validate, inputs=[val_input, val_expected], outputs=val_out)
            
            gr.Markdown("---\n### Learn Error")
            with gr.Row():
                learn_type = gr.Dropdown(choices=TASK_TYPES, label="Task Type")
                learn_error = gr.Textbox(label="Error Pattern")
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
            
            gr.Markdown("---\n### Predict Approach")
            with gr.Row():
                pred_type = gr.Dropdown(choices=TASK_TYPES, label="Task Type")
                pred_ctx = gr.Textbox(label="Context JSON (optional)")
            pred_btn = gr.Button("Predict")
            pred_out = gr.JSON(label="Result")
            pred_btn.click(fn=debug_predict, inputs=[pred_type, pred_ctx], outputs=pred_out)
            
            gr.Markdown("---\n### Perplexity Analysis")
            with gr.Row():
                px_type = gr.Textbox(label="Error Type")
                px_msg = gr.Textbox(label="Error Message")
            px_btn = gr.Button("Analyze")
            px_out = gr.JSON(label="Result")
            px_btn.click(fn=debug_perplexity, inputs=[px_type, px_msg], outputs=px_out)
        
        with gr.Tab("Settings"):
            gr.Markdown("### Configuration\n")
            gr.JSON(value={"status": "minimal_mode", "message": "Core modules not loaded"})


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
