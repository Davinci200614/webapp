import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


APP_NAME = os.getenv("APP_NAME", "MACHINATI × Nouba")
DB_PATH = os.getenv("DB_PATH", "webapp.db")
CORS_ORIGINS = _origins(os.getenv("CORS_ORIGINS", "http://localhost:5173"))

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "")
GEMINI_STT_MODEL = os.getenv("GEMINI_STT_MODEL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
LLM_FALLBACK_PROVIDER = os.getenv("LLM_FALLBACK_PROVIDER", "").strip().lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
CONVERSATION_CORE = os.getenv("CONVERSATION_CORE", "v2").strip().lower()
CONVERSATION_REPLY_STYLE = os.getenv("CONVERSATION_REPLY_STYLE", "model").strip().lower()
CONVERSATION_REPLY_TIMEOUT_SECONDS = float(os.getenv("CONVERSATION_REPLY_TIMEOUT_SECONDS", "4"))
CONVERSATION_ROUTING = os.getenv("CONVERSATION_ROUTING", "model_first").strip().lower()
CONVERSATION_PROVIDER = os.getenv("CONVERSATION_PROVIDER", "auto").strip().lower()
CONVERSATION_ENABLED = os.getenv("CONVERSATION_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OPERATOR_API_KEY = os.getenv("OPERATOR_API_KEY", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
AUTH_BOOTSTRAP_EMAIL = os.getenv("AUTH_BOOTSTRAP_EMAIL", "").strip().lower()
AUTH_BOOTSTRAP_PASSWORD = os.getenv("AUTH_BOOTSTRAP_PASSWORD", "")
AUTH_SESSION_TTL_HOURS = int(os.getenv("AUTH_SESSION_TTL_HOURS", "12"))
MUTATIONS_ENABLED = os.getenv("MUTATIONS_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
CONVERSATION_MODEL = os.getenv("CONVERSATION_MODEL", "")
CONVERSATION_GEMINI_MODEL = os.getenv("CONVERSATION_GEMINI_MODEL", GEMINI_MODEL)
CONVERSATION_TIMEOUT_SECONDS = float(os.getenv("CONVERSATION_TIMEOUT_SECONDS", "6"))
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "35"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "1024"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "180"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "2m")
STT_PROVIDER = os.getenv("STT_PROVIDER", "openai").strip().lower()
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Nouba service compatibility; all settings still come from this application.
CONVERSATION_THINKING_LEVEL = os.getenv("CONVERSATION_THINKING_LEVEL", "minimal")
INSPECTOR_ENABLED = os.getenv("INSPECTOR_ENABLED", "false").lower() in {"true", "1", "yes"}
WHATSAPP_CONTACT_NUMBER = os.getenv("WHATSAPP_CONTACT_NUMBER", "")

def resolve_db_path(value):
    path = Path(value).expanduser()
    return str((path if path.is_absolute() else Path(__file__).resolve().parents[1] / path).resolve())

DOCUMENT_CHECKLIST = os.getenv("DOCUMENT_CHECKLIST", "ملخص طلب الخدمة (الاسم، المكان، نوع الخدمة والتاريخ);تصريح بطبيعة الأشغال ومكانها;وثيقة تمثيل التعاونية إذا كان الطلب باسمها، عند الاقتضاء;وثيقة استغلال الأرض لطلب المعدات، عند الاقتضاء")
WHATSAPP_DOCUMENT_TEMPLATE = os.getenv("WHATSAPP_DOCUMENT_TEMPLATE", "").strip()
WHATSAPP_TEMPLATE_LANGUAGE = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "ar").strip()

PUBLIC_DEMO_MODE = os.getenv("PUBLIC_DEMO_MODE", "false").strip().lower() in {"1","true","yes","on"}
