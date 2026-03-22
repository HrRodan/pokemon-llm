"""
conftest.py — shared pytest configuration.

Ensures the project root is on sys.path so all tests can use absolute
imports (e.g. `from agents.base_agent import BaseAgent`) without
needing manual sys.path hacks inside individual test files.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from utils.config import settings

@pytest.fixture(autouse=True)
def force_small_models(monkeypatch):
    """
    Forces all tests to use the small, fast models specified by the user.
    Main agent: openrouter/google/gemini-3.1-flash-lite-preview
    Sub agents: openrouter/openai/gpt-oss-20b
    """
    monkeypatch.setattr(settings, "DEFAULT_MODEL", "openrouter/google/gemini-3.1-flash-lite-preview")
    monkeypatch.setattr(settings, "SUB_AGENT_MODEL", "openrouter/openai/gpt-oss-20b")
