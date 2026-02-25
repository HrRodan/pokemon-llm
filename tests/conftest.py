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
