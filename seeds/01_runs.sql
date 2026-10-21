-- Seed file for Celesto Run Ledger database
-- Mounted to /docker-entrypoint-initdb.d on container initialization

CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR(255) PRIMARY KEY,
    sandbox_name VARCHAR(255) NOT NULL UNIQUE,
    problem_id VARCHAR(255) NOT NULL,
    state VARCHAR(50) NOT NULL,
    execution_target VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed row required by specification:
-- Sandbox name: sbx-seeddemo1
-- State: deleted
-- Execution target: celesto_sandbox
-- Re-running the SQL does not duplicate it.
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
