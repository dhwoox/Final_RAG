from __future__ import annotations

from typing import Any, Dict, List

from lm_studio_skills.base import Skill, SkillParameter, SkillResult
from lm_studio_skills.registry import register_skill


@register_skill
class ListDevicesSkill(Skill):
  """Expose a simple inventory skill similar to Claude Code's device overview."""

  name = "list_devices"
  description = "List registered devices from the Suprema demo environment"
  parameters = (
    SkillParameter(
      name="only_connected",
      type="bool",
      required=False,
      default=True,
      description="When true, filter out devices that are not currently connected.",
    ),
  )

  def run(self, only_connected: bool = True, **_: Any) -> SkillResult:
    svc = self.context.service_manager
    devices = svc.getDeviceList()

    normalized: List[Dict[str, Any]] = []
    for device in devices:
      entry = {
        "device_id": getattr(device, "deviceID", None),
        "ip": getattr(device, "IPAddr", None),
        "type": int(getattr(device, "type", 0)),
        "connected": bool(getattr(device, "connected", True)),
        "name": getattr(device, "name", ""),
      }
      if only_connected and not entry["connected"]:
        continue
      normalized.append(entry)

    message = f"{len(normalized)} device(s) returned"
    return SkillResult(success=True, message=message, details={"devices": normalized})
