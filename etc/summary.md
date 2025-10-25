# 자동화 테스트 인수인계 요약

## 1. 개요

- 대상 프로젝트: `demo/test` 중심의 COMMONR, Access, Door, Auth 등 gRPC 기반 자동화 스위트
- 주요 구성 요소: `biostar/proto/`, `biostar/service/`, `demo/`, `demo/test/`, `example/`
- 목표: 테스트 케이스 요구사항을 분석하여 재현 가능한 자동화 코드를 작성하고, 이벤트/상태 검증을 통해 완전한 커버리지를 확보

---

## 2. 전체 워크플로우

1. **요구 분석 & TC 재정의**

   - 원문 TC를 표 형태로 재구성: Step, 입력 데이터, 장치 역할, 기대 이벤트/상태, 예외 조건을 열로 분리
   - 각 Step에 필요한 사전 조건(예: 사용자 존재, 인증 모드, 스케줄)을 식별하고 별도 목록으로 정리
   - 기대 결과에서 “로그/이벤트/화면” 표현은 gRPC 이벤트 코드와 상태 조회로 변환하여 검증 포인트로 기록

2. **리소스 조사 & 매핑**

   - `biostar/proto/` → 필요한 enum/메시지 구조 확인, 상수 값과 필수 필드 메모
   - `biostar/service/*_pb2.py`, `demo/manager.py` → 사용할 `ServiceManager` 메서드, 반환 타입, 예외 패턴 점검
   - `demo/test` → 터미널에서 `rg --glob "*"` 또는 IDE 검색 기능으로 키워드를 찾아 유사 테스트를 식별하고, 재사용 가능한 로직(데이터 준비, EventMonitor 구성, 복구 루틴)을 추출
     - `demo/test/testCOMMONR_xx`는 Legacy/확장 케이스로, 협박 지문 이벤트(0x1501), TNA 설정, Access/TNA/스케줄 조합, 대량 사용자 등록, 슬레이브-마스터 동기화, 복수 EventMonitor 사용 등 복잡한 패턴을 제공한다. 새 테스트를 설계할 때 유사 기능을 다루는 파일을 찾아 표로 정리해 두면 분석 시간이 줄어든다
   - Step별로 필요한 리소스를 표로 작성: **Step / 사용할 proto enum / ServiceManager 메서드 / 참고 테스트 파일 / 필요 JSON 경로**
   - 이벤트/로그 요구사항은 `demo/event_code.json`과 `self.svcManager.getEventDescription()`으로 대응
     - Expected Result에 “로그/이벤트 발생”이 있으면 반드시 해당 이벤트 코드·서브 코드·설명을 찾아 기록
     - 다중 이벤트(성공/실패, 타임아웃, 듀레스 등)는 모두 표에 정리해 Step과 1:1 매핑
     - `event_code.json`에서 찾은 정수 값은 테스트 코드에 그대로 사용하기보다 `0xXXXX` 형태로 표기하고 주석에 `event_code + sub_code` 근거를 남김

3. **데이터 & 환경 설계**

   - JSON이 존재하면 복사본을 만들어 필요한 필드만 수정(Builder 사용)하여 입력 데이터로 활용
   - JSON이 없고 랜덤 사용이 부적절한 경우:
     - `util` Builder로 빈 객체 생성 → TC 명세 값을 그대로 대입
     - ID/PIN/템플릿 등은 TC 데이터 표에 명시된 값(또는 고정 값)으로 설정해 재현성 보장
   - 새 JSON 리소스가 필요하면 `demo/test/data/` 하위에 `TC명_*.json` 형식으로 작성하고, Builder에서 로딩되도록 구조를 맞춘다
   - 장치 초기 상태 점검: `config.json`, `test/environ.json`의 대상 ID, Slave 구성, 인증 설정을 확인하고, 요구되는 시간/타임존/네트워크 조건이 있는지 체크
   - Device capability(`self.capability`, `self.capInfo`)를 먼저 확인하고 조건 불충족 시 `self.skipTest` 사유 기록
   - 변경 전 상태(사용자, 인증 설정, Door/Access 리소스 등)는 모두 백업

