import os

# Make sure Settings() never needs a real .env / real secrets to import during tests.
os.environ.setdefault("TRIAGE_PROVIDER", "simulated")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://civicpulse:civicpulse@localhost:5432/civicpulse_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
