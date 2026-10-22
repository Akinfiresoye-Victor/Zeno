import unittest
from types import SimpleNamespace
from unittest.mock import patch

from zeno.agent import ZenoAgent
from zeno.engine.errors import ErrorCategory, ErrorClassifier
from zeno.gemini_models import list_supported_gemini_models


class FakeGeminiModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        if model == "gemini-3.5-flash-lite":
            raise RuntimeError(
                "404 NOT_FOUND: models/gemini-3.5-flash-lite is not found"
            )
        return SimpleNamespace(
            text="Recovered with a supported model.",
            usage_metadata=None,
            function_calls=None,
            candidates=[],
        )

    def list(self):
        return [
            SimpleNamespace(
                name="models/gemini-2.5-flash",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="models/gemini-2.5-flash-preview",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="models/text-embedding-004",
                supported_actions=["embedContent"],
            ),
            SimpleNamespace(
                name="models/gemini-2.5-pro",
                supported_actions=["generateContent"],
            ),
        ]


class TestGeminiModelFallback(unittest.TestCase):
    def test_lists_only_generate_content_models_and_prefers_stable_flash(self):
        client = SimpleNamespace(models=FakeGeminiModels())

        candidates = list_supported_gemini_models(client)

        self.assertEqual(
            candidates,
            ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-preview"],
        )

    def test_agent_discovers_supported_model_after_stale_model_404(self):
        models = FakeGeminiModels()
        client = SimpleNamespace(models=models)
        agent = ZenoAgent()

        with patch("google.genai.Client", return_value=client):
            reply, input_tokens, output_tokens = agent._run_gemini_sdk_loop(
                model_name="gemini-3.5-flash-lite",
                api_key="test-key",
                messages_history=[],
                original_user_prompt="Test prompt",
            )

        self.assertEqual(reply, "Recovered with a supported model.")
        self.assertEqual((input_tokens, output_tokens), (0, 0))
        self.assertEqual(
            models.calls,
            ["gemini-3.5-flash-lite", "gemini-2.5-flash"],
        )

    def test_model_not_found_is_classified_as_actionable_bad_request(self):
        classified = ErrorClassifier.classify(
            "404 NOT_FOUND: models/gemini-1.5-flash is not found"
        )

        self.assertEqual(classified.category, ErrorCategory.BAD_REQUEST)
        self.assertFalse(classified.is_retryable)
        self.assertIn("model", classified.user_friendly_summary.lower())


if __name__ == "__main__":
    unittest.main()
