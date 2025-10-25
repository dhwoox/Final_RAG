"""
한국어 설명:
- 이 스크립트는 environ.json의 devices[deviceIndex]를 기준으로 대상 장치를 선택하고
  ServiceManager.getDeviceCapability() 결과를 요약 출력합니다.
- config/environ 경로는 lm_studio_skills.context의 기본값을 사용합니다.
"""

from pathlib import Path
from typing import List

from lm_studio_skills.context import SkillContext


def main(device_index: int = 0, require: List[str] = None):
  ctx = SkillContext()
  svc = ctx.service_manager
  environ = ctx.environ

  devices = environ.get("devices", [])
  if not devices:
    print("[오류] environ.json에 devices가 없습니다.")
    return 1

  if device_index < 0 or device_index >= len(devices):
    print(f"[오류] device_index 범위 초과: {device_index}")
    return 1

  target_id = devices[device_index]["id"]
  cap = svc.getDeviceCapability(target_id)
  print(f"대상 장치 ID: {target_id}")

  if require:
    failed = []
    for attr in require:
      actual = getattr(cap, attr, None)
      print(f" - {attr}: {actual}")
      if actual is not True:
        failed.append(attr)
    if failed:
      print(f"[결과] 요구 Capability 불일치: {failed}")
      return 2
  else:
    # 전체 속성 중 핵심 몇 개만 샘플 출력
    keys = [
      "fingerprintInputSupported",
      "cardSupported",
      "faceSupported",
    ]
    for k in keys:
      print(f" - {k}: {getattr(cap, k, None)}")

  print("[결과] Capability 점검 통과")
  return 0


if __name__ == "__main__":
  # 간단한 수동 실행용 기본값
  import sys, json
  # 예: python check_capabilities.py 0 '["fingerprintInputSupported"]'
  idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
  require = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
  raise SystemExit(main(idx, require))

