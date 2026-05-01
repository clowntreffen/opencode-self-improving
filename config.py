"""Configuration for opencode-self-improving."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # HuggingFace
    HF_TOKEN = os.getenv("HF_TOKEN", "")
    BUCKET_TYPE = os.getenv("BUCKET_TYPE", "memory")

    # Perplexity (optional)
    PERPLEXITY_ENABLED = os.getenv("PERPLEXITY_ENABLED", "true").lower() == "true"
    PERPLEXITY_URL = os.getenv(
        "PERPLEXITY_URL",
        "https://hermesinho-perplexity-ai.hf.space/gradio_api/mcp/sse"
    )

    # Vikunja (optional)
    VIKUNJA_ENABLED = os.getenv("VIKUNJA_ENABLED", "true").lower() == "true"
    VIKUNJA_URL = os.getenv("VIKUNJA_URL", "http://dietpi:3457/sse")

    # Storage
    HF_BUCKET_PATH = "/data"

    # App
    APP_PORT = int(os.getenv("PORT", "7860"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"


config = Config()