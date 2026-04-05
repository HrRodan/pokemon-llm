import os
import unittest
from unittest.mock import patch, MagicMock
from ai_tools.tools import LLMQuery
import ai_tools.tracing

class TestBugReproduction(unittest.TestCase):
    def test_reproduce_type_error(self):
        # Mock env vars so tracing *thinks* it is enabled
        env = {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_BASE_URL": "http://test"
        }
        
        # Simulate ImportError only during class retrieval,
        # but let the general 'import langfuse' succeed.
        import ai_tools.tracing
        ai_tools.tracing._tracing_checked = False
        
        with patch.dict(os.environ, env):
            with patch("langfuse.openai.OpenAI", side_effect=ImportError):
                cls = ai_tools.tracing.get_openai_class()
                # Should return standard OpenAI due to ImportError
                from openai import OpenAI as StandardOpenAI
                self.assertEqual(cls, StandardOpenAI)
                
                # But is_tracing_enabled() still returns True!
                self.assertTrue(ai_tools.tracing.is_tracing_enabled())
                
                # So get_langfuse_params() returns data
                params = ai_tools.tracing.get_langfuse_params(session_id="test")
                self.assertEqual(params["langfuse_session_id"], "test")
                
                # NOW: if we use this class with these params, it should fail
                mock_client = MagicMock(spec=StandardOpenAI)
                
                # Standard OpenAI.chat.completions.create doesn't know langfuse_session_id
                # (In the real world, this is handled by the openai client validation)
                def create_mock(**kwargs):
                    if "langfuse_session_id" in kwargs:
                        raise TypeError("Unexpected argument 'langfuse_session_id'")
                    return MagicMock()
                
                mock_client.chat.completions.create.side_effect = create_mock
                
                with self.assertRaisesRegex(TypeError, "langfuse_session_id"):
                    mock_client.chat.completions.create(**params)
                print("Successfully reproduced inconsistent state bug!")

if __name__ == "__main__":
    unittest.main()
