from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class WorkflowStep:
  """워크플로우 표 한 줄을 표현하는 데이터 구조."""

  step: str
  description: str
  api: str
  data: str
  event: str


@dataclass
class SkillManifest:
  """Markdown 스킬 매니페스트 전체를 담는 데이터 구조."""

  path: Path
  metadata: Dict[str, str] = field(default_factory=dict)
  preparation: List[List[str]] = field(default_factory=list)
  testdata: List[List[str]] = field(default_factory=list)
  workflow: List[WorkflowStep] = field(default_factory=list)
  verification: List[List[str]] = field(default_factory=list)
  recovery: List[List[str]] = field(default_factory=list)
  commands: List[List[str]] = field(default_factory=list)
  notes: Dict[str, Sequence[str]] = field(default_factory=dict)


def _parse_metadata_line(line: str) -> Optional[Tuple[str, str]]:
  if ":" not in line:
    return None
  key, value = line.split(":", 1)
  return key.strip(), value.strip()


def _parse_table(lines: List[str]) -> List[WorkflowStep]:
  headers: List[str] = []
  data_rows: List[WorkflowStep] = []

  if not lines:
    return data_rows

  header_line = lines[0]
  headers = [cell.strip() for cell in header_line.strip("|").split("|")]

  for row_line in lines[2:]:
    if not row_line.strip():
      continue
    cells = [cell.strip() for cell in row_line.strip("|").split("|")]
    while len(cells) < len(headers):
      cells.append("")
    step = WorkflowStep(
      step=cells[0] if len(cells) > 0 else "",
      description=cells[1] if len(cells) > 1 else "",
      api=cells[2] if len(cells) > 2 else "",
      data=cells[3] if len(cells) > 3 else "",
      event=cells[4] if len(cells) > 4 else "",
    )
    data_rows.append(step)

  return data_rows


def _parse_bullet(line: str) -> Optional[List[str]]:
  stripped = line.strip()
  if not stripped.startswith("-"):
    return None
  content = stripped[1:].strip()
  if not content:
    return []
  return shlex.split(content, posix=False)


def _section_key(raw: str) -> str:
  return raw.strip().replace(" ", "").lower()


def parse_manifest(path: Path) -> SkillManifest:
  """Markdown 파일을 읽어 SkillManifest 구조로 변환한다."""

  manifest = SkillManifest(path=path)

  current_section: Optional[str] = None
  table_buffer: List[str] = []
  notes_buffer: Dict[str, List[str]] = {}

  with path.open(encoding="utf-8") as handle:
    lines = handle.readlines()

  def flush_table():
    nonlocal table_buffer
    if current_section == "워크플로우" and table_buffer:
      manifest.workflow = _parse_table(table_buffer)
    table_buffer = []

  for raw_line in lines:
    line = raw_line.rstrip("\n")

    if line.startswith("# "):
      flush_table()
      current_section = "메인제목"
      notes_buffer.setdefault(current_section, [])
      continue

    if line.startswith("## "):
      flush_table()
      current_section = line[3:].strip()
      notes_buffer[current_section] = []
      continue

    if current_section == "메타데이터":
      parsed = _parse_metadata_line(line)
      if parsed:
        key, value = parsed
        manifest.metadata[key] = value
      continue

    if current_section == "워크플로우":
      if line.strip().startswith("|"):
        table_buffer.append(line)
      continue

    normalized = _section_key(current_section) if current_section else None

    if normalized in {"사전준비", "테스트데이터", "검증", "복구", "명령어"}:
      tokens = _parse_bullet(line)
      if tokens is not None:
        section_map = {
          "사전준비": manifest.preparation,
          "테스트데이터": manifest.testdata,
          "검증": manifest.verification,
          "복구": manifest.recovery,
          "명령어": manifest.commands,
        }
        target_list = section_map.get(normalized)
        if target_list is not None:
          target_list.append(tokens)
        continue

    if current_section:
      notes_buffer.setdefault(current_section, [])
      notes_buffer[current_section].append(line)

  flush_table()
  manifest.notes = {k: tuple(v) for k, v in notes_buffer.items()}
  return manifest
