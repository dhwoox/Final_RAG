from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import auth_pb2
import finger_pb2
import user_pb2
import util

from lm_studio_skills.base import Skill, SkillError, SkillParameter, SkillResult
from lm_studio_skills.registry import register_skill


@register_skill
class FingerprintAuthenticationSkill(Skill):
  """
  Reproduce the fingerprint-only success scenario as a reusable Claude-style skill.
  """

  name = "fingerprint_auth_success"
  description = "Enroll a fingerprint user, switch to fingerprint-only mode, and verify event 0x1301."
  parameters = (
    SkillParameter(
      name="timeout",
      type="float",
      default=5.0,
      description="Seconds to wait for the expected event.",
    ),
    SkillParameter(
      name="event_code",
      type="int",
      default=0x1301,
      description="Expected event code (eventCode | subCode) to validate.",
    ),
    SkillParameter(
      name="user_payload",
      type="path",
      required=False,
      description="Optional path to a user JSON payload compatible with util.UserBuilder.",
    ),
    SkillParameter(
      name="reuse_existing_users",
      type="bool",
      default=False,
      description="Keep pre-existing users on the device. When false they are restored after the run.",
    ),
  )

  def run(
    self,
    timeout: float = 5.0,
    event_code: int = 0x1301,
    user_payload: Optional[Path] = None,
    reuse_existing_users: bool = False,
    **_: Any,
  ) -> SkillResult:
    svc = self.context.service_manager
    environ = self.context.environ

    devices = environ.get("devices")
    if not devices:
      raise SkillError("environ.json does not list any devices to target.")

    target_id = devices[0]["id"]
    capability = svc.getDeviceCapability(target_id)
    if not getattr(capability, "fingerprintInputSupported", False):
      raise SkillError("Fingerprint input is not supported on the selected device.")

    backup_auth = svc.getAuthConfig(target_id)
    existing_users = svc.getUsers(target_id) or []

    replaced_users = False
    if existing_users and not reuse_existing_users:
      svc.removeUsers(target_id)
      replaced_users = True

    user_info = self._prepare_user(svc, user_payload)

    observed = None

    try:
      if not svc.enrollUsers(target_id, [user_info]):
        raise SkillError("Failed to enroll user for fingerprint scenario.")

      self._apply_fingerprint_only_mode(svc, target_id, capability)

      with util.EventMonitor(
        svc,
        target_id,
        eventCode=event_code,
        deviceID=target_id,
        userID=user_info.hdr.ID,
        quiet=True,
      ) as monitor:
        if not svc.detectFingerprint(target_id, user_info.fingers[0]):
          raise SkillError("detectFingerprint call failed.")

        if not monitor.caught(timeout=timeout):
          raise SkillError(f"Expected event {hex(event_code)} not observed within {timeout} seconds.")

        observed = monitor.description

    finally:
      svc.setAuthConfig(target_id, backup_auth)
      svc.removeUsers(target_id, [user_info.hdr.ID])

      if replaced_users and existing_users:
        svc.enrollUsers(target_id, existing_users)

    observed_code = None
    observed_desc = None
    if observed:
      observed_code = observed.eventCode | observed.subCode
      observed_desc = svc.getEventDescription(observed_code)

    details = {
      "target_device": target_id,
      "user_id": user_info.hdr.ID,
      "expected_event": hex(event_code),
      "observed_event": hex(observed_code) if observed_code is not None else None,
      "description": observed_desc,
    }

    message = f"Fingerprint authentication succeeded for user {user_info.hdr.ID}."
    return SkillResult(success=True, message=message, details=details)

  def _prepare_user(self, svc, user_payload: Optional[Path]):
    if user_payload:
      path = self._resolve_path(user_payload)
      with path.open(encoding="utf-8") as handle:
        user_info = json.load(handle, cls=util.UserBuilder)
    else:
      user_info = self._load_default_user()

    if user_info is None:
      user_info = user_pb2.UserInfo()

    user_info.hdr.ID = util.randomAlphanumericUserID()
    hashed_pin = svc.hashPIN(util.generateRandomPIN())
    if hashed_pin is None:
      raise SkillError("hashPIN returned None while preparing test user.")
    user_info.PIN = hashed_pin

    if not user_info.fingers:
      finger_data = finger_pb2.FingerprintTemplate()
      finger_data.index = 0
      finger_data.templates.append(b"fake_fingerprint_data")
      user_info.fingers.append(finger_data)
    elif not user_info.fingers[0].templates:
      user_info.fingers[0].templates.append(b"fake_fingerprint_data")

    return user_info

  def _load_default_user(self):
    data_dir = self.context.base_path / "demo" / "demo" / "test" / "data"
    if data_dir.exists():
      for entry in data_dir.iterdir():
        if entry.name.startswith("user") and entry.suffix == ".json":
          with entry.open(encoding="utf-8") as handle:
            return json.load(handle, cls=util.UserBuilder)
    return None

  def _resolve_path(self, candidate: Path) -> Path:
    path = Path(candidate)
    if path.is_absolute():
      return path
    return self.context.base_path / path

  def _apply_fingerprint_only_mode(self, svc, device_id, capability):
    auth_config = svc.getAuthConfig(device_id)
    del auth_config.authSchedules[:]

    auth_schedule = auth_pb2.AuthSchedule()
    if getattr(capability, "extendedFingerprintOnlySupported", False):
      auth_schedule.mode = auth_pb2.AUTH_EXT_MODE_FINGERPRINT_ONLY
    else:
      auth_schedule.mode = auth_pb2.AUTH_MODE_BIOMETRIC_ONLY

    auth_schedule.scheduleID = 1
    auth_config.authSchedules.append(auth_schedule)
    svc.setAuthConfig(device_id, auth_config)
