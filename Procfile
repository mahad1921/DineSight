# Start the FastAPI app. Railway sets PORT; default 8000 for local.
# Must bind to 0.0.0.0 so the app is reachable from outside the container.
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
