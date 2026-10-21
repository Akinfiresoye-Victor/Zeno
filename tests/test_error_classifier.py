import unittest
from pathlib import Path
import tempfile
import shutil

from zeno.engine.errors import (
    ErrorCategory,
    ErrorClassifier,
    RetryHandler,
    save_step_draft,
)


class TestErrorClassifier(unittest.TestCase):
    def test_classify_ssl_unexpected_eof(self):
        err = "urllib3.exceptions.ProtocolError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) [SSL: UNEXPECTED_EOF_WHILE_READING]"
        classified = ErrorClassifier.classify(err)
        self.assertEqual(classified.category, ErrorCategory.TRANSIENT_NETWORK)
        self.assertTrue(classified.is_retryable)
        self.assertFalse(classified.suggest_provider_switch)

    def test_classify_rate_limit(self):
        err = "google.api_core.exceptions.ResourceExhausted: 429 Resource has been exhausted (e.g. check quota)."
        classified = ErrorClassifier.classify(err)
        self.assertEqual(classified.category, ErrorCategory.RATE_LIMIT)
        self.assertTrue(classified.is_retryable)
        self.assertTrue(classified.suggest_provider_switch)

    def test_classify_server_overload(self):
        err = "503 Service Unavailable: The model is overloaded. Please try again later."
        classified = ErrorClassifier.classify(err)
        self.assertEqual(classified.category, ErrorCategory.SERVER_OVERLOAD)
        self.assertTrue(classified.is_retryable)
        self.assertTrue(classified.suggest_provider_switch)

    def test_classify_auth_error(self):
        err = "401 Unauthorized: Invalid API key provided"
        classified = ErrorClassifier.classify(err)
        self.assertEqual(classified.category, ErrorCategory.AUTHENTICATION)
        self.assertFalse(classified.is_retryable)

    def test_retry_handler_backoff_and_recovery(self):
        call_count = 0
        statuses = []

        def failing_then_succeeding():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionResetError("Connection reset by peer [SSL: UNEXPECTED_EOF_WHILE_READING]")
            return "SUCCESS_DATA"

        handler = RetryHandler(
            max_attempts=4,
            base_delays=[0.01, 0.01, 0.01, 0.01],
            on_status=lambda msg: statuses.append(msg),
        )

        success, result, error = handler.execute_with_retry(
            operation=failing_then_succeeding,
            provider_name="Gemini-2.5",
        )

        self.assertTrue(success)
        self.assertEqual(result, "SUCCESS_DATA")
        self.assertIsNone(error)
        self.assertEqual(call_count, 3)
        self.assertGreaterEqual(len(statuses), 2)
        self.assertIn("Gemini-2.5 connection dropped", statuses[0])

    def test_draft_saving_on_error(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="zeno_draft_test_"))
        try:
            draft_path = save_step_draft(tmp_dir, "step_3", "Partial code content before crash")
            self.assertTrue(draft_path.exists())
            self.assertEqual(draft_path.read_text(encoding="utf-8"), "Partial code content before crash")
            self.assertEqual(draft_path.parent.name, ".drafts")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
