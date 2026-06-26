# ConvoKit backend — FastAPI application entry point.
#
# Scaffold stage: only exposes a health check endpoint. Business logic
# (convocatorias, document extraction, Claude generation) is added in later
# implementation steps as described in CLAUDE.md.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ConvoKit API")

# Allow the frontend (Vite dev server / Vercel deployment) to call the API.
# Open during the MVP since the app is internal and has no authentication.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check used by the frontend to verify backend connectivity."""
    return {"status": "ok"}
