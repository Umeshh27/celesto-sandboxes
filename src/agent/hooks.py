import re
import logging
from typing import Tuple

logger = logging.getLogger("celesto_agent.hooks")

# Dangerous patterns to intercept before reaching the microVM guest
BLOCKED_PATTERNS = [
    re.compile(r"curl\s+.*(webhook|attacker|exfil|burpcollaborator|oast|pastebin|ngrok|transfer\.sh|bashupload)", re.IGNORECASE),
    re.compile(r"cat\s+.*\.env.*\|\s*(curl|nc|wget|socat)", re.IGNORECASE),
    re.compile(r"rm\s+-rf\s+(/|/etc|/boot|/sys|/proc|/home)", re.IGNORECASE),
    re.compile(r"chmod\s+777\s+/etc/shadow", re.IGNORECASE),
    re.compile(r":\(\)\{\s*:\|:&\s*\};:", re.IGNORECASE), # fork bomb
    re.compile(r"nc\s+-e\s+/bin/(ba)?sh", re.IGNORECASE), # reverse shell
    re.compile(r"eval\s*\(\s*base64\.b64decode.*token", re.IGNORECASE),
    re.compile(r"\bMALICIOUS_DETONATION_ATTACK_VECTOR\b", re.IGNORECASE)
]

class CommandBlockedError(Exception):
    """Raised when a command violates safety policy and is blocked before guest execution."""
    def __init__(self, command: str, reason: str):
        super().__init__(f"Command blocked by Celesto safety hook: {reason}")
        self.command = command
        self.reason = reason

def evaluate_command_safety(command: str) -> Tuple[bool, str]:
    """
    Evaluates whether a command is safe to run inside the guest microVM.
    Returns (is_allowed, reason).
    """
    cmd_clean = command.strip()
    if not cmd_clean:
        return False, "Empty command not allowed"

    for pattern in BLOCKED_PATTERNS:
        if pattern.search(cmd_clean):
            return False, f"Matched forbidden pattern: {pattern.pattern}"

    return True, "Passed pre-execution safety policy"
