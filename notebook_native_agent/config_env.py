from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

__all__ = ["load_env_file"]

def load_env_file(dotenv_path: str = ".env") -> None:
    """Optionally load environment variables from a local .env file."""
    if load_dotenv is None:
        return
    if not Path(dotenv_path).exists():
        return
    load_dotenv(dotenv_path=dotenv_path, encoding="utf-8", override=False)
    