import os
class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///studyhub.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_API_URL = os.environ.get("AI_API_URL", "")
    MAX_CONTENT_LENGTH = 64 *  1024 * 1024
    JEV_API_URL = os.environ.get("JEV_API_URL", "https://ai.hackclub.com/proxy/v1/jev/systemone")
    JEV_API_KEY = os.environ.get("JEV_API_KEY", "REMOVED")
    JEV_MODEL = os.environ.get("JEV_MODEL", "jev-latest")
    AUTO_TAG_MIN = float(os.environ.get("AUTO_TAG_MIN", "0.45"))
    