4. **구현 단계**

   - Step 순서대로 `ServiceManager` API를 호출하며 주석으로 TC Step 번호 매핑
   - 인증 모드는 capability에 따라 `AUTH_MODE_*` / `AUTH_EXT_MODE_*` 자동 선택, 필요 시 추가 설정(타임아웃 등) 적용
   - 입력 시뮬레이션은 지문→`detectFingerprint`, PIN/ID→`enterKey`, 카드→`detectCard`, 얼굴→`detectFace`로 나누고 재시도 시나리오 포함
   - Slave 관련 Step은 Master에 사용자 등록 후 Slave config 적용, 이벤트 모니터의 `deviceID`를 Slave ID로 지정

5. **검증 단계**

   - 이벤트 검증: `util.EventMonitor`로 감시 → `monitor.caught(timeout)` → `eventCode | subCode` 비교 → `getEventDescription` 확인
     - 테스트 실행 중 콘솔에 이벤트 내용을 출력해 장비 로그와 싱크 여부를 즉시 확인
     - 복수 이벤트가 예상되면 이벤트 코드별로 별도 모니터 블록을 두거나 `quiet=True` 옵션 없이 전체 흐름을 확인
     - 실패 시 실제 발생 코드와 기대 코드 차이를 로그에 남겨 추적 가능하게 함
   - 상태 검증: `getAuthConfig`, `getUsers`, `getDoorStatus`, `getAccessGroups` 등 조회 API로 변경 사항 확인
   - API 호출 성공 여부(`assertTrue(self.svcManager.detect... )`) 및 반환 데이터 정확성(`assertEqual`, `assertIn`) 검증
   - `python -m unittest demo.test.testCOMMONR_xx` 등 명령으로 실행하고 결과/로그 기록

6. **복구 & 안정화**

   - 테스트 본문 종료 시 `finally`에서 백업했던 사용자/설정/리소스를 순서대로 복원
   - 이벤트 모니터 스레드를 포함한 모든 리소스를 정리하고, 실패 시 남은 상태가 다음 테스트에 영향을 주지 않도록 확인

7. **커버리지 점검**

   - 기능별 체크리스트(모드, 입력 타입, 이벤트 유형, Master/Slave 조합, 확장 기능)를 업데이트
   - 미커버 영역은 TODO로 분류하고, 후속 테스트 계획에 반영

8. **인수 문서화**
   - 최종 구현 내용을 Step/데이터/검증 포인트와 함께 요약
   - 사용한 proto/Builder/JSON 경로, 장치 요구사항, 예상 이슈를 정리
   - 테스트 내에서 활용한 이벤트 코드·서브 코드 근거(파일 위치, 설명)를 명시해 후속 유지보수가 편하도록 함
   - 신규 TC를 추가할 때마다 문서와 체크리스트를 갱신해 추적 가능하도록 유지

---

## 3. 디렉터리별 참고 리소스

| 디렉터리                | 주요 파일                                                                        | 참고 내용                                                                                                          |
| ----------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `biostar/proto/`        | `auth.proto`, `finger.proto`, `device.proto`, `event.proto` 등                   | gRPC 서비스 및 enum 정의. `AUTH_MODE_*`, `FingerFlag`, `SecurityLevel` 등 확인                                     |
| `biostar/service/`      | `*_pb2.py`, `manager.py`                                                         | gRPC Stub, 메시지, `ServiceManager` 고수준 API (`hashPIN`, `detectFingerprint`, `enterKey`, `getEventDescription`) |
| `demo/`                 | `event_code.json`, `manager.py`, `test/util.py`                                  | 이벤트 코드 맵, 서비스 초기화, JSON Builder 로더, `EventMonitor`                                                   |
| `demo/test/testCOMMONR` | `testCOMMONR.py`, `testCOMMONR_*`, `testAuth.py`, `testAccess.py`, `testDoor.py` | 공통 테스트 베이스 + 각 기능 시나리오 구현 패턴                                                                    |
| `demo/test/`            | `testCOMMONR_*`, `testBCRTC_*`, `testCOMMONR_30_xx` 등                           | Legacy/확장 케이스(협박 지문, TNA/스케줄, 대량 사용자, 슬레이브 테스트, 다중 EventMonitor)                         |
| `example/`              | `example/.../test/*.py`                                                          | 간단한 샘플; API 사용법 및 이벤트 처리 참고                                                                        |

