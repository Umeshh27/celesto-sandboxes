import os
import logging
import httpx
from typing import Optional, Dict, Any

logger = logging.getLogger("celesto_agent.ledger")

class LedgerClient:
    """Client for logging sandbox runs to the Celesto Run Ledger API."""
    def __init__(self, api_url: Optional[str] = None):
        base = api_url or os.getenv("LEDGER_API_URL") or "http://localhost:8080"
        self.api_url = base.rstrip("/")
        self.client = httpx.Client(timeout=3.0)

    def record_run(self, run_id: str, sandbox_name: str, problem_id: str, state: str) -> bool:
        payload = {
            "run_id": run_id,
            "sandbox_name": sandbox_name,
            "problem_id": problem_id,
            "state": state,
            "execution_target": "celesto_sandbox"
        }
        try:
            resp = self.client.post(f"{self.api_url}/api/runs", json=payload)
            if resp.status_code in (200, 201):
                return True
            else:
                logger.warning(f"Ledger record rejected ({resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            # Fallback when API service is offline or in unit tests
            logger.debug(f"Direct ledger update skipped (service offline): {e}")
            return False

    def record_state(self, sandbox_name: str, state: str) -> bool:
        run_id = f"run-{sandbox_name}"
        return self.record_run(run_id, sandbox_name, "suspicious_package_detonation", state)
