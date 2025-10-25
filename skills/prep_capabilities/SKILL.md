# 스킬: prep_capabilities (Capability 점검)

## 메타데이터
- 이름: prep_capabilities
- 설명: 대상 장치의 Capability를 조회하고, 조건 불충족 시 테스트를 Skip하도록 지침을 제공합니다.
- 태그: capability, device, skip, manager.getDeviceCapability

## 입력
- deviceIndex(선택): `environ.json`의 `devices` 배열 인덱스 (기본 0)
- require: 확인할 속성 배열 (예: `["fingerprintInputSupported", "cardSupported"]`)

## 출력
- 결과: 각 속성의 실제 값과 일치 여부(boolean), 요약 메시지

## 선행조건
- `demo/demo/config.json`, `demo/demo/test/environ.json` 경로 확인 가능

## 사용 API/리소스
- ServiceManager.getDeviceCapability(deviceID)
- demo/demo/test/util.py (skipTest 패턴 참고용)

## 단계 요약
1) 대상 장치 선택(deviceIndex) → deviceID 해석
2) `getDeviceCapability(deviceID)` 호출
3) 요구 속성(require)과 실제 값을 비교, 불일치 시 Skip 지침 반환

## 예시 (의사 코드)
```
- 입력: deviceIndex=0, require=["fingerprintInputSupported"]
- 처리: capability = svc.getDeviceCapability(targetID)
- 검증: capability.fingerprintInputSupported == True
- 출력: 통과/불일치 목록
```

## 스크립트
- `scripts/check_capabilities.py`: 실제 Capability를 출력/요약