---

## 4. 데이터 & 환경 준비 가이드

- **ID 생성**
  - `self.capInfo.alphanumericIDSupported` 참 → TC 명세의 ID 규칙을 따르는 고정 문자열을 지정 (`"AUTO_TC01"` 등)
  - False → 숫자 범위 내에서 고정 값 사용 (`"12345678"`). 랜덤 값이 필요하면 TC에서 허용하는 범위 내에서 `util.random*` 호출 후 로그에 기록
- **PIN 처리**
  - TC에서 PIN 값이 정해져 있다면 해당 값을 bytes로 변환 후 `self.svcManager.hashPIN(고정PIN)` 호출
  - 값이 지정되지 않은 경우에도 재현성 확보를 위해 고정 PIN(예: `b"1357"`)을 선정하고 주석에 명시
- **지문/얼굴 템플릿**
  - JSON에 템플릿이 없으면 `util` Builder로 생성 후 더미 바이트(`b"finger_template_tc01"`)를 추가
  - 여러 지문이 필요한 케이스는 인덱스와 바이트를 명시적으로 정의 (`index=0`, `templates=[b"finger_a"]`)
- **JSON Builder 활용**
  - `util.UserBuilder`, `util.DoorBuilder`, `util.AccessGroupBuilder` 등으로 로딩한 뒤 TC 요구에 맞춰 필드를 덮어쓴다
  - 원본 JSON을 수정하지 않기 위해 `copy.deepcopy` 후 수정한 객체를 사용
- **Capability & Skip**
  - `self.capability.fingerprintInputSupported`, `PINInputSupported`, `extendedFingerprintOnlySupported` 등 체크
  - 조건 불충족 시 즉시 `self.skipTest("fingerprint input not supported")` 형태로 명시
- **백업/복구**
  - `backup_users = self.svcManager.getUsers(...)`
  - `backup_auth = copy.deepcopy(self.svcManager.getAuthConfig(...))`
  - `finally`에서 `removeUsers`, `setAuthConfig(backup)` 등 원복 순서를 지켜 깨끗한 상태 유지

### 이벤트 코드 확보/검증 절차

1. TC 기대 결과에 “이벤트/로그 발생”이 있으면, 해당 Step 번호 옆에 **이벤트 명세 열**을 추가한다.
2. `demo/event_code.json`에서 `event_code`와 `sub_code`를 검색해 정수 값과 설명을 모두 기록한다.
3. 테스트 코드에는 `eventCode=0xXXXX` (메인 코드) 형태로 입력하고, 주석 또는 상수 명(`BS2_EVENT_IDENTIFY_SUCCESS`)으로 어떤 조합인지 명시한다.
4. 다중 이벤트를 한 Step에서 검증해야 할 경우, `EVENT_SUCCESS`, `EVENT_FAIL`처럼 상수로 분리하고 기대 설명(`desc`)을 Docstring에 복사해 둔다.
5. 실행 중에는 `self.svcManager.getEventDescription(0xXXXX)`을 호출해 실제 장비가 동일한 설명을 제공하는지 검증한다.
6. 신규 이벤트가 추가되거나 서브 코드가 변경되면 `event_code.json`을 업데이트하고, 테스트 상수/주석도 동시에 수정한다.
7. 이벤트 코드를 가지고 오는 이유:
   - **Expected Result를 코드 수준으로 명확히 대응** → 서술형 요구사항을 정량적 검증으로 전환
   - **실패 분석이 용이** → 실제 발생한 `eventCode | subCode`와 기대 값을 비교해 원인 분석
   - **문서화 일관성 확보** → 후임이 이벤트 의미를 바로 이해하고 재사용 가능
   - **로깅 표준화** → 장비 로그와 테스트 로그의 텍스트가一致하여 추적 쉬움

---

