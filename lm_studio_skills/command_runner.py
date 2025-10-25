from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List, Optional


def run_command(
  command: List[str],
  *,
  cwd: Optional[Path] = None,
  timeout: Optional[float] = None,
) -> Dict[str, object]:
  """화이트리스트 기반의 간단한 명령 실행기."""

  completed = subprocess.run(
    command,
    cwd=str(cwd) if cwd else None,
    timeout=timeout,
    capture_output=True,
    text=True,
  )

  return {
    "returncode": completed.returncode,
    "stdout": completed.stdout,
    "stderr": completed.stderr,
    "command": command,
    "cwd": str(cwd) if cwd else None,
  }
