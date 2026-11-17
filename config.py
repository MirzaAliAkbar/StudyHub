import os


def _load_env_file(path=".env"):
    """Read KEY=VALUE lines from .env so no extra package is needed."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env_file()


def _database_url():
    url = os.environ.get("DATABASE_URL", "sqlite:///studyhub.db")
    if url.startswith("postgres://"):          # hosted providers still hand this out
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_API_URL = os.environ.get("AI_API_URL", "")
    MAX_CONTENT_LENGTH = 64 * 1024 * 1024
    JEV_API_URL = os.environ.get("JEV_API_URL", "https://ai.hackclub.com/proxy/v1/jev/systemone")
    JEV_API_KEY = os.environ.get("JEV_API_KEY", "")
    JEV_MODEL = os.environ.get("JEV_MODEL", "jev-latest")
    AUTO_TAG_MIN = float(os.environ.get("AUTO_TAG_MIN", "0.45"))
