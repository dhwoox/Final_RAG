"""
Chainlit 앱: 질의를 입력하면 LLM이 관련 스킬을 제안하고,
선택 시 매니페스트(.md) 또는 파이썬 스킬을 실행해 로그를 표시합니다.

사전 준비
- pip install chainlit
- (선택) LM Studio 또는 OpenAI 호환 서버를 환경변수로 설정
  - OPENAI_API_KEY, OPENAI_BASE_URL 등

실행
- chainlit run chainlit_app/chainlit.py -w
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

import chainlit as cl

try:
  # OpenAI 호환(LM Studio 포함)
  from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
  OpenAI = None  # 런타임에 없으면 LLM 기능 비활성화

REPO_ROOT = Path(__file__).resolve().parents[1]
LM_SKILLS_PKG = REPO_ROOT / "lm_studio_skills"
SKILLS_DIR = REPO_ROOT / "skills"
WORKFLOWS_DIR = REPO_ROOT / "workflows"


def _run_cmd(args: List[str]) -> Tuple[int, str, str]:
  """명령 실행 헬퍼(표준 출력/에러 캡처)."""
  proc = subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True)
  return proc.returncode, proc.stdout, proc.stderr


def _scan_skill_files() -> List[Path]:
  files: List[Path] = []
  if SKILLS_DIR.exists():
    for p in SKILLS_DIR.rglob("SKILL.md"):
      files.append(p)
  # 워크플로우 후보(.md)도 함께 포함
  if WORKFLOWS_DIR.exists():
    for p in WORKFLOWS_DIR.rglob("*.md"):
      files.append(p)
  # 샘플 매니페스트도 후보에 추가
  sample = LM_SKILLS_PKG / "skills.md"
  if sample.exists():
    files.append(sample)
  return files


def _rank_by_overlap(query: str, paths: List[Path], topk: int = 5) -> List[Path]:
  """아주 단순한 키워드 중첩 점수로 상위 파일을 추립니다."""
  q_tokens = set(query.lower().split())
  scored = []
  for p in paths:
    try:
      text = p.read_text(encoding="utf-8")
    except Exception:
      continue
    content = text.lower()
    score = sum(1 for t in q_tokens if t in content)
    scored.append((score, p))
  scored.sort(key=lambda x: (-x[0], str(x[1])))
  return [p for s, p in scored[:topk] if s > 0]


async def _send_step(title: str, content: str):
  """단계 로그를 Chainlit 메시지로 출력."""
  await cl.Message(author=title, content=content).send()


async def _run_lm_skill_manifest(md_path: Path):
  await _send_step("Runner", f"매니페스트 실행: {md_path}")
  code, out, err = _run_cmd(["python", "-m", "lm_studio_skills", "run-md", str(md_path)])
  await _send_step("stdout", out or "(empty)")
  if err:
    await _send_step("stderr", err)
  if code != 0:
    await _send_step("Runner", f"실패 (exit={code})")
  else:
    await _send_step("Runner", "성공")


def _get_llm_client() -> Optional[object]:
  """LM Studio(OpenAI 호환) 클라이언트 생성.

  환경변수 기본값:
  - OPENAI_BASE_URL (기본: http://localhost:1234/v1)
  - OPENAI_API_KEY (기본: lm-studio)
  - LLM_MODEL (기본: qwen/qwen3-8b)
  """
  if OpenAI is None:
    return None

  base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
  api_key = os.getenv("OPENAI_API_KEY", "lm-studio")

  try:
    client = OpenAI(base_url=base_url, api_key=api_key)
    return client
  except Exception:
    return None


def _llm_choose_manifest(client, query: str, candidates: List[Path]) -> Optional[Path]:
  """LLM에게 후보 목록을 주고 가장 적합한 매니페스트 경로를 선택하도록 요청."""
  if not candidates:
    return None

  # 후보 요약(경로 + 파일 앞부분 일부)
  def to_snippet(p: Path) -> str:
    try:
      text = p.read_text(encoding="utf-8")
      head = text[:800]
    except Exception:
      head = ""
    return f"- path: {p}\n  snippet: |\n{head}"

  manifest_list = "\n".join(to_snippet(p) for p in candidates)
  model = os.getenv("LLM_MODEL", "qwen/qwen3-8b")

  system = (
    "당신은 테스트 자동화 오케스트레이터입니다. 사용자의 질의에 가장 적합한 매니페스트(.md) 하나를 선택하세요.\n"
    "반드시 JSON으로만 응답하세요: {\"path\": \"상대경로\"}.\n"
    "설명이 불충분하면 가장 가까운 후보를 고르세요."
  )
  user = (
    f"질의: {query}\n\n"
    f"후보 매니페스트 목록:\n{manifest_list}\n\n"
    "가장 적합한 파일의 path만 JSON으로 답변하세요."
  )

  try:
    resp = client.chat.completions.create(
      model=model,
      messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user},
      ],
      temperature=0,
      response_format={"type": "json_object"},
      max_tokens=256,
    )
    content = resp.choices[0].message.content if resp.choices else "{}"
    data = json.loads(content)
    path_str = data.get("path")
    if not path_str:
      return None
    sel = Path(path_str)
    if not sel.is_absolute():
      # 레포 기준 상대경로 허용
      if (REPO_ROOT / sel).exists():
        sel = (REPO_ROOT / sel).resolve()
      elif (LM_SKILLS_PKG / sel).exists():
        sel = (LM_SKILLS_PKG / sel).resolve()
    if sel.exists() and sel.suffix.lower() == ".md":
      return sel
  except Exception as e:  # pragma: no cover
    # LLM 불가 시 선택 안 함
    pass
  return None


@cl.on_chat_start
async def on_start():
  intro = (
    "안녕하세요! 질의를 입력하면 관련 스킬을 찾아 제안하고,\n"
    "선택 시 매니페스트(.md) 또는 파이썬 스킬을 실행해 결과를 보여드립니다.\n\n"
    "예시:\n"
    "- 'COMMONR 30 지문 인증 이벤트 검증'\n"
    "- 'fingerprint only 인증 구성하고 이벤트 0x1301 확인'\n"
    "- 'skills.md 실행' (lm_studio_skills/skills.md)\n"
  )
  await cl.Message(content=intro).send()


@cl.on_message
async def on_message(message: cl.Message):
  query = message.content.strip()

  # 1) 사용자가 skills.md/워크플로 파일을 직접 지시하는 경우
  if query.endswith(".md"):
    md = Path(query)
    if not md.is_absolute():
      # 레포 상대 경로 우선
      if (REPO_ROOT / query).exists():
        md = REPO_ROOT / query
      elif (LM_SKILLS_PKG / query).exists():
        md = LM_SKILLS_PKG / query
    if md.exists():
      await _run_lm_skill_manifest(md)
      return

  # 2) skills/ 폴더에서 관련 SKILL.md 후보 찾기
  skill_files = _scan_skill_files()
  ranked = _rank_by_overlap(query, skill_files, topk=5)
  if ranked:
    lines = [f"- {p.relative_to(REPO_ROOT)}" for p in ranked]
    await _send_step("추천 스킬", "\n".join(lines))
  else:
    await _send_step("추천 스킬", "관련 스킬을 찾지 못했습니다. 쿼리를 구체화해 주세요.")

  # 3) LLM 연결되어 있으면 후보 중 하나를 선택해 실행 제안
  client = _get_llm_client()
  if client and ranked:
    await _send_step("LLM", f"LM Studio 모델로 랭킹 선택 시도 (model={os.getenv('LLM_MODEL', 'qwen/qwen3-8b')})")
    selected = _llm_choose_manifest(client, query, ranked)
    if selected:
      await _send_step("LLM 선택", f"{selected.relative_to(REPO_ROOT)}")
      await _run_lm_skill_manifest(selected)
      return
    else:
      await _send_step("LLM", "선택 실패. 수동으로 파일명을 보내 실행할 수 있습니다.")
  else:
    # LLM 미설정 시 안내
    await _send_step(
      "LLM",
      "LM Studio 연결이 비활성화되어 있습니다. 환경변수 OPENAI_BASE_URL/OPENAI_API_KEY/LLM_MODEL을 설정하면 자동 선택이 가능합니다.",
    )

  # 4) lm_studio_skills의 샘플 매니페스트를 자동 제안
  lm_md = LM_SKILLS_PKG / "skills.md"
  if lm_md.exists():
    await _send_step("참고", f"샘플 매니페스트 실행을 원하면 파일명을 그대로 보내세요: {lm_md.relative_to(REPO_ROOT)}")
