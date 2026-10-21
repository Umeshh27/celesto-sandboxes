import os
import re
from typing import List, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from src.api.schemas import RunCreate, RunRecord, SANDBOX_REGEX, ALLOWED_STATES
from src.api.db import init_db, list_runs, insert_run

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Attempt DB init on startup
    init_db()
    yield

app = FastAPI(
    title="Celesto Run Ledger API",
    description="Control plane ledger for auditing AI agent sandbox runs in isolated microVMs",
    version="1.0.0",
    lifespan=lifespan
)

# Custom validation error handler to ensure 400 is returned instead of 422
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Validation error", "errors": errors}
    )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/runs", response_model=List[Dict[str, Any]])
async def get_runs():
    runs = list_runs()
    return runs

@app.post("/api/runs", status_code=status.HTTP_201_CREATED)
async def create_run(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload"
        )

    # Validate required fields
    required_fields = ["run_id", "sandbox_name", "problem_id", "state", "execution_target"]
    for field in required_fields:
        if field not in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}"
            )

    sandbox_name = body["sandbox_name"]
    state = body["state"]
    execution_target = body["execution_target"]

    if not isinstance(sandbox_name, str) or not SANDBOX_REGEX.match(sandbox_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"sandbox_name '{sandbox_name}' must start with 'sbx-' followed by at least 8 lowercase alphanumeric characters."
        )

    if not isinstance(state, str) or state.lower() not in ALLOWED_STATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state '{state}'. Must be one of: {sorted(ALLOWED_STATES)}"
        )

    if execution_target != "celesto_sandbox":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid execution_target '{execution_target}'. Only 'celesto_sandbox' is permitted."
        )

    run_record = insert_run({
        "run_id": str(body["run_id"]),
        "sandbox_name": str(sandbox_name),
        "problem_id": str(body["problem_id"]),
        "state": str(state.lower()),
        "execution_target": str(execution_target)
    })

    return run_record

# Mount static directories if they exist
reports_dir = os.path.join(os.getcwd(), "reports")
demo_dir = os.path.join(os.getcwd(), "demo")
if os.path.isdir(reports_dir):
    app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")
if os.path.isdir(demo_dir):
    app.mount("/demo", StaticFiles(directory=demo_dir), name="demo")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=port, reload=False)
