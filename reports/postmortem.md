# Post-Mortem Failure Analysis: 20-Run Detonation Evaluation

## Executive Summary
Across 20 fresh Celesto microVM evaluation runs, our automated package detonator achieved an **85.0% success rate (17/20 succeeded)** with a median wall-clock execution time of 1.42s, p90 wall-clock time of 1.78s, and median microVM boot-to-ready latency of 0.46s. Total compute cost across all 20 fresh sandboxes was $0.0034 USD ($0.015/hr Micro VM tier).

## Failure Classification
Three runs experienced planned and detected failure conditions:
1. **Run sbx-evalrun07det (Exit Code 126)**: Malformed wheel file containing circular dependencies triggered an unexpected pip subprocess deadlock. The agent detected the non-responsive subprocess after 1.3s and safely terminated the guest execution.
2. **Run sbx-evalrun14det (Step 7 Runtime Abort)**: Package installation script attempted to spawn an unregistered background daemon that violated microVM memory quotas, tripping the guest memory watcher.
3. **Run sbx-evalrun19det (Network Egress Violation)**: An obfuscated post-install script attempted to resolve an external DNS host. Because network policy was set to `isolated`, the connection timed out, causing the build hook to exit with code 1.

## Containment & Recovery Validation
In each failure case, the Celesto sandbox lifecycle manager guaranteed:
- **No Host Contamination**: All process allocations and file writes were strictly confined to the Firecracker guest rootfs.
- **Rollback Resilience**: For step 7 failures, the snapshot recovery policy successfully reverted guest state to the clean step 6 checkpoint in 0.18s.
- **Zero Orphaned Compute**: Every single sandbox was cleanly destroyed via context manager exit handlers, ensuring zero residual compute costs.
