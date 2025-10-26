# G-SDK Python 자동화 테스트 워크플로우 가이드

> **목적**: 이 문서는 테스트 케이스 작성 시 따라야 할 **일반적인 절차**를 설명합니다.
> 특정 케이스가 아닌, 모든 테스트에 공통적으로 적용되는 워크플로우입니다.

---

## 📋 목차

1. [Phase 1: 테스트 요구사항 분석](#phase-1-테스트-요구사항-분석)
2. [Phase 2: 환경 구성 및 초기화](#phase-2-환경-구성-및-초기화)
3. [Phase 3: 테스트 데이터 준비](#phase-3-테스트-데이터-준비)
4. [Phase 4: 디바이스 능력 검증](#phase-4-디바이스-능력-검증)
5. [Phase 5: 인증 모드 설정](#phase-5-인증-모드-설정)
6. [Phase 6: 테스트 실행](#phase-6-테스트-실행)
7. [Phase 7: 결과 검증](#phase-7-결과-검증)
8. [에러 처리 패턴](#에러-처리-패턴)
9. [워크플로우 체크리스트](#워크플로우-체크리스트)

---

## Phase 1: 테스트 요구사항 분석

### 1.1 테스트 시나리오 파싱

주어진 테스트 케이스 설명에서 다음 정보를 추출하세요:

- **대상 기능**: User, Auth, Door, Access 등
- **인증 방식**: Card, Fingerprint, Face, PIN, 복합 인증
- **디바이스 타입**: Master, Slave
- **예상 이벤트**: 성공/실패 이벤트 코드

**예시 입력:**
```
"Master 장치에서 지문+PIN 복합 인증 테스트"
```

**추출 결과:**
```python
{
  "categories": ["user", "auth", "finger"],
  "auth_mode": "FINGERPRINT_PIN",
  "device_target": "Master",
  "expected_event": "0x1302"  # 지문+PIN 성공 이벤트
}
```

### 1.2 카테고리별 리소스 매핑

`resources/category_map.json` 을 참조하여 필요한 파일 목록을 생성하세요:

**매핑 구조 예시:**
```json
{
  "user": {
    "proto": "biostar/proto/user.proto",
    "pb2": "biostar/service/user_pb2.py",
    "pb2_grpc": "biostar/service/user_pb2_grpc.py",
    "example": "example/user/"
  },
  "auth": { ... },
  "finger": { ... }
}
```

### 1.3 카테고리 키워드 매핑 테이블

| 카테고리 | 키워드 | 주요 기능 |
|---------|--------|----------|
| `user` | 사용자, User, 등록, enroll, 조회 | 사용자 관리 |
| `auth` | 인증, Auth, 인증모드, AuthMode | 인증 설정 |
| `finger` | 지문, Fingerprint | 지문 관리 |
| `face` | 얼굴, Face | 얼굴 관리 |
| `card` | 카드, Card | 카드 관리 |
| `door` | 도어, Door | 도어 관리 |
| `access` | 접근, Access, AccessGroup, AccessLevel | 접근 제어 |
| `event` | 이벤트, Event, 로그, Log | 이벤트 모니터링 |
| `device` | 디바이스, Device, Capability | 디바이스 정보 |
| `schedule` | 스케줄, Schedule | 스케줄 관리 |

---

## Phase 2: 환경 구성 및 초기화

### 2.1 표준 Import 패턴

```python
# 필수 표준 라이브러리
import unittest
import json
import time
import random
import os
from copy import deepcopy

# 테스트 베이스 클래스
from testCOMMONR import TestCOMMONR
from manager import ServiceManager
import util

# 카테고리별 pb2 모듈 (요구사항에 따라 자동 결정)
# 예: user 카테고리 → user_pb2
import user_pb2
# 예: auth 카테고리 → auth_pb2
import auth_pb2
# 예: finger 카테고리 → finger_pb2
import finger_pb2
# 예: device 카테고리 → device_pb2
import device_pb2
# 예: event 카테고리 → event_pb2
import event_pb2

# 필요에 따라 추가
# import door_pb2
# import access_pb2
# import schedule_pb2
```

**Import 규칙:**
- Phase 1에서 추출한 카테고리별로 `{category}_pb2` import
- testCOMMONR, manager, util은 항상 import
- 복합 인증 테스트의 경우 여러 pb2 모듈 필요

---

### 2.2 클래스 정의 및 setUp/tearDown

```python
class testCOMMONR_XX_Y(TestCOMMONR):
    """
    테스트 시나리오 설명

    전제조건:
    - Master 디바이스가 등록되어 있어야 함
    - 디바이스가 지문 입력을 지원해야 함

    테스트 절차:
    1. 사용자 등록 (지문 + PIN 포함)
    2. 지문+PIN 인증 모드 설정
    3. 지문 인식 + PIN 입력
    4. 인증 성공 이벤트 확인

    예상 결과:
    - 이벤트 코드 0x1302 (지문+PIN 인증 성공) 발생
    """

    def setUp(self):
        """
        테스트 환경 초기화

        부모 클래스(TestCOMMONR)의 setUp이 자동으로:
        - config.json 로드 → ServiceManager 생성
        - environ.json 로드 → targetID, slaveIDs 추출
        - 디바이스 등록 확인 및 capability 조회
        - 기존 사용자/Door/AccessLevel/AccessGroup 백업
        - 초기화 (removeUsers, removeDoors 등)
        """
        super().setUp()  # 부모 setUp 호출 필수

        # 테스트별 추가 백업이 필요한 경우만 여기에 작성
        # 예: 특별한 설정 백업
        # self.backupSpecialConfig = self.svcManager.getSpecialConfig(self.targetID)

    def tearDown(self):
        """
        테스트 정리

        부모 클래스(TestCOMMONR)의 tearDown이 자동으로:
        - 인증 설정 복원
        - 테스트 사용자 삭제
        - 백업 사용자 복원
        - Door/AccessLevel/AccessGroup 복원
        """
        # 테스트별 추가 정리가 필요한 경우만 여기에 작성
        # 예: 특별한 설정 복원
        # self.svcManager.setSpecialConfig(self.targetID, self.backupSpecialConfig)

        super().tearDown()  # 부모 tearDown 호출 필수
```

**부모 클래스(TestCOMMONR)가 제공하는 것:**

#### 자동 제공 속성
```python
self.svcManager      # ServiceManager 인스턴스
self.targetID        # 마스터 디바이스 ID (int)
self.capability      # 디바이스 Capability (device_pb2.CapabilityInfo)
self.capInfo         # 디바이스 상세 정보 (device_pb2.CapabilityInfo)
self.slaveIDs        # 슬레이브 디바이스 ID 리스트 (list[int])
self.backupUsers     # setUp에서 백업한 사용자 목록
self.backupAuthMode  # setUp에서 백업한 인증 설정
self.backupDoors     # setUp에서 백업한 도어 목록
self.backupAccessLevels    # setUp에서 백업한 접근 레벨
self.backupAccessGroups    # setUp에서 백업한 접근 그룹
```

#### 자동 백업/복원 항목
- Users (사용자 목록)
- Doors (도어 설정)
- AccessLevels (접근 레벨)
- AccessGroups (접근 그룹)
- AuthMode (인증 설정)

---

### 2.3 테스트 메서드 네이밍 규칙

```python
def testCommonr_{번호}_{서브번호}_{기능명}_{대상}(self):
    """
    예시:
    - testCommonr_30_1_fingerprint_only_on_Master
    - testCommonr_30_1_fingerprint_PIN_on_Slave
    - testCommonr_30_1_card_authentication
    """
    pass
```

**네이밍 컨벤션:**
- `testCommonr_`: 고정 접두사
- `{번호}`: 대분류 번호 (예: 30 = 인증 테스트)
- `{서브번호}`: 소분류 번호 (예: 1, 2, 3...)
- `{기능명}`: 테스트하는 기능 (예: fingerprint_only, fingerprint_PIN)
- `{대상}`: 테스트 대상 (예: on_Master, on_Slave)

---

## Phase 3: 테스트 데이터 준비

### 3.1 사용자 데이터 로드

```python
# JSON 파일에서 사용자 템플릿 로드
user = None
for entry in os.listdir(self.getDataFilePath()):
    if entry.startswith("User") and entry.endswith(".json"):
        with open(self.getDataFilePath(jsonFileName=entry), encoding='UTF-8') as f:
            print(f"\033[90m...Testing User with JSON[{os.path.basename(f.name)}]\033[0m", flush=True)

            # UserBuilder 클래스로 JSON → user_pb2.UserInfo 변환
            from cli.menu.user.userMenu import UserBuilder
            user = json.load(f, cls=UserBuilder)
            break

# 사용자 데이터가 없으면 테스트 스킵
if user is None:
    self.skipTest("no user data found")
```

**UserBuilder의 역할:**
- JSON 파일을 `user_pb2.UserInfo` 객체로 변환
- 카드, 지문, 얼굴 데이터 자동 파싱
- Base64 인코딩된 템플릿 데이터 디코딩

---

### 3.2 필수 속성 설정

#### User ID 생성
```python
# 디바이스 능력에 따라 ID 타입 결정
userId = util.randomNumericUserID()  # 기본: 숫자형 ID (1~4294967294)

if self.capInfo.alphanumericIDSupported:
    # 알파뉴메릭 지원 디바이스의 경우
    userId = util.randomAlphanumericUserID(
        lenOfUserID=0,      # 0이면 1~32자 랜덤
        expending=[]        # 추가 허용 문자 (선택)
    )

user.hdr.ID = userId
```

**ID 생성 규칙:**
- 숫자형 ID: `1` ~ `4294967294` 범위
- 알파뉴메릭 ID: 최대 32자, `a-z, A-Z, 0-9, _, -` 허용
- ID는 항상 문자열로 저장 (`user.hdr.ID = str(...)`)

#### PIN 설정
```python
# PIN 생성 (4~16자리 숫자)
plainPIN = util.generateRandomPIN(
    lengthOfPin=0,      # 0이면 4~16 랜덤
    minLenOfPin=4,
    maxLenOfPin=16
)
# 반환: bytes (예: b'123456')

# PIN 해싱 (디바이스에 저장할 때는 해싱된 값 사용)
user.PIN = self.svcManager.hashPIN(plainPIN)

# plainPIN은 인증 테스트 시 사용하므로 보관 필수!
```

**주의사항:**
- PIN은 숫자만 허용 (0-9)
- 해싱된 PIN을 UserInfo에 저장
- 인증 테스트 시 원본 `plainPIN` 사용

#### 이름 설정 (선택)
```python
# 랜덤 이름 생성
name = util.generateRandomName(
    deviceType=self.svcManager.getDeviceType(self.targetID),
    includeKorean=False,
    lengthOfName=0,      # 0이면 1~48 랜덤
    maxLength=48
)

user.name = name
```

---

### 3.3 바이오메트릭 데이터 처리

실제 바이오메트릭 템플릿은 생성할 수 없으므로 JSON 템플릿 사용:

```python
# JSON에서 로드된 user 객체에 이미 포함됨
if len(user.fingers) > 0:
    finger = random.choice(user.fingers)
    fingerTemplate = finger.templates[0]  # bytes
    print(f"Using finger index: {finger.index}")

if len(user.faces) > 0:
    face = random.choice(user.faces)
    faceTemplate = face.templates[0]  # bytes
    print(f"Using face index: {face.index}")
```

**JSON 구조 예시:**
```json
{
  "hdr": {
    "ID": "template_user",
    "numOfCard": 1,
    "numOfFinger": 2,
    "numOfFace": 1
  },
  "fingers": [
    {
      "index": 0,
      "flag": 0,
      "templates": ["base64_encoded_fingerprint_template"]
    },
    {
      "index": 1,
      "flag": 0,
      "templates": ["base64_encoded_fingerprint_template"]
    }
  ],
  "faces": [
    {
      "index": 0,
      "flag": 0,
      "templates": ["base64_encoded_face_template"]
    }
  ]
}
```

---

## Phase 4: 디바이스 능력 검증

### 4.1 필수 기능 확인

테스트 실행 전 디바이스가 필요한 기능을 지원하는지 확인:

```python
# 지문 입력 지원 확인
if not self.capability.fingerprintInputSupported:
    self.skipTest("fingerprint input not supported")

# 지문 최대 용량 확인
if self.capability.maxFingerprints == 0:
    self.skipTest("no fingerprint capacity")

# PIN 입력 지원 확인
if not self.capability.PINInputSupported:
    self.skipTest("PIN input not supported")

# 얼굴 입력 지원 확인
if not self.capability.faceInputSupported:
    self.skipTest("face input not supported")

# 카드 입력 지원 확인
if not self.capability.cardInputSupported:
    self.skipTest("card input not supported")
```

**Capability 주요 속성:**
```python
# 입력 지원 여부 (bool)
capability.cardInputSupported
capability.idInputSupported
capability.fingerprintInputSupported
capability.PINInputSupported
capability.faceInputSupported

# 확장 모드 지원 여부 (bool)
capability.extendedCardOnlySupported
capability.extendedFingerprintOnlySupported
capability.extendedFaceOnlySupported
capability.extendedIdPINSupported
capability.extendedFingerprintPINSupported
capability.extendedFingerprintFaceSupported
capability.extendedFingerprintFaceOrPINSupported
capability.extendedFingerprintFacePINSupported

# 최대 용량 (int)
capability.maxCards
capability.maxFingerprints
capability.maxFaces
capability.maxUserImages
```

---

### 4.2 Slave 디바이스 선택 (필요 시)

Master-Slave 구조 테스트 시 적절한 Slave 선택:

```python
# 지문 입력 가능한 Slave 찾기
slaveID, slaveCap = self.getFingerprintInputSupportedDevice(self.slaveIDs)
if slaveID is None:
    self.skipTest("no slave device supports fingerprint input")

# 카드 입력 가능한 Slave 찾기
slaveID, slaveCap = self.getCardInputSupportedDevice(self.slaveIDs)
if slaveID is None:
    self.skipTest("no slave device supports card input")

# 얼굴 입력 가능한 Slave 찾기
slaveID, slaveCap = self.getFaceInputSupportedDevice(self.slaveIDs)
if slaveID is None:
    self.skipTest("no slave device supports face input")

# ID+PIN 입력 가능한 Slave 찾기
slaveID, slaveCap = self.getIdPinInputSupportedDevice(self.slaveIDs)
if slaveID is None:
    self.skipTest("no slave device supports ID+PIN input")
```

**헬퍼 메서드 (testCOMMONR 제공):**
- `getFingerprintInputSupportedDevice(slaveIDs)` → (deviceID, capability)
- `getCardInputSupportedDevice(slaveIDs)` → (deviceID, capability)
- `getFaceInputSupportedDevice(slaveIDs)` → (deviceID, capability)
- `getIdPinInputSupportedDevice(slaveIDs)` → (deviceID, capability)
- `getTNASupportedDevice(slaveIDs)` → (deviceID, capInfo)

---

### 4.3 디바이스 타입 확인

```python
# 디바이스 타입 조회
deviceType = self.svcManager.getDeviceType(self.targetID)

# Station 계열 디바이스 확인
if not util.kindOfStation(deviceType):
    self.skipTest("device is not a station type")

# 알파뉴메릭 ID 지원 확인
if not self.capInfo.alphanumericIDSupported:
    self.skipTest("alphanumeric ID not supported")
```

**주요 디바이스 타입 상수 (device_pb2):**
```python
device_pb2.BIOSTATION_2 = 1
device_pb2.BIOSTATION_A2 = 2
device_pb2.FACESTATION_2 = 3
device_pb2.BIOSTATION_L2 = 4
device_pb2.BIOENTRY_W2 = 5
device_pb2.CORESTATION_40 = 6
device_pb2.XSTATION_2 = 10
device_pb2.BIOSTATION_3 = 13
```

---

## Phase 5: 인증 모드 설정

### 5.1 인증 설정 조회 및 수정

#### 기본 패턴
```python
# 1. 현재 인증 설정 조회
authConf = self.svcManager.getAuthConfig(deviceID)

# 2. 기존 스케줄 삭제
authConf.authSchedules.clear()

# 3. 새 인증 모드 추가
# 확장 모드 지원 확인 후 설정
if self.capability.extendedFingerprintPINSupported:
    authConf.authSchedules.append(
        auth_pb2.AuthSchedule(
            mode=auth_pb2.AUTH_EXT_MODE_FINGERPRINT_PIN,
            scheduleID=1  # 1 = 항상 활성 (Always)
        )
    )
else:
    # Fallback to basic mode
    authConf.authSchedules.append(
        auth_pb2.AuthSchedule(
            mode=auth_pb2.AUTH_MODE_BIOMETRIC_PIN,
            scheduleID=1
        )
    )

# 4. 설정 적용
self.svcManager.setAuthConfig(deviceID, authConf)

# 5. 설정 적용 대기 (중요!)
time.sleep(0.5)  # 최소 500ms 대기
```

---

### 5.2 인증 모드 상수

#### 기본 모드 (auth_pb2.AUTH_MODE_*)
```python
AUTH_MODE_CARD_ONLY = 0         # 카드만
AUTH_MODE_BIOMETRIC_ONLY = 1    # 바이오메트릭만 (지문 또는 얼굴)
AUTH_MODE_ID_PIN = 2            # ID + PIN
AUTH_MODE_BIOMETRIC_PIN = 3     # 바이오메트릭 + PIN
```

#### 확장 모드 (auth_pb2.AUTH_EXT_MODE_*)
```python
AUTH_EXT_MODE_CARD_ONLY = 0                     # 카드만
AUTH_EXT_MODE_FINGERPRINT_ONLY = 1              # 지문만
AUTH_EXT_MODE_FACE_ONLY = 2                     # 얼굴만
AUTH_EXT_MODE_ID_PIN = 3                        # ID + PIN
AUTH_EXT_MODE_FINGERPRINT_PIN = 4               # 지문 + PIN
AUTH_EXT_MODE_FINGERPRINT_FACE = 7              # 지문 + 얼굴
AUTH_EXT_MODE_FINGERPRINT_FACE_OR_PIN = 8       # (지문 + 얼굴) 또는 (지문 + PIN)
AUTH_EXT_MODE_FINGERPRINT_FACE_PIN = 9          # 지문 + 얼굴 + PIN
```

---

### 5.3 헬퍼 메서드 활용

testCOMMONR 클래스가 제공하는 헬퍼 메서드 사용:

#### 여러 모드 동시 활성화
```python
backup = self.setAuthmodeEnabled(
    deviceID=self.targetID,
    capability=self.capability,
    cardEnabled=True,      # 카드 모드 활성화
    idEnabled=True,        # ID+PIN 모드 활성화
    fingerEnabled=True,    # 지문 모드 활성화
    faceEnabled=True,      # 얼굴 모드 활성화
    scheduleID=1           # 항상 활성
)
# 반환값: 백업된 원본 AuthConfig
```

#### 단일 모드 설정
```python
# 카드 전용 모드
backup = self.setCardOnlyAuthMode(
    deviceID=self.targetID,
    capability=self.capability,
    scheduleID=1
)

# 지문 전용 모드
backup = self.setFingerprintOnlyAuthMode(
    deviceID=self.targetID,
    capability=self.capability,
    scheduleID=1
)

# 얼굴 전용 모드
backup = self.setFaceOnlyAuthMode(
    deviceID=self.targetID,
    capability=self.capability,
    scheduleID=1
)
```

---

### 5.4 스케줄 ID 의미

```python
scheduleID = 1   # 항상 활성 (Always) - 가장 많이 사용
scheduleID = 2   # 사용자 정의 스케줄 1
scheduleID = 3   # 사용자 정의 스케줄 2
# ...
```

**스케줄 ID 1 (Always):**
- 24시간 365일 활성
- 테스트에서 가장 많이 사용
- 별도 스케줄 설정 불필요

---

### 5.5 기타 인증 설정

```python
authConf = self.svcManager.getAuthConfig(deviceID)

# Private Auth 비활성화 (전역 인증 모드 사용)
authConf.usePrivateAuth = False

# Match Timeout 설정 (1~20초)
authConf.matchTimeout = 5  # 초

# Timeout 범위 상수
import auth_pb2
min_timeout = auth_pb2.MIN_MATCH_TIMEOUT  # 1초
max_timeout = auth_pb2.MAX_MATCH_TIMEOUT  # 20초

# 랜덤 timeout 설정 예시
authConf.matchTimeout = random.randint(min_timeout, max_timeout)

# 설정 적용
self.svcManager.setAuthConfig(deviceID, authConf)
time.sleep(0.5)
```

---

## Phase 6: 테스트 실행

### 6.1 사용자 등록

```python
# 사용자 등록
self.svcManager.enrollUsers(self.targetID, [user])

# 등록 검증
retrieved = self.svcManager.getUsers(self.targetID, [user.hdr.ID])
self.assertEqual(1, len(retrieved), "User not enrolled")
self.assertEqual(user.hdr.ID, retrieved[0].hdr.ID)

# 속성 검증
self.assertEqual(len(user.cards), len(retrieved[0].cards))
self.assertEqual(len(user.fingers), len(retrieved[0].fingers))
self.assertEqual(len(user.faces), len(retrieved[0].faces))
```

**주의사항:**
- PIN은 해싱되므로 직접 비교 불가
- 바이오메트릭 템플릿은 바이트 배열 길이로 검증

---

### 6.2 이벤트 모니터링 + 인증 시도

#### 기본 패턴
```python
with util.EventMonitor(
    svcManager=self.svcManager,
    masterID=self.targetID,
    eventCode=0x1301,          # 예상 이벤트 코드
    deviceID=authTargetID,     # Master 또는 Slave
    userID=user.hdr.ID,        # 필터: 특정 사용자만
    quiet=True                 # True: 매칭된 이벤트만 출력
) as m:
    # 인증 동작 수행
    finger = random.choice(user.fingers)
    self.svcManager.detectFingerprint(authTargetID, finger.templates[0])

    # 이벤트 발생 확인
    self.assertTrue(m.caught(timeout=5.0), "Expected event did not occur")
```

---

#### 지문 단일 인증
```python
with util.EventMonitor(
    self.svcManager,
    self.targetID,
    eventCode=0x1301,  # 지문 인증 성공
    deviceID=self.targetID,
    userID=user.hdr.ID
) as m:
    finger = random.choice(user.fingers)
    print(f"Detecting Fingerprint[{finger.index}]")
    self.svcManager.detectFingerprint(self.targetID, finger.templates[0])

    self.assertTrue(m.caught(timeout=5.0))
```

---

#### 지문 + PIN 복합 인증
```python
with util.EventMonitor(
    self.svcManager,
    self.targetID,
    eventCode=0x1302,  # 지문+PIN 인증 성공
    userID=user.hdr.ID
) as m:
    # 지문 인식
    finger = random.choice(user.fingers)
    self.svcManager.detectFingerprint(self.targetID, finger.templates[0])

    # PIN 입력
    self.svcManager.enterKey(self.targetID, plainPIN)

    self.assertTrue(m.caught(timeout=5.0))
```

---

#### 지문 + 얼굴 복합 인증
```python
with util.EventMonitor(
    self.svcManager,
    self.targetID,
    eventCode=0x1307,  # 지문+얼굴 인증 성공
    userID=user.hdr.ID
) as m:
    # 지문 인식
    finger = random.choice(user.fingers)
    self.svcManager.detectFingerprint(self.targetID, finger.templates[0])

    # 얼굴 인식
    face = random.choice(user.faces)
    self.svcManager.detectFace(self.targetID, face.templates[0])

    self.assertTrue(m.caught(timeout=5.0))
```

---

#### ID + PIN 인증
```python
with util.EventMonitor(
    self.svcManager,
    self.targetID,
    eventCode=0x1001,  # ID+PIN 인증 성공
    userID=user.hdr.ID
) as m:
    # ID 입력
    self.svcManager.enterKey(self.targetID, user.hdr.ID)

    # PIN 입력
    self.svcManager.enterKey(self.targetID, plainPIN)

    self.assertTrue(m.caught(timeout=5.0))
```

---

### 6.3 Master-Slave 구조 테스트

```python
# 1. Master에 사용자 등록
self.svcManager.enrollUsers(self.targetID, [user])

# 2. Slave 디바이스 선택
slaveID, slaveCap = self.getFingerprintInputSupportedDevice(self.slaveIDs)
if slaveID is None:
    self.skipTest("no slave supports fingerprint")

# 3. Master와 Slave 모두 인증 모드 설정
self.setAuthmodeEnabled(self.targetID, self.capability)
self.setAuthmodeEnabled(slaveID, slaveCap, fingerEnabled=True)

# 4. Slave에서 인증 테스트
with util.EventMonitor(
    self.svcManager,
    self.targetID,              # Master ID (이벤트는 Master로 전송됨)
    eventCode=0x1301,
    deviceID=slaveID,           # Slave ID (필터)
    userID=user.hdr.ID
) as m:
    # Slave 디바이스에서 지문 인식
    self.svcManager.detectFingerprint(slaveID, finger.templates[0])

    self.assertTrue(m.caught())
```

---

## Phase 7: 결과 검증

### 7.1 상태 검증

```python
# 사용자 통계 확인
statistic = self.svcManager.getUserStatistic(self.targetID)

self.assertEqual(expected_count, statistic.numOfUsers)
self.assertEqual(expected_cards, statistic.numOfCards)
self.assertEqual(expected_fingers, statistic.numOfFingerprints)
self.assertEqual(expected_faces, statistic.numOfFaces)
```

---

### 7.2 설정 검증 (Set → Get 패턴)

```python
# 설정 변경
expected_timeout = 10
authConf.matchTimeout = expected_timeout
self.svcManager.setAuthConfig(deviceID, authConf)

# 조회
retrieved = self.svcManager.getAuthConfig(deviceID)

# 검증
self.assertEqual(
    expected_timeout,
    retrieved.matchTimeout,
    f"Expected timeout {expected_timeout}, got {retrieved.matchTimeout}"
)
```

---

### 7.3 이벤트 내용 검증

```python
with util.EventMonitor(...) as m:
    # 동작 수행
    self.svcManager.detectFingerprint(...)

    # 이벤트 발생 확인
    caught = m.caught(timeout=5.0)
    self.assertTrue(caught, "Event not caught")

    # 이벤트 상세 내용 검증
    if caught:
        self.assertEqual(user.hdr.ID, m.description.userID)
        self.assertEqual(authTargetID, m.description.deviceID)
        self.assertEqual(expected_event_code, m.description.eventCode | m.description.subCode)
```

**EventMonitor.description 속성:**
```python
m.description.eventCode     # 메인 이벤트 코드
m.description.subCode       # 서브 코드
m.description.userID        # 사용자 ID
m.description.deviceID      # 디바이스 ID
m.description.timestamp     # 발생 시간
```

---

## 에러 처리 패턴

### gRPC 에러 처리

```python
try:
    self.svcManager.enrollUsers(deviceID, users)
except grpc.RpcError as e:
    print(f"gRPC Error: {e.code()} - {e.details()}")
    raise  # 테스트 실패 처리
```

---

### 타임아웃 처리

```python
with util.EventMonitor(...) as m:
    # 동작 수행
    self.svcManager.detectFingerprint(...)

    # 타임아웃 지정
    succeed = m.caught(timeout=10.0)

    if not succeed:
        self.fail("Expected event did not occur within 10 seconds")

    # 또는 조건부 처리
    if succeed:
        self.assertTrue(True)  # 성공
    else:
        print("Event timeout - test may need longer wait time")
```

---

### 설정 변경 후 대기

```python
# 인증 설정 변경 후
self.svcManager.setAuthConfig(deviceID, authConf)
time.sleep(0.5)  # 최소 500ms 대기

# 중요한 설정 변경은 더 긴 대기
self.svcManager.setFingerprintConfig(deviceID, fingerConf)
time.sleep(1.0)  # 1초 대기

# 대량 사용자 등록 후
self.svcManager.enrollUsers(deviceID, large_user_list)
time.sleep(2.0)  # 2초 대기
```

---

### skipTest 사용

```python
# 디바이스 능력 부족
if not self.capability.fingerprintInputSupported:
    self.skipTest("fingerprint not supported")

# 필요한 Slave 없음
slaveID, slaveCap = self.getFingerprintInputSupportedDevice(self.slaveIDs)
if slaveID is None:
    self.skipTest("no slave device supports fingerprint")

# 데이터 없음
if user is None:
    self.skipTest("no user data available")

# 알파뉴메릭 미지원
if not self.capInfo.alphanumericIDSupported:
    self.skipTest("alphanumeric ID not supported")
```

---

## 워크플로우 체크리스트

테스트 작성 시 다음 순서를 따르세요:

### ✅ 사전 준비
- [ ] 테스트 시나리오 분석 (Phase 1)
- [ ] 필요한 카테고리 추출 (user, auth, finger 등)
- [ ] 카테고리별 리소스 파일 확인 (proto, pb2, example)

### ✅ 코드 작성
- [ ] Import 문 작성 (카테고리별 pb2 모듈)
- [ ] 클래스 정의 및 docstring 작성
- [ ] setUp/tearDown 오버라이드 (필요 시)

### ✅ 테스트 로직
- [ ] Phase 3: 테스트 데이터 준비 (JSON 로드 + ID/PIN 생성)
- [ ] Phase 4: 디바이스 능력 검증 (skipTest 사용)
- [ ] Phase 5: 인증 모드 설정
- [ ] Phase 6: 사용자 등록 + EventMonitor + 인증 수행
- [ ] Phase 7: 결과 검증 (assertEqual/assertTrue)

### ✅ 에러 처리
- [ ] try-except로 gRPC 에러 처리
- [ ] timeout 설정 (EventMonitor)
- [ ] time.sleep() 추가 (설정 변경 후)
- [ ] skipTest 조건 확인

---

## 주요 이벤트 코드 참조

| 코드 | 설명 | 사용 시나리오 |
|------|------|--------------|
| `0x1001` | ID+PIN 인증 성공 | ID/PIN 모드 테스트 |
| `0x1301` | 지문 인증 성공 | 지문 단일 인증 |
| `0x1302` | 지문+PIN 인증 성공 | 지문+PIN 복합 인증 |
| `0x1303` | 카드+지문 인증 성공 | 카드+지문 복합 인증 |
| `0x1307` | 지문+얼굴 인증 성공 | 지문+얼굴 복합 인증 |
| `0x1308` | 지문+얼굴+PIN 인증 성공 | 3요소 복합 인증 |
| `0x2200` | 사용자 등록 이벤트 | 사용자 추가 검증 |

자세한 이벤트 코드는 `resources/event_codes.json` 참조

---

## 예제: 완전한 테스트 메서드

```python
def testCommonr_30_1_fingerprint_PIN_on_Master(self):
    """
    Master 디바이스에서 지문+PIN 복합 인증 테스트

    전제조건:
    - Master 디바이스가 지문 입력 지원
    - Master 디바이스가 PIN 입력 지원

    절차:
    1. 사용자 등록 (지문 + PIN)
    2. 지문+PIN 인증 모드 설정
    3. 지문 인식 + PIN 입력
    4. 인증 성공 이벤트 확인

    예상 결과:
    - 이벤트 코드 0x1302 발생
    """
    # Phase 3: 데이터 준비
    user = None
    for entry in os.listdir(self.getDataFilePath()):
        if entry.startswith("User") and entry.endswith(".json"):
            with open(self.getDataFilePath(jsonFileName=entry), 'utf-8') as f:
                from cli.menu.user.userMenu import UserBuilder
                user = json.load(f, cls=UserBuilder)
                break

    if user is None:
        self.skipTest("no user data")

    userId = util.randomNumericUserID()
    if self.capInfo.alphanumericIDSupported:
        userId = util.randomAlphanumericUserID()

    user.hdr.ID = userId
    plainPIN = util.generateRandomPIN()
    user.PIN = self.svcManager.hashPIN(plainPIN)

    # Phase 4: 디바이스 능력 검증
    if not self.capability.fingerprintInputSupported:
        self.skipTest("fingerprint not supported")

    if not self.capability.PINInputSupported:
        self.skipTest("PIN not supported")

    if self.capability.maxFingerprints == 0 or len(user.fingers) == 0:
        self.skipTest("no fingerprint data")

    # Phase 5: 인증 모드 설정
    authConf = self.svcManager.getAuthConfig(self.targetID)
    authConf.authSchedules.clear()

    if self.capability.extendedFingerprintPINSupported:
        authConf.authSchedules.append(
            auth_pb2.AuthSchedule(
                mode=auth_pb2.AUTH_EXT_MODE_FINGERPRINT_PIN,
                scheduleID=1
            )
        )
    else:
        authConf.authSchedules.append(
            auth_pb2.AuthSchedule(
                mode=auth_pb2.AUTH_MODE_BIOMETRIC_PIN,
                scheduleID=1
            )
        )

    self.svcManager.setAuthConfig(self.targetID, authConf)
    time.sleep(0.5)

    # Phase 6: 테스트 실행
    self.svcManager.enrollUsers(self.targetID, [user])

    retrieved = self.svcManager.getUsers(self.targetID, [user.hdr.ID])
    self.assertEqual(1, len(retrieved))

    with util.EventMonitor(
        self.svcManager,
        self.targetID,
        eventCode=0x1302,
        userID=user.hdr.ID
    ) as m:
        finger = random.choice(user.fingers)
        self.svcManager.detectFingerprint(self.targetID, finger.templates[0])
        self.svcManager.enterKey(self.targetID, plainPIN)

        # Phase 7: 검증
        self.assertTrue(m.caught(timeout=5.0))
```

---

## 마무리

이 워크플로우를 따르면:
1. **일관성**: 모든 테스트가 동일한 구조
2. **재현성**: 단계별로 추적 가능
3. **유지보수성**: 수정 및 확장 용이
4. **디버깅**: 에러 발생 시 단계 특정 가능

**다음 문서**: [02_REFERENCE_GUIDE.md](./02_REFERENCE_GUIDE.md) - 참조 파일 및 API 가이드
