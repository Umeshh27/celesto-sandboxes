import os
import logging
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("celesto_ledger.db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ledger:ledger@ledger:5432/ledger")

# Fallback store if running in lightweight standalone test mode
_IN_MEMORY_RUNS: List[Dict[str, Any]] = [
    {
        "run_id": "seed-run-init-001",
        "sandbox_name": "sbx-seeddemo1",
        "problem_id": "detonation-seed-problem",
        "state": "deleted",
        "execution_target": "celesto_sandbox",
        "created_at": "2026-10-21T12:00:00Z",
        "updated_at": "2026-10-21T12:00:00Z",
    }
]

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=3)

def init_db():
    """Ensure table exists and seed is present."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS runs (
                        run_id VARCHAR(255) PRIMARY KEY,
                        sandbox_name VARCHAR(255) NOT NULL UNIQUE,
                        problem_id VARCHAR(255) NOT NULL,
                        state VARCHAR(50) NOT NULL,
                        execution_target VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at)
                    VALUES (
                        'seed-run-init-001',
                        'sbx-seeddemo1',
                        'detonation-seed-problem',
                        'deleted',
                        'celesto_sandbox',
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (sandbox_name) DO NOTHING;
                """)
                conn.commit()
                logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database connection skipped during init: {e}")

def list_runs() -> List[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at FROM runs ORDER BY created_at ASC;")
                rows = cur.fetchall()
                results = []
                for row in rows:
                    item = dict(row)
                    if item.get("created_at"):
                        item["created_at"] = item["created_at"].isoformat()
                    if item.get("updated_at"):
                        item["updated_at"] = item["updated_at"].isoformat()
                    results.append(item)
                return results
    except Exception as e:
        logger.warning(f"Falling back to in-memory store for list_runs: {e}")
        return list(_IN_MEMORY_RUNS)

def insert_run(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at)
                    VALUES (%(run_id)s, %(sandbox_name)s, %(problem_id)s, %(state)s, %(execution_target)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (sandbox_name) DO UPDATE SET
                        state = EXCLUDED.state,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING run_id, sandbox_name, problem_id, state, execution_target, created_at, updated_at;
                """, data)
                row = cur.fetchone()
                conn.commit()
                result = dict(row)
                if result.get("created_at"):
                    result["created_at"] = result["created_at"].isoformat()
                if result.get("updated_at"):
                    result["updated_at"] = result["updated_at"].isoformat()
                return result
    except Exception as e:
        logger.warning(f"Recording run in memory fallback due to DB error: {e}")
        # update or insert in memory
        for r in _IN_MEMORY_RUNS:
            if r["sandbox_name"] == data["sandbox_name"]:
                r.update(data)
                return r
        _IN_MEMORY_RUNS.append(data)
        return data
