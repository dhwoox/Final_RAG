from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

from .base import SkillError
from .context import SkillContext
from .manifest import parse_manifest
from .manifest_runner import ManifestExecutor
from .registry import global_registry, load_builtin_skills


def _parse_key_value(items) -> Dict[str, str]:
  result: Dict[str, str] = {}
  for item in items or ():
    if "=" not in item:
      raise SkillError(f"잘못된 파라미터 형식: {item}. KEY=VALUE 형태여야 합니다.")
    key, value = item.split("=", 1)
    result[key.strip()] = value.strip()
  return result


def _build_context(args) -> SkillContext:
  return SkillContext(
    base_path=args.base_path,
    config_path=args.config,
    environ_path=args.environ,
  )


def _cmd_list(args):
  load_builtin_skills()
  registry = global_registry
  for skill_cls in sorted(registry.list_skill_types(), key=lambda cls: cls.name):
    print(f"{skill_cls.name}\t{skill_cls.description}")


def _cmd_describe(args):
  load_builtin_skills()
  registry = global_registry
  skill_cls = registry.get(args.skill)
  if skill_cls is None:
    raise SkillError(f"스킬 '{args.skill}' 을(를) 찾을 수 없습니다.")

  print(f"이름       : {skill_cls.name}")
  print(f"설명       : {skill_cls.description}")
  if not skill_cls.parameters:
    print("파라미터   : (없음)")
    return

  print("파라미터   :")
  for spec in skill_cls.parameters:
    req = "필수" if spec.required else f"기본값={spec.default!r}"
    print(f"  - {spec.name} ({spec.type}, {req})")
    if spec.description:
      print(f"      {spec.description}")


def _cmd_run(args):
  load_builtin_skills()
  registry = global_registry
  skill_cls = registry.get(args.skill)
  if skill_cls is None:
    raise SkillError(f"스킬 '{args.skill}' 을(를) 찾을 수 없습니다.")

  context = _build_context(args)
  skill = skill_cls(context)
  raw_params = _parse_key_value(args.param)
  result = skill.execute(raw_params)

  print(result.message)
  if result.details:
    for key, value in result.details.items():
      print(f"{key}: {value}")


def _cmd_list_md(args):
  manifest = parse_manifest(args.path)
  name = manifest.metadata.get("이름") or manifest.metadata.get("name") or "(제목 없음)"
  description = manifest.metadata.get("설명") or manifest.metadata.get("description") or ""
  print(f"이름: {name}")
  if description:
    print(f"설명: {description}")
  if manifest.workflow:
    print("워크플로우 단계 수:", len(manifest.workflow))


def _cmd_describe_md(args):
  manifest = parse_manifest(args.path)
  print("=== 메타데이터 ===")
  for key, value in manifest.metadata.items():
    print(f"{key}: {value}")
  print("\n=== 사전준비 ===")
  for tokens in manifest.preparation:
    print(" -", " ".join(tokens))
  print("\n=== 테스트 데이터 ===")
  for tokens in manifest.testdata:
    print(" -", " ".join(tokens))
  print("\n=== 워크플로우 ===")
  for step in manifest.workflow:
    print(f" - {step.step}: {step.description} -> {step.api}")
  print("\n=== 검증 ===")
  for tokens in manifest.verification:
    print(" -", " ".join(tokens))
  print("\n=== 복구 ===")
  for tokens in manifest.recovery:
    print(" -", " ".join(tokens))
  if manifest.commands:
    print("\n=== 명령어 ===")
    for tokens in manifest.commands:
      print(" -", " ".join(tokens))


def _cmd_run_md(args):
  context = _build_context(args)
  manifest = parse_manifest(args.path)
  executor = ManifestExecutor(context, manifest)
  result = executor.execute()
  print(result.message)
  if result.details:
    metadata = result.details.get("metadata", {})
    if metadata:
      print("메타데이터:")
      for key, value in metadata.items():
        print(f"  {key}: {value}")
    print("로그:")
    for log in result.details.get("logs", []):
      stage = log.get("stage")
      message = log.get("message")
      print(f"  [{stage}] {message}")
      extra = {k: v for k, v in log.items() if k not in {"stage", "message"}}
      for key, value in extra.items():
        print(f"    - {key}: {value}")
    observed = result.details.get("observed_events", {})
    if observed:
      print("관측된 이벤트:")
      for name, code in observed.items():
        print(f"  {name}: {code}")


def main(argv=None):
  parser = argparse.ArgumentParser(description="LM Studio Claude 스타일 스킬 실행기")
  parser.add_argument("--base-path", type=Path, default=None, help="레포지토리 루트 경로 재지정")
  parser.add_argument("--config", type=Path, default=None, help="config.json 경로 재지정")
  parser.add_argument("--environ", type=Path, default=None, help="environ.json 경로 재지정")

  subparsers = parser.add_subparsers(dest="command", required=True)

  list_parser = subparsers.add_parser("list", help="파이썬 기반 스킬 목록 출력")
  list_parser.set_defaults(func=_cmd_list)

  describe_parser = subparsers.add_parser("describe", help="파이썬 기반 스킬 상세 정보")
  describe_parser.add_argument("skill", help="스킬 식별자")
  describe_parser.set_defaults(func=_cmd_describe)

  run_parser = subparsers.add_parser("run", help="파이썬 기반 스킬 실행")
  run_parser.add_argument("skill", help="스킬 식별자")
  run_parser.add_argument(
    "--param",
    action="append",
    default=[],
    metavar="KEY=VALUE",
    help="파라미터 덮어쓰기 (여러 번 사용 가능)",
  )
  run_parser.set_defaults(func=_cmd_run)

  list_md_parser = subparsers.add_parser("list-md", help="Markdown 스킬 요약")
  list_md_parser.add_argument("path", type=Path, help="매니페스트 파일 경로")
  list_md_parser.set_defaults(func=_cmd_list_md)

  describe_md_parser = subparsers.add_parser("describe-md", help="Markdown 스킬 상세 출력")
  describe_md_parser.add_argument("path", type=Path, help="매니페스트 파일 경로")
  describe_md_parser.set_defaults(func=_cmd_describe_md)

  run_md_parser = subparsers.add_parser("run-md", help="Markdown 스킬 실행")
  run_md_parser.add_argument("path", type=Path, help="매니페스트 파일 경로")
  run_md_parser.set_defaults(func=_cmd_run_md)

  args = parser.parse_args(argv)

  try:
    args.func(args)
  except SkillError as exc:
    print(f"[SkillError] {exc}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
  main()
