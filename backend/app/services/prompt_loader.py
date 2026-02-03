import os
from pathlib import Path


def get_prompts_dir() -> Path:
    prompts_dir = os.getenv("PROMPTS_DIR")
    if not prompts_dir:
        raise RuntimeError("PROMPTS_DIR is not set; cannot load prompt files.")
    path = Path(prompts_dir).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"PROMPTS_DIR does not exist: {path}")
    return path


def load_prompt(filename: str) -> str:
    path = get_prompts_dir() / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
