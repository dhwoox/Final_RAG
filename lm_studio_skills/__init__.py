"""
LM Studio Skills package.

Provides a Claude Code style skill system for orchestrating automation
scenarios with the existing Suprema demo suite.
"""

from pathlib import Path
import sys

# Ensure the legacy demo modules are importable without altering PYTHONPATH manually.
_PACKAGE_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_ROOT.parent
_DEMO_ROOT = _REPO_ROOT / "demo"
_DEMO_PATH = _DEMO_ROOT / "demo"
_TEST_PATH = _DEMO_PATH / "test"
_PROTO_PATH = _DEMO_ROOT / "biostar" / "service"

for _path in (_DEMO_ROOT, _DEMO_PATH, _TEST_PATH, _PROTO_PATH):
  if _path.exists():
    path_str = str(_path)
    if path_str not in sys.path:
      sys.path.append(path_str)

__all__ = [
  "base",
  "context",
  "registry",
]
