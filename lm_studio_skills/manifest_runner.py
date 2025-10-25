from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import auth_pb2
import finger_pb2
import user_pb2
import util

from .base import SkillError, SkillResult
from .command_runner import run_command
from .context import SkillContext
from .manifest import SkillManifest, WorkflowStep


class ManifestExecutor:
  """Markdown 매니페스트를 해석해 실제 자동화를 수행하는 실행기."""

  def __init__(self, context: SkillContext, manifest: SkillManifest):
    self.context = context
    self.manifest = manifest
    self.svc = context.service_manager
    self.environ = context.environ

    self.target_id: Optional[int] = None
    self.variables: Dict[str, Any] = {}
    self.backups: Dict[str, Any] = {}
    self.monitors: Dict[str, util.EventMonitor] = {}
    self.monitor_events: Dict[str, Any] = {}
    self.logs: List[Dict[str, Any]] = []

  def execute(self) -> SkillResult:
    """매니페스트 전 과정을 실행하고 결과를 반환한다."""

    try:
      self._ensure_default_target()
      self._run_instructions(self.manifest.preparation, stage="사전준비")
      self._run_instructions(self.manifest.testdata, stage="테스트데이터")
      self._run_workflow(self.manifest.workflow)
      self._run_instructions(self.manifest.verification, stage="검증")
      self._run_instructions(self.manifest.recovery, stage="복구")
      self._run_instructions(self.manifest.commands, stage="명령어")
    finally:
      self._cleanup_monitors()

    observed_events = {}
    for name, event in self.monitor_events.items():
      if event:
        observed_events[name] = event.eventCode | event.subCode
      else:
        observed_events[name] = None

    return SkillResult(
      success=True,
      message="매니페스트 실행이 완료되었습니다.",
      details={
        "metadata": self.manifest.metadata,
        "logs": self.logs,
        "observed_events": observed_events,
      },
    )

  def _ensure_default_target(self):
    devices = self.environ.get("devices", [])
    if not devices:
      raise SkillError("environ.json에 devices 정보가 없습니다.")
    if self.target_id is None:
      self.target_id = devices[0]["id"]
      self.variables["target_id"] = self.target_id
      self._log("target", f"기본 대상 장치 ID {self.target_id} 선택")

  def _run_instructions(self, instructions: List[List[str]], stage: str):
    for tokens in instructions:
      if not tokens:
        continue
      command = tokens[0]
      handler = getattr(self, f"_handle_{command}", None)
      if handler is None:
        raise SkillError(f"{stage} 단계에서 지원하지 않는 명령: {command}")
      handler(tokens[1:], stage)

  def _run_workflow(self, steps: List[WorkflowStep]):
    for step in steps:
      if not step.api:
        continue
      result = self._execute_expression(step.api)
      self._log("workflow", f"{step.step} - {step.description}", {"result": result})

  def _handle_set_target(self, args: List[str], stage: str):
    if not args:
      raise SkillError("set_target 명령에는 인덱스가 필요합니다.")
    index = int(args[0])
    devices = self.environ.get("devices", [])
    if index >= len(devices):
      raise SkillError(f"장치 인덱스 {index} 가 범위를 벗어났습니다.")
    self.target_id = devices[index]["id"]
    self.variables["target_id"] = self.target_id
    self._log(stage, f"장치 인덱스 {index} -> ID {self.target_id}")

  def _handle_select_target_id(self, args: List[str], stage: str):
    if not args:
      raise SkillError("select_target_id 명령에는 장치 ID가 필요합니다.")
    self.target_id = int(args[0])
    self.variables["target_id"] = self.target_id
    self._log(stage, f"장치 ID {self.target_id} 직접 지정")

  def _handle_require_capability(self, args: List[str], stage: str):
    if not args:
      raise SkillError("require_capability 명령에는 속성 이름이 필요합니다.")
    attr = args[0]
    expected = True
    if len(args) > 1:
      expected = self._to_bool(args[1])
    capability = self.svc.getDeviceCapability(self._require_target())
    actual = getattr(capability, attr, None)
    if actual != expected:
      raise SkillError(f"Capability {attr} 값이 기대치 {expected}와 다릅니다: {actual}")
    self._log(stage, f"Capability {attr} 확인 완료 ({actual})")

  def _handle_backup_auth_config(self, args: List[str], stage: str):
    config = self.svc.getAuthConfig(self._require_target())
    self.backups["auth_config"] = config
    self._log(stage, "인증 설정 백업 완료")

  def _handle_backup_users(self, args: List[str], stage: str):
    users = self.svc.getUsers(self._require_target())
    self.backups["users"] = users or []
    self._log(stage, f"사용자 {len(self.backups['users'])}명 백업")

  def _handle_build_random_user(self, args: List[str], stage: str):
    if not args:
      raise SkillError("build_random_user 명령에는 변수명이 필요합니다.")
    var_name = args[0]
    user = self._build_random_user()
    self.variables[var_name] = user
    self._log(stage, f"랜덤 사용자 {var_name} 생성 (ID={user.hdr.ID})")

  def _handle_load_user_json(self, args: List[str], stage: str):
    if len(args) < 2:
      raise SkillError("load_user_json 명령에는 변수명과 경로가 필요합니다.")
    var_name, raw_path = args[0], args[1]
    path = self.context.base_path / Path(raw_path)
    with path.open(encoding="utf-8") as handle:
      user = json.load(handle, cls=util.UserBuilder)
    self.variables[var_name] = user
    self._log(stage, f"{raw_path} 에서 사용자 {var_name} 로딩")

  def _handle_ensure_hashed_pin(self, args: List[str], stage: str):
    if not args:
      raise SkillError("ensure_hashed_pin 명령에는 사용자 변수가 필요합니다.")
    user = self._require_variable(args[0])
    hashed = self.svc.hashPIN(util.generateRandomPIN())
    if hashed is None:
      raise SkillError("hashPIN 호출이 실패했습니다.")
    user.PIN = hashed
    self._log(stage, "사용자 PIN 해시 생성 완료")

  def _handle_ensure_fingerprint_template(self, args: List[str], stage: str):
    if not args:
      raise SkillError("ensure_fingerprint_template 명령에는 사용자 변수가 필요합니다.")
    user = self._require_variable(args[0])
    if not user.fingers:
      template = finger_pb2.FingerprintTemplate()
      template.index = 0
      template.templates.append(b"fake_fingerprint_data")
      user.fingers.append(template)
    elif not user.fingers[0].templates:
      user.fingers[0].templates.append(b"fake_fingerprint_data")
    self._log(stage, "사용자 지문 템플릿 확보 완료")

  def _handle_restore_auth_config(self, args: List[str], stage: str):
    backup = self.backups.get("auth_config")
    if backup is None:
      self._log(stage, "복원할 인증 설정이 없습니다.")
      return
    self.svc.setAuthConfig(self._require_target(), backup)
    self._log(stage, "인증 설정 복원 완료")

  def _handle_restore_users(self, args: List[str], stage: str):
    backup_users = self.backups.get("users")
    if backup_users is None:
      self._log(stage, "복원할 사용자 데이터가 없습니다.")
      return
    self.svc.removeUsers(self._require_target())
    if backup_users:
      self.svc.enrollUsers(self._require_target(), backup_users)
    self._log(stage, f"사용자 {len(backup_users)}명 복원")

  def _handle_run(self, args: List[str], stage: str):
    if not args:
      raise SkillError("run 명령에는 실행할 커맨드가 필요합니다.")
    result = run_command(args, cwd=self.context.base_path)
    self._log(stage, "명령 실행", result)
    if result["returncode"] != 0:
      raise SkillError(f"명령 실행 실패: {' '.join(args)}")

  def _handle_assert_true(self, args: List[str], stage: str):
    if not args:
      raise SkillError("assert_true 명령에는 표현식이 필요합니다.")
    expr = " ".join(args)
    value = self._execute_expression(expr)
    if not value:
      raise SkillError(f"assert_true 실패: {expr}")
    self._log(stage, f"assert_true 통과 ({expr})")

  def _handle_assert_equal(self, args: List[str], stage: str):
    if len(args) < 2:
      raise SkillError("assert_equal 명령에는 좌변과 우변이 필요합니다.")
    left_expr = args[0]
    right_expr = args[1]
    left_val = self._execute_expression(left_expr)
    right_val = self._execute_expression(right_expr)
    if left_val != right_val:
      raise SkillError(f"assert_equal 실패: {left_val} != {right_val}")
    self._log(stage, f"assert_equal 통과 ({left_val} == {right_val})")

  def _handle_log(self, args: List[str], stage: str):
    message = " ".join(args)
    self._log(stage, message)

  def start_monitor(self, name: str, event_code: int, *, user: Optional[str] = None):
    monitor = util.EventMonitor(
      self.svc,
      self._require_target(),
      eventCode=event_code,
      deviceID=self._require_target(),
      userID=self._resolve_user_id(user) if user else None,
      quiet=True,
      startInstantly=False,
    )
    monitor.start()
    self.monitors[name] = monitor
    self._log("monitor", f"{name} 모니터 시작 (event={hex(event_code)})")
    return monitor

  def verify_monitor(self, name: str, *, timeout: float = 3.0):
    monitor = self._require_monitor(name)
    if not monitor.caught(timeout=timeout):
      raise SkillError(f"{name} 모니터에서 이벤트를 수신하지 못했습니다.")
    self.monitor_events[name] = monitor.description
    self._log("monitor", f"{name} 모니터 이벤트 수신 완료")
    return monitor.description

  def observed_event(self, name: str) -> Optional[int]:
    event = self.monitor_events.get(name)
    if not event:
      return None
    return event.eventCode | event.subCode

  def observed_description(self, name: str) -> Optional[str]:
    event = self.monitor_events.get(name)
    if not event:
      return None
    code = event.eventCode | event.subCode
    return self.svc.getEventDescription(code)

  def enroll_user(self, user: user_pb2.UserInfo) -> bool:
    return self.svc.enrollUsers(self._require_target(), [user])

  def remove_user(self, user: user_pb2.UserInfo) -> bool:
    return self.svc.removeUsers(self._require_target(), [user.hdr.ID])

  def detect_fingerprint(self, user: user_pb2.UserInfo) -> bool:
    finger = user.fingers[0]
    return self.svc.detectFingerprint(self._require_target(), finger)

  def set_fingerprint_only_mode(self) -> bool:
    capability = self.svc.getDeviceCapability(self._require_target())
    auth_config = self.svc.getAuthConfig(self._require_target())
    del auth_config.authSchedules[:]
    schedule = auth_pb2.AuthSchedule()
    if getattr(capability, "extendedFingerprintOnlySupported", False):
      schedule.mode = auth_pb2.AUTH_EXT_MODE_FINGERPRINT_ONLY
    else:
      schedule.mode = auth_pb2.AUTH_MODE_BIOMETRIC_ONLY
    schedule.scheduleID = 1
    auth_config.authSchedules.append(schedule)
    return self.svc.setAuthConfig(self._require_target(), auth_config)

  def _execute_expression(self, expr: str):
    env = {
      "svc": self.svc,
      "context": self.context,
      "target_id": self._require_target(),
      "variables": self.variables,
      "start_monitor": self.start_monitor,
      "verify_monitor": self.verify_monitor,
      "observed_event": self.observed_event,
      "observed_description": self.observed_description,
      "enroll_user": self.enroll_user,
      "remove_user": self.remove_user,
      "detect_fingerprint": self.detect_fingerprint,
      "set_fingerprint_only_mode": self.set_fingerprint_only_mode,
    }
    env.update(self.variables)

    reserved = {
      "svc",
      "context",
      "target_id",
      "variables",
      "start_monitor",
      "verify_monitor",
      "observed_event",
      "observed_description",
      "enroll_user",
      "remove_user",
      "detect_fingerprint",
      "set_fingerprint_only_mode",
    }
    try:
      compiled = compile(expr, "<manifest>", "eval")
      result = eval(compiled, {}, env)
      self._sync_variables(env, reserved)
      return result
    except SyntaxError:
      compiled = compile(expr, "<manifest>", "exec")
      exec(compiled, {}, env)
      self._sync_variables(env, reserved)
      return None

  def _require_target(self) -> int:
    if self.target_id is None:
      self._ensure_default_target()
    return self.target_id  # type: ignore

  def _require_variable(self, name: str):
    if name not in self.variables:
      raise SkillError(f"필요한 변수 {name} 이(가) 존재하지 않습니다.")
    return self.variables[name]

  def _require_monitor(self, name: str) -> util.EventMonitor:
    if name not in self.monitors:
      raise SkillError(f"모니터 {name} 이(가) 시작되지 않았습니다.")
    return self.monitors[name]

  def _resolve_user_id(self, user_name: str) -> Optional[str]:
    user = self.variables.get(user_name)
    if not user:
      return None
    return getattr(user.hdr, "ID", None)

  def _build_random_user(self) -> user_pb2.UserInfo:
    user = user_pb2.UserInfo()
    user.hdr.ID = util.randomAlphanumericUserID()
    user.PIN = util.generateRandomPIN()
    template = finger_pb2.FingerprintTemplate()
    template.index = 0
    template.templates.append(b"fake_fingerprint_data")
    user.fingers.append(template)
    return user

  def _to_bool(self, value: str) -> bool:
    lowered = value.lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
      return True
    if lowered in {"0", "false", "no", "n", "off"}:
      return False
    raise SkillError(f"bool로 변환할 수 없는 값: {value}")

  def _log(self, stage: str, message: str, extra: Optional[Dict[str, Any]] = None):
    entry = {"stage": stage, "message": message}
    if extra:
      entry.update(extra)
    self.logs.append(entry)

  def _cleanup_monitors(self):
    for monitor in self.monitors.values():
      try:
        monitor.stop()
      except Exception:
        continue
    self.monitors.clear()

  def _sync_variables(self, env: Dict[str, Any], reserved: set):
    for key, value in env.items():
      if key in reserved:
        continue
      self.variables[key] = value