## 5. 구현 패턴

- **Auth 모드 설정**

  ```python
  auth_conf = copy.deepcopy(self.svcManager.getAuthConfig(device_id))
  del auth_conf.authSchedules[:]
  schedule = auth_pb2.AuthSchedule()
  if capability.extendedFingerprintOnlySupported:
      schedule.mode = auth_pb2.AUTH_EXT_MODE_FINGERPRINT_ONLY
  else:
      schedule.mode = auth_pb2.AUTH_MODE_BIOMETRIC_ONLY
  schedule.scheduleID = 1
  auth_conf.authSchedules.append(schedule)
  self.svcManager.setAuthConfig(device_id, auth_conf)
  time.sleep(0.3)
  ```

- **이벤트 검증**

  ```python
  with util.EventMonitor(self.svcManager, master_id,
                         eventCode=expected_code,
                         deviceID=target_device,
                         userID=user_id) as monitor:
      self.assertTrue(self.svcManager.detectFingerprint(target_device, template))
      self.assertTrue(monitor.caught())
      self.assertEqual(monitor.description.eventCode | monitor.description.subCode,
                       expected_code)
      self.assertTrue(self.svcManager.getEventDescription(expected_code))
  ```

- **복합 인증 (지문+PIN)**

  ```python
  wrong_pin = b"9999" if plain_pin != b"9999" else b"8888"
  with util.EventMonitor(..., eventCode=0x1403) as fail_monitor:
      self._detect(...)
      self._enter_key(wrong_pin)
      self.assertTrue(fail_monitor.caught())

  with util.EventMonitor(..., eventCode=0x1302) as success_monitor:
      self._detect(...)
      self._enter_key(plain_pin)
      self.assertTrue(success_monitor.caught())
  ```

- **Slave 시나리오**
  - 사용자 등록은 Master (`self.targetID`)
  - Slave Capability 획득: `auth_target, cap = self.getFingerprintInputSupportedDevice(self.slaveIDs)`
  - 각각 Auth 모드 설정 후 Slave에 대해 입력/이벤트 검증

### 추가 패턴 (demo/test/testCOMMONR_xx.py 참고)

- **TNA/근태 설정**: `testCOMMONR_09_1` 등에서 `tna_pb2.TNAConfig`를 사용해 다양한 모드를 설정/검증. `self.getTNASupportedDevice`로 Slave Capability 확인 후 `setTNAConfig` → `getTNAConfig` 비교 패턴을 재사용.
- **협박 지문·다중 이벤트**: `testCOMMONR_30_7_12`처럼 Finger flag를 `BS2_FINGER_FLAG_DURESS`로 설정하고 `eventCode=0x1501`(듀레스) 모니터링. 성공/실패 이벤트를 연속으로 검증할 때는 EventMonitor 블록을 분리하고 사용자 데이터를 재활용.
- **대량 사용자/랜덤 루프**: 일부 테스트는 여러 사용자 ID/PIN을 반복 생성하여 장치 한계 및 일관성을 확인. 재현성을 위해 루프에서도 생성한 값과 결과를 로그에 남긴다.
- **스케줄·타임아웃 조합**: `testCOMMONR_21_xx`, `testCOMMONR_30_6_11` 등은 인증 모드 변경과 함께 스케줄/타임아웃을 조정하고 재확인한다. 변경 전후 설정을 `copy.deepcopy`로 보존해 복원 로직을 항상 포함한다.
- **복수 디바이스 흐름**: Master/Slave 간 권한 전송, 스케줄 적용, 이벤트 감시를 병행하는 케이스가 많으므로, 슬레이브 ID 리스트에서 Capability를 찾고 각 단계마다 `skipTest` 조건을 명시해 유지보수를 용이하게 한다.

---

## 6. 검증 포인트 표 예시

