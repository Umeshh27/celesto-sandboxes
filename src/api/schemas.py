import re
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

SANDBOX_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")
ALLOWED_STATES = {"created", "ready", "running", "succeeded", "failed", "deleted"}

class RunCreate(BaseModel):
    run_id: str = Field(..., min_length=1, description="Unique identifier for the run")
    sandbox_name: str = Field(..., description="Sandbox identifier starting with sbx- and >= 8 lowercase alphanumeric chars")
    problem_id: str = Field(..., min_length=1, description="Identifier for the problem being evaluated")
    state: str = Field(..., description="Lifecycle state of the sandbox run")
    execution_target: str = Field(..., description="Must strictly be celesto_sandbox")

    @field_validator("sandbox_name")
    def validate_sandbox_name(cls, v: str) -> str:
        if not SANDBOX_REGEX.match(v):
            raise ValueError(
                f"sandbox_name '{v}' is invalid; must match pattern '^sbx-[a-z0-9]{{8,}}$'"
            )
        return v

    @field_validator("state")
    def validate_state(cls, v: str) -> str:
        state_lower = v.lower()
        if state_lower not in ALLOWED_STATES:
            raise ValueError(
                f"Invalid state '{v}'. Must be one of: {sorted(ALLOWED_STATES)}"
            )
        return state_lower

    @field_validator("execution_target")
    def validate_execution_target(cls, v: str) -> str:
        if v != "celesto_sandbox":
            raise ValueError(
                f"Invalid execution_target '{v}'. Execution target must strictly be 'celesto_sandbox'"
            )
        return v

class RunRecord(BaseModel):
    run_id: str
    sandbox_name: str
    problem_id: str
    state: str
    execution_target: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
