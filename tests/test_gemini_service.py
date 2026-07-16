from __future__ import annotations

import json
import unittest

from app.services.gemini_service import (
    DEFAULT_GEMINI_MODEL,
    GeminiError,
    GeminiService,
    normalize_gemini_model,
)


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class GeminiServiceTests(unittest.TestCase):
    def test_request_contains_bounded_generation_and_extracts_text(self) -> None:
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return _Response(
                {
                    "candidates": [
                        {"content": {"parts": [{"text": "What I see\nA useful pattern."}]}}
                    ]
                }
            )

        service = GeminiService("test-key", opener=opener)
        answer = service.generate_productivity_report(
            {"window": {"days": 14}, "daily": []}, "Slept well"
        )

        self.assertEqual(answer, "What I see\nA useful pattern.")
        self.assertIn(f"{DEFAULT_GEMINI_MODEL}:generateContent", seen["url"])
        self.assertEqual(seen["timeout"], 30)
        self.assertLessEqual(seen["body"]["generationConfig"]["maxOutputTokens"], 420)
        prompt = seen["body"]["contents"][0]["parts"][0]["text"]
        self.assertIn("Slept well", prompt)
        self.assertIn("untrusted data", prompt)

    def test_missing_key_and_missing_candidate_are_safe_errors(self) -> None:
        with self.assertRaises(GeminiError):
            GeminiService("")

        service = GeminiService("test-key", opener=lambda *_args, **_kwargs: _Response({}))
        with self.assertRaises(GeminiError):
            service.generate_productivity_report({"daily": []})

    def test_retired_saved_default_is_upgraded(self) -> None:
        self.assertEqual(normalize_gemini_model("gemini-2.5-flash-lite"), DEFAULT_GEMINI_MODEL)
        self.assertEqual(
            GeminiService("test-key", "gemini-2.5-flash-lite").model,
            DEFAULT_GEMINI_MODEL,
        )


if __name__ == "__main__":
    unittest.main()
