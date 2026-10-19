import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if it exists
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

class Settings:
    # Project paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    DOCS_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = BASE_DIR / "data" / "task_assistant.db"
    CHROMA_DIR: Path = BASE_DIR / "data" / "chroma_db"

    # AI / LLM Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

    # SMTP Configuration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "assistant@taskagent.local")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")
    DEV_EMAIL: str = os.getenv("DEV_EMAIL", "developer@company.com")

    # Scheduler Configuration (Daily morning scan)
    REMINDER_HOUR: int = int(os.getenv("REMINDER_HOUR", "9"))
    REMINDER_MINUTE: int = int(os.getenv("REMINDER_MINUTE", "0"))

    # Server configuration
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    @classmethod
    def ensure_directories(cls):
        """Ensure necessary directories exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def update_setting(cls, key: str, value: str):
        """Update in-memory setting and save to .env file."""
        setattr(cls, key, value)
        os.environ[key] = str(value)
        
        # Also update or append in .env file
        env_lines = []
        if ENV_PATH.exists():
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                env_lines = f.readlines()

        found = False
        new_lines = []
        for line in env_lines:
            if line.strip().startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(f"{key}={value}\n")

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

# Initialize directories
settings = Settings()
settings.ensure_directories()
