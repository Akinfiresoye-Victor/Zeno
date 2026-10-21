"""
Error Handling, Classification, and Retry Engine for Zeno Desktop AI Assistant.
Enforces Rule D:
- Granular error classification (transient network, SSL EOF, rate limit, overload, auth, bad request, tool error).
- Exponential backoff with jitter and live user status updates.
- Explicit provider/model switching with user consent (never silent).
- Zero work loss: saves partial drafts and never marks a failed model call complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import logging
from pathlib import Path
import random
import re
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("zeno.errors")


class ErrorCategory(str, Enum):
    TRANSIENT_NETWORK = "transient_network"
    RATE_LIMIT = "rate_limit"
    SERVER_OVERLOAD = "server_overload"
    AUTHENTICATION = "authentication"
    BAD_REQUEST = "bad_request"
    TOOL_COMMAND_ERROR = "tool_command_error"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedError:
    category: ErrorCategory
    raw_message: str
    is_retryable: bool
    recommended_backoff_seconds: float
    user_friendly_summary: str
    suggest_provider_switch: bool


class ErrorClassifier:
    """Classifies errors into actionable categories according to Rule D."""

    # Signatures for transient network failures
    TRANSIENT_NETWORK_PATTERNS = [
        r"ssl",
        r"eof",
        r"unexpected_eof_while_reading",
        r"connection\s*(reset|refused|aborted|closed)",
        r"wsarecv",
        r"timed?\s*out",
        r"socket",
        r"broken\s*pipe",
        r"dns",
        r"getaddrinfo",
        r"remotely\s*closed",
        r"network\s*is\s*unreachable",
        r"temporary\s*failure",
    ]

    # Rate limiting
    RATE_LIMIT_PATTERNS = [
        r"\b429\b",
        r"rate\s*limit",
        r"quota\s*exceeded",
        r"resource\s*exhausted",
        r"too\s*many\s*requests",
    ]

    # Server overload
    OVERLOAD_PATTERNS = [
        r"\b503\b",
        r"service\s*unavailable",
        r"overloaded",
        r"high\s*demand",
        r"server\s*busy",
        r"\b502\b",
        r"\b504\b",
        r"gateway\s*timeout",
    ]

    # Authentication / Authorization
    AUTH_PATTERNS = [
        r"\b401\b",
        r"\b403\b",
        r"api\s*key\s*(invalid|missing|expired|not\s*found)",
        r"permission\s*denied",
        r"unauthorized",
        r"forbidden",
    ]

    # Bad request / client errors
    BAD_REQUEST_PATTERNS = [
        r"\b400\b",
        r"invalid\s*argument",
        r"context\s*length",
        r"token\s*limit",
        r"max\s*tokens",
    ]

    @classmethod
    def classify(cls, error_input: Any) -> ClassifiedError:
        msg = str(error_input or "").strip()
        lower_msg = msg.lower()

        # 1. Transient Network (SSL EOF, connection drops, socket timeouts)
        if any(re.search(pat, lower_msg) for pat in cls.TRANSIENT_NETWORK_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.TRANSIENT_NETWORK,
                raw_message=msg,
                is_retryable=True,
                recommended_backoff_seconds=2.0,
                user_friendly_summary="Network connection dropped or timed out (e.g. SSL EOF).",
                suggest_provider_switch=False,
            )

        # 2. Rate Limits
        if any(re.search(pat, lower_msg) for pat in cls.RATE_LIMIT_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.RATE_LIMIT,
                raw_message=msg,
                is_retryable=True,
                recommended_backoff_seconds=4.0,
                user_friendly_summary="AI model rate limit exceeded. Pausing before retry.",
                suggest_provider_switch=True,
            )

        # 3. Server Overload
        if any(re.search(pat, lower_msg) for pat in cls.OVERLOAD_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.SERVER_OVERLOAD,
                raw_message=msg,
                is_retryable=True,
                recommended_backoff_seconds=4.0,
                user_friendly_summary="AI provider server is currently overloaded.",
                suggest_provider_switch=True,
            )

        # 4. Authentication
        if any(re.search(pat, lower_msg) for pat in cls.AUTH_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.AUTHENTICATION,
                raw_message=msg,
                is_retryable=False,
                recommended_backoff_seconds=0.0,
                user_friendly_summary="API key authentication failed. Please update key in Settings.",
                suggest_provider_switch=True,
            )

        # 5. Bad Request
        if any(re.search(pat, lower_msg) for pat in cls.BAD_REQUEST_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.BAD_REQUEST,
                raw_message=msg,
                is_retryable=False,
                recommended_backoff_seconds=0.0,
                user_friendly_summary="Invalid model request parameters or prompt exceeds context window.",
                suggest_provider_switch=False,
            )

        # 6. Fallback Unknown / Tool Error
        return ClassifiedError(
            category=ErrorCategory.UNKNOWN,
            raw_message=msg,
            is_retryable=False,
            recommended_backoff_seconds=0.0,
            user_friendly_summary=f"Execution error: {msg[:100]}",
            suggest_provider_switch=False,
        )


class RetryHandler:
    """
    Executes operations with exponential backoff and randomized jitter.
    Reports live status lines: 'Gemini connection dropped. Retry 2 of 5 in 8s...'
    """

    DEFAULT_BASE_DELAYS = [2.0, 4.0, 8.0, 16.0, 32.0]

    def __init__(
        self,
        max_attempts: int = 5,
        base_delays: Optional[list[float]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        check_abort: Optional[Callable[[], bool]] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delays = base_delays or self.DEFAULT_BASE_DELAYS
        self.on_status = on_status
        self.check_abort = check_abort

    def calculate_wait_time(self, attempt_index: int) -> float:
        """Calculate exponential backoff duration + random jitter (0.0 to 1.0s)."""
        idx = min(attempt_index, len(self.base_delays) - 1)
        base = self.base_delays[idx]
        jitter = random.uniform(0.0, 1.0)
        return round(base + jitter, 1)

    def execute_with_retry(
        self,
        operation: Callable[[], Any],
        provider_name: str = "Model",
        save_draft_fn: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, Any, Optional[ClassifiedError]]:
        """
        Execute operation. If a retryable error occurs, back off and retry.
        Returns: (success, result, last_classified_error)
        """
        last_classified: Optional[ClassifiedError] = None

        for attempt in range(self.max_attempts):
            if self.check_abort and self.check_abort():
                if self.on_status:
                    self.on_status("Operation stopped by operator.")
                return False, None, ClassifiedError(
                    category=ErrorCategory.UNKNOWN,
                    raw_message="Aborted by user",
                    is_retryable=False,
                    recommended_backoff_seconds=0,
                    user_friendly_summary="Task stopped by user.",
                    suggest_provider_switch=False,
                )

            try:
                result = operation()
                return True, result, None
            except Exception as exc:
                last_classified = ErrorClassifier.classify(exc)
                logger.warning(
                    "Attempt %d/%d failed [%s]: %s",
                    attempt + 1,
                    self.max_attempts,
                    last_classified.category.value,
                    exc,
                )

                # Save partial work draft
                if save_draft_fn:
                    try:
                        save_draft_fn(f"Draft saved after error at attempt {attempt+1}: {str(exc)}")
                    except Exception:
                        pass

                # If non-retryable or final attempt, break
                if not last_classified.is_retryable or attempt >= self.max_attempts - 1:
                    break

                wait_sec = self.calculate_wait_time(attempt)
                status_msg = f"{provider_name} connection dropped ({last_classified.category.value}). Retry {attempt + 2} of {self.max_attempts} in {int(wait_sec)}s..."
                if self.on_status:
                    self.on_status(status_msg)

                # Sleep in short increments to remain responsive to stop signals
                end_time = time.time() + wait_sec
                while time.time() < end_time:
                    if self.check_abort and self.check_abort():
                        return False, None, last_classified
                    time.sleep(0.2)

        return False, None, last_classified


def save_step_draft(project_dir: Path | str, step_id: str, content: str) -> Path:
    """Save partial output into <project>/.drafts/ so work is never lost."""
    pdir = Path(project_dir).resolve()
    drafts_dir = pdir / ".drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_file = drafts_dir / f"draft_{step_id}_{timestamp}.txt"
    draft_file.write_text(content, encoding="utf-8")
    return draft_file
