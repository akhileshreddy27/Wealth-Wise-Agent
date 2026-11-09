import os

# Tests never talk to a real AI provider, even if backend/.env has a key (env vars beat .env).
os.environ["LLM_PROVIDER"] = "none"
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
