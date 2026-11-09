"""Explicit local launcher: python -m backend [--env-file PATH].

The selected local file overrides inherited settings for this child process only.
Direct uvicorn launches continue to use deployment-provided environment variables.
"""
import argparse
from pathlib import Path
from dotenv import load_dotenv
import uvicorn

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

def start(env_file: Path = DEFAULT_ENV_FILE) -> None:
    env_file = Path(env_file).resolve()
    if not env_file.is_file():
        raise FileNotFoundError("Local backend environment file does not exist.")
    load_dotenv(dotenv_path=env_file, override=True)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the local backend with a selected environment file.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    start(parser.parse_args().env_file)