| Step | 동작            | 입력/설정                          | 기대 결과                   | 검증 방법                                | 이벤트 코드 | 비고                    |
| ---- | --------------- | ---------------------------------- | --------------------------- | ---------------------------------------- | ----------- | ----------------------- |
| 1    | `enrollUsers`   | 사용자 JSON + 지문 + 해시 PIN      | 사용자 등록 성공            | `self.svcManager.getUsers`에서 존재 확인 | -           | 기존 사용자 백업/복원   |
| 2    | `setAuthConfig` | 지문+PIN 모드 (extended 여부 고려) | 인증 모드 반영              | `getAuthConfig` 비교                     | -           | 적용 후 0.3s 대기       |
| 3    | 지문+오답 PIN   | 지문 템플릿, `wrong_pin`           | 실패 이벤트 기록            | `EventMonitor`로 `0x1403` 확인           | 0x1403      | 재시도 준비 확인        |
| 4    | 지문+정답 PIN   | 지문 템플릿, `plain_pin`           | 성공 이벤트 기록, 설명 존재 | `EventMonitor` / `getEventDescription`   | 0x1302      | Expected Result 충족    |
| 5    | 복구            | 사용자/설정 원상 복귀              | 초기 상태 회복              | `removeUsers` → `enrollUsers(backup)`    | -           | `finally` 블록에서 수행 |

시나리오마다 표를 작성해 체크리스트로 활용한다.

---

## 7. 기능별 커버리지 체크리스트

- **인증 모드**
  - 지문 Only / 지문+PIN / 얼굴 / 카드 / ID 시나리오
  - Master vs Slave, Extended 모드 지원 여부
- **Credential 조합**
  - 성공, 실패, 타임아웃, Duress, 이벤트 조합 확인
  - `event_code.json`에 따른 서브 코드까지 점검
- **접근 제어**
  - AccessGroup, HolidayGroup, AccessLevel, Schedule, Operator
  - Door/Lift/APB Zone 설정 및 상태 조회
- **환경 설정**
  - Display/Status/DST/Wiegand 설정 (`util.load*` + `ServiceManager.set*`)
  - 인증 타임아웃, 매치 타임아웃 조정 및 적용 확인
- **추가 기능**
  - Thermal, TNA, Blacklist, Gateway, Sync 등 example 폴더 참조
  - 새로운 장비 유형/Capability 등장 시 테스트 확장 계획

---

## 8. 유지보수 & 문제 해결 가이드

- **proto 변경**: `.proto` 수정 시 `*_pb2.py` 재생성 → 기존 enum 값 호환성 확인
- **event_code.json 관리**: 신규 이벤트 추가 시 `ServiceManager.eventSvc.initCodeMap` 경로 확인, 테스트 갱신
- **장치 준비**: `config.json`, `test/environ.json`에 장치 정보 작성; Master/Slave id 확인
- **PIN/Hash 문제**: `hashPIN`이 `None` 반환 시 장치 연결 실패 가능 → 로그 확인
- **gRPC 오류**: `ServiceManager` API는 실패 시 False 반환 → 테스트에서 즉시 `assertTrue`로 감지
- **시간 관련 이슈**: `setDeviceTime` 필요 시 `testAuth.py` 패턴 참고
- **성능/타임아웃**: 이벤트 모니터 대기 시간은 상황에 맞게 확장 (`monitor.caught(timeout)`)
- **로그 수집**: 필요 시 CLI 또는 장치 로그 활용, 테스트 실패 시 이벤트 출력(`EventMonitor`가 콘솔에 로그 제공)

---

## 9. 인수 마무리 체크

- [ ] TC 요구사항 분석 문서 (`검증 포인트 표`) 준비 여부
- [ ] 관련 proto/서비스/API 조사 및 최신성 확인
- [ ] 테스트 코드 작성 시 CLAUDE 워크플로우 준수 (`필수 import`, `skipTest`, `util` 사용)
- [ ] 모든 변경 사항에 대한 복구 로직 포함 여부
- [ ] 성공/실패/타임아웃 이벤트에 대한 검증 커버리지 확보
- [ ] `python -m unittest` 결과 기록 및 공유
- [ ] 체크리스트/인수 문서 갱신 후 공유 완료

이 문서에 따라 후임자는 시나리오 분석부터 테스트 구현, 검증, 문서화까지 일관된 방식으로 자동화 코드를 작성하고 유지보수할 수 있다.
