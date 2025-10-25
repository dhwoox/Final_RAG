# G-SDK Python 자동화 테스트 참조 가이드

> **목적**: 이 문서는 테스트 작성 시 **어떤 파일을 어떻게 참조해야 하는지** 설명합니다.
> LLM이 능동적으로 필요한 리소스를 탐색하고 활용할 수 있도록 가이드합니다.

---

## 📋 목차

1. [카테고리 기반 리소스 탐색](#1-카테고리-기반-리소스-탐색)
2. [핵심 참조 파일](#2-핵심-참조-파일)
3. [카테고리별 상세 참조](#3-카테고리별-상세-참조)
4. [공식 문서 참조](#4-공식-문서-참조)
5. [참조 우선순위](#5-참조-우선순위)

---

## 1. 카테고리 기반 리소스 탐색

### 1.1 카테고리 식별 방법

테스트 요구사항에서 다음 키워드를 찾아 카테고리를 식별하세요:

| 카테고리 | 키워드 | 관련 파일 경로 | 주요 기능 |
|---------|--------|--------------|----------|
| `user` | 사용자, User, 등록, enroll, 조회, 삭제 | user.proto, user_pb2.py, example/user/ | 사용자 관리 |
| `auth` | 인증, Auth, 인증모드, AuthMode, AuthSchedule | auth.proto, auth_pb2.py, example/auth/ | 인증 설정 |
| `finger` | 지문, Fingerprint, 지문인증, 지문등록 | finger.proto, finger_pb2.py, example/finger/ | 지문 관리 |
| `face` | 얼굴, Face, 안면인식 | face.proto, face_pb2.py, example/face/ | 얼굴 관리 |
| `card` | 카드, Card, 스마트카드 | card.proto, card_pb2.py, example/card/ | 카드 관리 |
| `door` | 도어, Door, 출입문 | door.proto, door_pb2.py, example/door/ | 도어 관리 |
| `access` | 접근, Access, AccessGroup, AccessLevel, 권한 | access.proto, access_pb2.py, example/access/ | 접근 제어 |
| `event` | 이벤트, Event, 로그, Log, 모니터링 | event.proto, event_pb2.py, example/event/ | 이벤트 모니터링 |
| `device` | 디바이스, Device, Capability | device.proto, device_pb2.py, example/device/ | 디바이스 정보 |
| `schedule` | 스케줄, Schedule, 시간대 | schedule.proto, schedule_pb2.py, example/schedule/ | 스케줄 관리 |
| `connect` | 연결, Connect, 접속 | connect.proto, connect_pb2.py, example/connect/ | 디바이스 연결 |
| `zone` | Zone, APB, 구역 | zone.proto, zone_pb2.py, example/apb/ | 구역 관리 |
| `lift` | Lift, 엘리베이터 | lift.proto, lift_pb2.py, example/lift/ | 엘리베이터 |
| `tna` | TNA, 근태 | tna.proto, tna_pb2.py, example/tna/ | 근태 관리 |

**예시:**
> "지문 인증 테스트" → 카테고리: `user`, `auth`, `finger`, `event`

---

### 1.2 카테고리별 탐색 경로

카테고리를 식별했으면 다음 4가지 파일을 참조하세요:

```
{category}를 위한 리소스:
1. biostar/proto/{category}.proto        # 메시지 구조 정의
2. biostar/service/{category}_pb2.py     # Python 메시지 클래스
3. biostar/service/{category}_pb2_grpc.py # gRPC Stub
4. example/{category}/*.py               # 공식 래퍼 클래스
```

**구체적 예시 (auth 카테고리):**
```python
# 1. auth.proto에서 찾을 정보
# - AuthConfig 메시지 구조
# - AuthSchedule 메시지 구조
# - AUTH_MODE_* 상수 정의
# - 필드 타입 및 의미

# 2. auth_pb2.py에서 사용
import auth_pb2

# 메시지 생성
authConf = auth_pb2.AuthConfig()
authConf.authSchedules.append(
    auth_pb2.AuthSchedule(mode=auth_pb2.AUTH_EXT_MODE_FINGERPRINT_PIN)
)

# 상수 사용
mode = auth_pb2.AUTH_MODE_CARD_ONLY
min_timeout = auth_pb2.MIN_MATCH_TIMEOUT
max_timeout = auth_pb2.MAX_MATCH_TIMEOUT

# 3. auth_pb2_grpc.py
# (일반적으로 직접 사용 안 함, manager.py가 래핑함)

# 4. example/auth/auth.py에서 패턴 확인
# - getConfig() 사용법
# - setConfig() 에러 처리
# - 권장 사용 패턴
```

---

### 1.3 전체 카테고리 목록

`resources/category_map.json` 에서 46개 카테고리 전체 확인 가능:

```json
{
  "user": {...},
  "auth": {...},
  "finger": {...},
  "face": {...},
  "card": {...},
  "door": {...},
  "access": {...},
  "event": {...},
  "device": {...},
  "schedule": {...},
  "connect": {...},
  "apb_zone": {...},
  "timed_apb_zone": {...},
  "fire_zone": {...},
  "intrusion_zone": {...},
  "interlock_zone": {...},
  "lift_zone": {...},
  "lock_zone": {...},
  "lift": {...},
  "tna": {...},
  "admin": {...},
  "operator": {...},
  "tenant": {...},
  "gateway": {...},
  "master": {...},
  "server": {...},
  "action": {...},
  "display": {...},
  "input": {...},
  "network": {...},
  "rs485": {...},
  "status": {...},
  "system": {...},
  "thermal": {...},
  "time": {...},
  "udp": {...},
  "udp_master": {...},
  "voip": {...},
  "wiegand": {...},
  "rtsp": {...},
  "login": {...},
  "cert": {...},
  "err": {...},
  "test": {...},
  "zone": {...}
}
```

---

## 2. 핵심 참조 파일

### 2.1 manager.py - API 호출의 중앙 관리자

**위치**: `demo/manager.py`

**역할**: 모든 gRPC 서비스를 통합 관리하는 중앙 매니저

#### 서비스 구조
```python
# ServiceManager 인스턴스는 testCOMMONR에서 자동 제공
self.svcManager = ServiceManager(config)

# 주요 서비스 접근 패턴
self.svcManager.{서비스명}Svc.{메서드}(...)
```

#### 초기화되는 서비스 목록
```python
# 사용자 및 인증
self.svcManager.userSvc      # 사용자 관리
self.svcManager.authSvc      # 인증 설정
self.svcManager.cardSvc      # 카드 관리
self.svcManager.fingerSvc    # 지문 관리
self.svcManager.faceSvc      # 얼굴 관리

# 접근 제어
self.svcManager.doorSvc      # 도어 관리
self.svcManager.accessSvc    # 접근 그룹/레벨
self.svcManager.scheduleSvc  # 스케줄

# 이벤트 및 모니터링
self.svcManager.eventSvc     # 이벤트 로그

# 디바이스
self.svcManager.deviceSvc    # 디바이스 정보
self.svcManager.connectSvc   # 디바이스 연결

# 구역 관리
self.svcManager.apbZoneSvc   # APB 구역
self.svcManager.liftSvc      # 엘리베이터

# 시스템
self.svcManager.systemSvc    # 시스템 설정
self.svcManager.timeSvc      # 시간 설정
self.svcManager.networkSvc   # 네트워크 설정

# 기타 30+ 서비스...
```

---

#### 주요 통합 메서드

##### User 관리
| 메서드 | 내부 호출 | 파라미터 | 반환값 | 설명 |
|--------|----------|---------|--------|------|
| `enrollUsers(deviceID, users, overwrite=False)` | `userSvc.enroll()` | deviceID: int<br>users: list[UserInfo]<br>overwrite: bool | None | 사용자 등록 |
| `getUsers(deviceID, userIDs=[])` | `userSvc.getUser()` | deviceID: int<br>userIDs: list[str] | list[UserInfo] | 사용자 조회 (전체 또는 특정) |
| `removeUsers(deviceID, userIDs=[])` | `userSvc.delete()` or `userSvc.deleteAll()` | deviceID: int<br>userIDs: list[str] | None | 사용자 삭제 |
| `getUserStatistic(deviceID)` | `userSvc.getStatistic()` | deviceID: int | UserStatistic | 사용자 통계 조회 |
| `hashPIN(plainPIN)` | `userSvc.hashPIN()` | plainPIN: bytes | bytes | PIN 해싱 |

##### Device 관리
| 메서드 | 내부 호출 | 파라미터 | 반환값 | 설명 |
|--------|----------|---------|--------|------|
| `getDeviceCapability(deviceID)` | `deviceSvc.getCapInfo()` | deviceID: int | CapabilityInfo | 디바이스 기능 정보 |
| `getCapabilityInfo(deviceID)` | `deviceSvc.getCapInfo()` | deviceID: int | CapabilityInfo | 상세 기능 정보 |
| `getDeviceType(deviceID)` | `deviceSvc.getInfo()` | deviceID: int | int | 디바이스 타입 |
| `isRegistered(deviceID)` | 내부 로직 | deviceID: int | bool | 등록 여부 확인 |
| `isSlave(deviceID)` | 내부 로직 | deviceID: int | bool | 슬레이브 여부 |

##### Auth 설정
| 메서드 | 내부 호출 | 파라미터 | 반환값 | 설명 |
|--------|----------|---------|--------|------|
| `getAuthConfig(deviceID)` | `authSvc.getConfig()` | deviceID: int | AuthConfig | 인증 설정 조회 |
| `setAuthConfig(deviceID, config)` | `authSvc.setConfig()` | deviceID: int<br>config: AuthConfig | None | 인증 설정 변경 |

##### Fingerprint 설정
| 메서드 | 내부 호출 | 파라미터 | 반환값 | 설명 |
|--------|----------|---------|--------|------|
| `getFingerprintConfig(deviceID)` | `fingerSvc.getConfig()` | deviceID: int | FingerprintConfig | 지문 설정 조회 |
| `setFingerprintConfig(deviceID, config)` | `fingerSvc.setConfig()` | deviceID: int<br>config: FingerprintConfig | None | 지문 설정 변경 |
| `detectFingerprint(deviceID, templateData)` | `fingerSvc.scan()` | deviceID: int<br>templateData: bytes | None | 지문 인식 시뮬레이션 |

##### Face 설정
| 메서드 | 내부 호출 | 파라미터 | 반환값 | 설명 |
|--------|----------|---------|--------|------|
| `detectFace(deviceID, templateData)` | `faceSvc.detect()` | deviceID: int<br>templateData: bytes | None | 얼굴 인식 시뮬레이션 |

##### Event 관리
| 메서드 | 내부 호출 | 파라미터 | 반환값 | 설명 |
|--------|----------|---------|--------|------|
| `monitorLog(deviceID, enable)` | `eventSvc.enableMonitoring()` or `eventSvc.disableMonitoring()` | deviceID: int<br>enable: bool | None | 이벤트 모니터링 활성화 |
| `subscribeLog(queueSize)` | `eventSvc.subscribe()` | queueSize: int | iterator | 이벤트 스트림 구독 |
| `getEventDescription(eventCode)` | `eventSvc.getEventString()` | eventCode: int | str | 이벤트 코드 설명 |

##### Door 관리
| 메서드 | 내부 호출 | 파라미터 | 반환값 | 설명 |
|--------|----------|---------|--------|------|
| `getDoors(deviceID)` | `doorSvc.getList()` | deviceID: int | list[DoorInfo] | 도어 목록 조회 |
| `setDoor(deviceID, doorInfo)` | `doorSvc.set()` | deviceID: int<br>doorInfo: DoorInfo | None | 도어 설정 |
| `removeDoors(deviceID, doorIDs=[])` | `doorSvc.delete()` or `doorSvc.deleteAll()` | deviceID: int<br>doorIDs: list[int] | None | 도어 삭제 |

##### AccessLevel/Group 관리
| 메서드 | 내부 호출 | 파라미터 | 반환값 | 설명 |
|--------|----------|---------|--------|------|
| `getAccessLevels(deviceID)` | `accessSvc.getAccessLevels()` | deviceID: int | list[AccessLevel] | 접근 레벨 조회 |
| `setAccessLevel(deviceID, level)` | `accessSvc.setAccessLevel()` | deviceID: int<br>level: AccessLevel | None | 접근 레벨 설정 |
| `removeAccessLevels(deviceID, levelIDs=[])` | `accessSvc.deleteAccessLevel()` | deviceID: int<br>levelIDs: list[int] | None | 접근 레벨 삭제 |
| `getAccessGroups(deviceID)` | `accessSvc.getAccessGroups()` | deviceID: int | list[AccessGroup] | 접근 그룹 조회 |
| `setAccessGroup(deviceID, group)` | `accessSvc.setAccessGroup()` | deviceID: int<br>group: AccessGroup | None | 접근 그룹 설정 |
| `removeAccessGroups(deviceID, groupIDs=[])` | `accessSvc.deleteAccessGroup()` | deviceID: int<br>groupIDs: list[int] | None | 접근 그룹 삭제 |

##### Input 관리
| 메서드 | 내부 호출 | 파라미터 | 반환값 | 설명 |
|--------|----------|---------|--------|------|
| `enterKey(deviceID, key)` | `inputSvc.enterKey()` | deviceID: int<br>key: bytes or str | None | 키 입력 시뮬레이션 (PIN 입력 등) |

---

#### manager.py 탐색 팁
```python
# 1. manager.py 파일 열기
# 2. ServiceManager 클래스의 __init__ 메서드 확인 → 어떤 서비스가 초기화되는지
# 3. 필요한 메서드 검색 (예: "def enrollUsers")
# 4. 메서드 내부에서 self.{서비스}Svc.{메서드}() 패턴 확인
# 5. example/{서비스}/{서비스}.py 파일 참조하여 상세 사용법 확인
```

---

### 2.2 testCOMMONR.py - 테스트 베이스 클래스

**위치**: `demo/test/testCOMMONR.py`

**역할**: 모든 테스트의 부모 클래스, 공통 설정 및 헬퍼 제공

#### 상속 시 자동 제공 속성

```python
class testCOMMONR_XX_Y(TestCOMMONR):
    # 다음 속성들이 자동으로 사용 가능

    self.svcManager      # ServiceManager 인스턴스
    self.targetID        # 마스터 디바이스 ID (int)
    self.capability      # device_pb2.CapabilityInfo
    self.capInfo         # device_pb2.CapabilityInfo
    self.slaveIDs        # list[int] - 슬레이브 디바이스 ID 목록

    # setUp에서 자동 백업
    self.backupUsers           # list[UserInfo]
    self.backupAuthMode        # AuthConfig
    self.backupDoors           # list[DoorInfo]
    self.backupAccessLevels    # list[AccessLevel]
    self.backupAccessGroups    # list[AccessGroup]
```

---

#### 주요 헬퍼 메서드

##### 디바이스 선택 헬퍼
```python
def getFingerprintInputSupportedDevice(self, slaveIDs: list[int]) -> (int, CapabilityInfo):
    """
    지문 입력 가능한 슬레이브 디바이스 찾기

    Args:
        slaveIDs: 검색할 슬레이브 ID 리스트

    Returns:
        (deviceID, capability) 또는 (None, None)
    """
    for slaveID in slaveIDs:
        cap = self.svcManager.getDeviceCapability(slaveID)
        if cap.fingerprintInputSupported:
            return slaveID, cap
    return None, None
```

**사용 예시:**
```python
slaveID, slaveCap = self.getFingerprintInputSupportedDevice(self.slaveIDs)
if slaveID is None:
    self.skipTest("no slave supports fingerprint")
```

**유사 메서드:**
- `getCardInputSupportedDevice(slaveIDs)` → 카드 입력 가능 디바이스
- `getFaceInputSupportedDevice(slaveIDs)` → 얼굴 입력 가능 디바이스
- `getIdPinInputSupportedDevice(slaveIDs)` → ID+PIN 입력 가능 디바이스
- `getTNASupportedDevice(slaveIDs)` → TNA 지원 디바이스

---

##### 인증 모드 설정 헬퍼
```python
def setAuthmodeEnabled(self, deviceID, capability,
                       cardEnabled=True, idEnabled=True,
                       fingerEnabled=True, faceEnabled=True,
                       scheduleID=1):
    """
    여러 인증 모드 동시 활성화

    Args:
        deviceID: 디바이스 ID
        capability: 디바이스 Capability
        cardEnabled: 카드 인증 활성화 여부
        idEnabled: ID+PIN 인증 활성화 여부
        fingerEnabled: 지문 인증 활성화 여부
        faceEnabled: 얼굴 인증 활성화 여부
        scheduleID: 스케줄 ID (1=항상)

    Returns:
        백업된 원본 AuthConfig
    """
    backup = self.svcManager.getAuthConfig(deviceID)
    authConf = copy.deepcopy(backup)

    authConf.authSchedules.clear()

    if cardEnabled:
        authConf.authSchedules.append(
            self.makeAuthSch(
                capability.extendedCardOnlySupported,
                auth_pb2.AUTH_MODE_CARD_ONLY,
                auth_pb2.AUTH_EXT_MODE_CARD_ONLY,
                scheduleID
            )
        )

    if idEnabled:
        authConf.authSchedules.append(
            self.makeAuthSch(
                capability.extendedIdPINSupported,
                auth_pb2.AUTH_MODE_ID_PIN,
                auth_pb2.AUTH_EXT_MODE_ID_PIN,
                scheduleID
            )
        )

    if fingerEnabled:
        authConf.authSchedules.append(
            self.makeAuthSch(
                capability.extendedFingerprintOnlySupported,
                auth_pb2.AUTH_MODE_BIOMETRIC_ONLY,
                auth_pb2.AUTH_EXT_MODE_FINGERPRINT_ONLY,
                scheduleID
            )
        )

    if faceEnabled:
        authConf.authSchedules.append(
            self.makeAuthSch(
                capability.extendedFaceOnlySupported,
                auth_pb2.AUTH_MODE_BIOMETRIC_ONLY,
                auth_pb2.AUTH_EXT_MODE_FACE_ONLY,
                scheduleID
            )
        )

    self.svcManager.setAuthConfig(deviceID, authConf)
    return backup
```

**사용 예시:**
```python
# 지문과 얼굴 모드만 활성화
backup = self.setAuthmodeEnabled(
    self.targetID,
    self.capability,
    cardEnabled=False,
    idEnabled=False,
    fingerEnabled=True,
    faceEnabled=True
)
```

---

**단일 모드 설정 헬퍼:**
```python
def setCardOnlyAuthMode(self, deviceID, capability, scheduleID=1):
    """카드 전용 인증 모드 설정"""
    pass

def setFingerprintOnlyAuthMode(self, deviceID, capability, scheduleID=1):
    """지문 전용 인증 모드 설정"""
    pass

def setFaceOnlyAuthMode(self, deviceID, capability, scheduleID=1):
    """얼굴 전용 인증 모드 설정"""
    pass
```

---

##### 인증 스케줄 생성 헬퍼
```python
def makeAuthSch(self, isExtended: bool,
                basicMode: auth_pb2.AuthMode = auth_pb2.AUTH_MODE_CARD_ONLY,
                extMode: auth_pb2.AuthMode = auth_pb2.AUTH_EXT_MODE_CARD_ONLY,
                scheduleID: int = 1) -> auth_pb2.AuthSchedule:
    """
    디바이스 능력에 따라 적절한 AuthSchedule 생성

    Args:
        isExtended: 확장 모드 지원 여부
        basicMode: 기본 모드
        extMode: 확장 모드
        scheduleID: 스케줄 ID

    Returns:
        AuthSchedule 객체
    """
    if isExtended:
        return auth_pb2.AuthSchedule(mode=extMode, scheduleID=scheduleID)
    return auth_pb2.AuthSchedule(mode=basicMode, scheduleID=scheduleID)
```

---

##### 경로 헬퍼
```python
def getConfigPath(self, jsonFilename="config.json") -> str:
    """config.json 경로 반환"""
    biostarAutoTestBasePath = os.environ.get("BIOSTAR_AUTO_TEST_BASE_PATH")
    if biostarAutoTestBasePath:
        return os.path.join(biostarAutoTestBasePath, jsonFilename)
    return os.path.join(os.getcwd(), jsonFilename)

def getEnvironPath(self, jsonFilename="environ.json", directoryName="test") -> str:
    """environ.json 경로 반환"""
    biostarAutoTestBasePath = os.environ.get("BIOSTAR_AUTO_TEST_BASE_PATH")
    if biostarAutoTestBasePath:
        return os.path.join(biostarAutoTestBasePath, directoryName, jsonFilename)
    return os.path.join(os.getcwd(), directoryName, jsonFilename)

def getDataFilePath(self, jsonFileName=None, directoryName="data") -> str:
    """
    데이터 파일 경로 반환

    Args:
        jsonFileName: 파일명 (None이면 디렉토리 경로만)
        directoryName: 데이터 디렉토리 (기본 "data")

    Returns:
        전체 경로
    """
    biostarAutoTestBasePath = os.environ.get("BIOSTAR_AUTO_TEST_BASE_PATH")
    if biostarAutoTestBasePath:
        pathName = os.path.join(biostarAutoTestBasePath, directoryName)
    else:
        pathName = os.path.join(os.getcwd(), directoryName)

    if jsonFileName:
        pathName = os.path.join(pathName, jsonFileName)

    return pathName
```

---

#### setUp/tearDown 흐름

**setUp 자동 처리:**
```python
def setUp(self):
    # 1. config.json 로드 → ServiceManager 생성
    with open(self.getConfigPath(), encoding='UTF-8') as f:
        config = json.load(f)
        self.svcManager = ServiceManager(config)

    # 2. environ.json 로드 → targetID, slaveIDs 추출
    with open(self.getEnvironPath(), encoding='UTF-8') as f:
        environ = json.load(f)
        self.targetID = environ["devices"][0]["id"]
        slavesInfo = environ["devices"][0].get("slaves", [])
        for slave in slavesInfo:
            self.slaveIDs.append(slave["id"])

    # 3. 디바이스 등록 확인
    self.assertTrue(self.svcManager.isRegistered(self.targetID))

    # 4. Capability 조회
    self.capability = self.svcManager.getDeviceCapability(self.targetID)
    self.capInfo = self.svcManager.getCapabilityInfo(self.targetID)

    # 5. 백업
    self.backupAuthMode = self.svcManager.getAuthConfig(self.targetID)
    self.backupUsers = self.svcManager.getUsers(self.targetID)
    self.backupDoors = self.svcManager.getDoors(self.targetID)
    self.backupAccessLevels = self.svcManager.getAccessLevels(self.targetID)
    self.backupAccessGroups = self.svcManager.getAccessGroups(self.targetID)

    # 6. 초기화
    self.svcManager.removeUsers(self.targetID)
    self.svcManager.removeDoors(self.targetID)
    self.svcManager.removeAccessLevels(self.targetID)
    self.svcManager.removeAccessGroups(self.targetID)
```

**tearDown 자동 처리:**
```python
def tearDown(self):
    # 1. 인증 설정 복원
    self.svcManager.setAuthConfig(self.targetID, self.backupAuthMode)

    # 2. 테스트 사용자 삭제
    self.svcManager.removeUsers(self.targetID)

    # 3. 백업 사용자 복원
    if self.backupUsers:
        self.svcManager.enrollUsers(self.targetID, self.backupUsers)

    # 4. Door/AccessLevel/AccessGroup 복원
    self.svcManager.removeDoors(self.targetID)
    self.svcManager.removeAccessLevels(self.targetID)
    self.svcManager.removeAccessGroups(self.targetID)

    for door in self.backupDoors:
        self.svcManager.setDoor(self.targetID, door)

    for level in self.backupAccessLevels:
        self.svcManager.setAccessLevel(self.targetID, level)

    for group in self.backupAccessGroups:
        self.svcManager.setAccessGroup(self.targetID, group)
```

---

### 2.3 util.py - 유틸리티 함수

**위치**: `demo/test/util.py`

**역할**: 공통 헬퍼 함수 및 EventMonitor 클래스

#### 1) EventMonitor 클래스

```python
class EventMonitor:
    """실시간 이벤트 모니터링"""

    def __init__(self, svcManager, masterID,
                 eventCode=0x0000, deviceID=None,
                 userID=None, cardID=None, entityID=None,
                 quiet=False, startInstantly=True):
        """
        Args:
            svcManager: ServiceManager 인스턴스
            masterID: 마스터 디바이스 ID
            eventCode: 필터링할 이벤트 코드 (0x0000=전체)
            deviceID: 필터링할 디바이스 ID (None=전체)
            userID: 필터링할 사용자 ID (None=전체)
            cardID: 필터링할 카드 ID (None=전체)
            entityID: 필터링할 엔티티 ID (None=전체)
            quiet: True시 매칭된 이벤트만 출력
            startInstantly: 즉시 모니터링 시작 여부
        """

    def caught(self, timeout=3.0) -> bool:
        """
        이벤트 발생 대기

        Args:
            timeout: 대기 시간 (초)

        Returns:
            bool: timeout 내 이벤트 발생 여부
        """

    def start(self):
        """모니터링 시작"""

    def stop(self):
        """모니터링 종료"""
```

**사용 패턴:**
```python
# Context Manager 사용 (권장)
with util.EventMonitor(
    svcManager=self.svcManager,
    masterID=self.targetID,
    eventCode=0x1301,      # 필터: 지문 인증 성공만
    deviceID=slaveID,      # 필터: 특정 디바이스만
    userID=user.hdr.ID,    # 필터: 특정 사용자만
    quiet=True             # 매칭된 이벤트만 출력
) as m:
    # 테스트 동작
    self.svcManager.detectFingerprint(slaveID, fingerTemplate)

    # 이벤트 발생 확인
    self.assertTrue(m.caught(timeout=5.0))

    # 이벤트 상세 정보 접근
    if m.caught():
        print(f"Event user: {m.description.userID}")
        print(f"Event device: {m.description.deviceID}")
```

---

#### 2) 랜덤 데이터 생성 함수

##### User ID 생성
```python
def randomNumericUserID() -> str:
    """
    숫자형 사용자 ID 생성

    Returns:
        str: "1" ~ "4294967294" 범위의 문자열
    """
    availableUserID = random.randint(1, 4294967294)
    return str(availableUserID)
```

```python
def randomAlphanumericUserID(lenOfUserID=0, expending=[]) -> str:
    """
    알파뉴메릭 사용자 ID 생성

    Args:
        lenOfUserID: 길이 (0이면 1~32 랜덤)
        expending: 추가 허용 문자 리스트

    Returns:
        str: 최대 32자의 알파뉴메릭 ID

    Raises:
        ValueError: 길이가 32 초과인 경우
    """
    candidates = ['a', 'b', 'c', ..., '9', '_', '-']
    if expending:
        candidates.extend(expending)

    random.shuffle(candidates)

    if lenOfUserID == 0:
        lenOfUserID = random.randint(1, 32)

    availableUserID = ''.join(candidates[:lenOfUserID])

    if len(availableUserID) > 32:
        raise ValueError

    return availableUserID
```

---

##### PIN 생성
```python
def generateRandomPIN(lengthOfPin=0, minLenOfPin=4, maxLenOfPin=16) -> bytes:
    """
    랜덤 PIN 생성

    Args:
        lengthOfPin: PIN 길이 (0이면 랜덤)
        minLenOfPin: 최소 길이
        maxLenOfPin: 최대 길이

    Returns:
        bytes: PIN 번호 (예: b'123456')
    """
    if lengthOfPin == 0:
        lengthOfPin = random.randint(minLenOfPin, maxLenOfPin)

    candidates = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
    pin = ''.join([random.choice(candidates) for i in range(lengthOfPin)])

    return pin.encode('utf-8')
```

---

##### 카드 ID 생성
```python
def generateCardID(serial_number=0, length=32) -> bytes:
    """
    카드 ID 생성

    Args:
        serial_number: 시리얼 번호 (0이면 랜덤)
        length: 바이트 길이 (기본 32)

    Returns:
        bytes: 카드 ID 데이터
    """
    if serial_number == 0:
        serial_number = random.randint(1, 0xffffffff)

    v = serial_number
    digits = bytearray()

    while v > 0:
        v, r = v // 256, v % 256
        digits.append(r)

    assert(len(digits) <= length)

    digits += bytearray(length - len(digits))
    digits.reverse()

    return bytes(digits)
```

---

##### 이름 생성
```python
def generateRandomName(deviceType, includeKorean=False,
                       lengthOfName=0, maxLength=48) -> str:
    """
    랜덤 사용자 이름 생성

    Args:
        deviceType: 디바이스 타입
        includeKorean: 한글 포함 여부
        lengthOfName: 이름 길이 (0이면 랜덤)
        maxLength: 최대 길이

    Returns:
        str: 랜덤 이름
    """
    candidates = ['a', 'b', ..., '9', '~', '!', '@', ...]

    if deviceType != device_pb2.UNKNOWN:
        candidates.extend(["\\", "/", "'", ":", "*", "?", '"', "`", "<", ">", "|", "."])

    if lengthOfName == 0:
        lengthOfName = random.randint(1, maxLength)

    name = ''.join([random.choice(candidates) for i in range(lengthOfName)])

    if includeKorean:
        faker = Faker("ko-KR")
        name = faker.name() + name
        name = name[:lengthOfName]

    return name
```

---

##### 날짜/시간 생성
```python
def generateRandomDateTime(
    minDateTime=datetime.datetime(2001, 1, 1, 0, 0),
    maxDateTime=datetime.datetime(2030, 12, 31, 23, 59)
) -> datetime.datetime:
    """
    랜덤 날짜/시간 생성

    Args:
        minDateTime: 최소 날짜/시간
        maxDateTime: 최대 날짜/시간

    Returns:
        datetime.datetime: 랜덤 날짜/시간
    """
    minimum = int(time.mktime(minDateTime.timetuple()))
    maximum = int(time.mktime(maxDateTime.timetuple()))

    return datetime.datetime.fromtimestamp(random.randrange(minimum, maximum))
```

---

#### 3) 스케줄 검증 함수

```python
def onSchedule(schedule, holidayGroups, timestamp) -> bool:
    """
    주어진 시간이 스케줄 범위 내인지 확인

    Args:
        schedule: schedule_pb2.Schedule
        holidayGroups: list[HolidayGroup]
        timestamp: unix timestamp

    Returns:
        bool: 스케줄 내 포함 여부
    """
    pass

def onHoliday(holiday, timestamp) -> bool:
    """
    주어진 시간이 휴일인지 확인

    Returns:
        bool: 휴일 여부
    """
    pass

def onHolidayGroup(holidayGroup, timestamp) -> bool:
    """
    주어진 시간이 휴일 그룹 내 포함되는지 확인

    Returns:
        bool: 휴일 그룹 내 포함 여부
    """
    pass
```

---

#### 4) 디바이스 타입 확인

```python
def kindOfStation(deviceType: int) -> bool:
    """
    Station 계열 디바이스 여부 확인

    Args:
        deviceType: device_pb2의 디바이스 타입 상수

    Returns:
        bool: BioStation/FaceStation/CoreStation/XStation 등이면 True
    """
    if deviceType in [
        device_pb2.BIOSTATION_2,
        device_pb2.BIOSTATION_A2,
        device_pb2.FACESTATION_2,
        device_pb2.BIOSTATION_L2,
        device_pb2.BIOENTRY_W2,
        device_pb2.CORESTATION_40,
        device_pb2.FACESTATION_F2_FP,
        device_pb2.FACESTATION_F2,
        device_pb2.XSTATION_2_QR,
        device_pb2.XSTATION_2,
        device_pb2.XSTATION_2_FP,
        device_pb2.BIOSTATION_3,
        device_pb2.BIOSTATION_2A
    ]:
        return True
    return False
```

---

#### 5) 설정 파일 로더

```python
def loadAuthConfig(path) -> auth_pb2.AuthConfig:
    """JSON 파일에서 AuthConfig 로드"""
    with open(path) as f:
        from cli.menu.config.auth.authConfigMenu import AuthConfigBuilder
        return json.load(f, cls=AuthConfigBuilder)

def loadDoor(path) -> door_pb2.DoorInfo:
    """JSON 파일에서 DoorInfo 로드"""
    with open(path) as f:
        from cli.menu.door.doorMenu import DoorBuilder
        return json.load(f, cls=DoorBuilder)

def loadUser(path) -> user_pb2.UserInfo:
    """JSON 파일에서 UserInfo 로드"""
    with open(path) as f:
        from cli.menu.user.userMenu import UserBuilder
        return json.load(f, cls=UserBuilder)

# 유사 함수들:
# - loadAccessGroup(path)
# - loadAccessLevel(path)
# - loadAccessSchedule(path)
# - loadHolidayGroup(path)
# - loadAPBZone(path)
# - loadDisplayConfig(path)
# - loadDstConfig(path)
# - loadStatusConfig(path)
# - loadWiegandConfig(path)
```

---

## 3. 카테고리별 상세 참조

이 섹션에서는 자주 사용되는 카테고리별로 상세 참조 정보를 제공합니다.

### 3.1 user 카테고리

**관련 파일:**
- `biostar/proto/user.proto` - UserInfo, UserHdr, UserSetting 정의
- `biostar/service/user_pb2.py` - Python 메시지 클래스
- `example/user/user.py` - UserSvc 클래스

#### 주요 메시지 구조

```python
# UserInfo 전체 구조
user_pb2.UserInfo(
    hdr=user_pb2.UserHdr(
        ID="사용자ID",              # str
        numOfCard=1,               # int
        numOfFinger=2,             # int
        numOfFace=1,               # int
        numOfPhoto=0               # int
    ),
    setting=user_pb2.UserSetting(
        startTime=0,               # uint32 (unix timestamp)
        endTime=0,                 # uint32 (unix timestamp)
        biometricAuthMode=0,       # uint32
        cardAuthMode=0,            # uint32
        IDAuthMode=0,              # uint32
        securityLevel=0            # uint32
    ),
    name="사용자이름",              # str (최대 48자)
    cards=[                        # CardData 리스트
        user_pb2.CardData(
            cardData=bytes_data    # bytes (32바이트)
        )
    ],
    fingers=[                      # FingerData 리스트
        user_pb2.FingerData(
            index=0,               # int (0-9)
            flag=0,                # int
            templates=[bytes_data] # list[bytes]
        )
    ],
    faces=[                        # FaceData 리스트
        user_pb2.FaceData(
            index=0,               # int
            flag=0,                # int
            templates=[bytes_data] # list[bytes]
        )
    ],
    PIN=hashed_pin_bytes,          # bytes (해싱된 PIN)
    accessGroupIDs=[1, 2],         # list[int]
    jobCodes=[                     # list[JobCode]
        user_pb2.JobCode(...)
    ],
    photo=image_bytes              # bytes (JPEG 이미지)
)
```

#### example/user/user.py 주요 메서드

```python
class UserSvc:
    def getList(self, deviceID) -> list[user_pb2.UserHdr]:
        """사용자 목록 조회 (헤더만)"""

    def getUser(self, deviceID, userIDs, mask=user_pb2.USER_MASK_ALL) -> list[user_pb2.UserInfo]:
        """
        사용자 상세 정보 조회

        Args:
            deviceID: 디바이스 ID
            userIDs: 사용자 ID 리스트 (빈 리스트면 전체)
            mask: 조회할 정보 마스크

        Returns:
            list[UserInfo]
        """

    def enroll(self, deviceID, users, overwrite):
        """
        사용자 등록

        Args:
            deviceID: 디바이스 ID
            users: list[UserInfo]
            overwrite: 기존 사용자 덮어쓰기 여부
        """

    def update(self, deviceID, users):
        """사용자 정보 업데이트"""

    def delete(self, deviceID, userIDs):
        """특정 사용자 삭제"""

    def deleteAll(self, deviceID):
        """모든 사용자 삭제"""

    def setFinger(self, deviceID, userFingers):
        """사용자 지문 설정"""

    def setCard(self, deviceID, userCards):
        """사용자 카드 설정"""

    def setFace(self, deviceID, userFaces):
        """사용자 얼굴 설정"""

    def hashPIN(self, userPIN) -> bytes:
        """PIN 해싱"""

    def getStatistic(self, deviceID) -> user_pb2.UserStatistic:
        """
        사용자 통계 조회

        Returns:
            UserStatistic(
                numOfUsers=int,
                numOfCards=int,
                numOfFingerprints=int,
                numOfFaces=int
            )
        """
```

---

### 3.2 auth 카테고리

**관련 파일:**
- `biostar/proto/auth.proto`
- `biostar/service/auth_pb2.py`
- `example/auth/auth.py`

#### 주요 상수

```python
# 기본 모드 (auth_pb2.AUTH_MODE_*)
AUTH_MODE_CARD_ONLY = 0         # 카드만
AUTH_MODE_BIOMETRIC_ONLY = 1    # 바이오메트릭만
AUTH_MODE_ID_PIN = 2            # ID + PIN
AUTH_MODE_BIOMETRIC_PIN = 3     # 바이오메트릭 + PIN
AUTH_MODE_CARD_BIOMETRIC = 4    # 카드 + 바이오메트릭
AUTH_MODE_CARD_PIN = 5          # 카드 + PIN
AUTH_MODE_CARD_BIOMETRIC_OR_PIN = 6  # 카드 + (바이오메트릭 또는 PIN)
AUTH_MODE_CARD_BIOMETRIC_PIN = 7     # 카드 + 바이오메트릭 + PIN
AUTH_MODE_ID_BIOMETRIC = 8      # ID + 바이오메트릭

# 확장 모드 (auth_pb2.AUTH_EXT_MODE_*)
AUTH_EXT_MODE_CARD_ONLY = 0
AUTH_EXT_MODE_FINGERPRINT_ONLY = 1
AUTH_EXT_MODE_FACE_ONLY = 2
AUTH_EXT_MODE_ID_PIN = 3
AUTH_EXT_MODE_FINGERPRINT_PIN = 4
AUTH_EXT_MODE_CARD_FINGERPRINT = 5
AUTH_EXT_MODE_CARD_FACE = 6
AUTH_EXT_MODE_FINGERPRINT_FACE = 7
AUTH_EXT_MODE_FINGERPRINT_FACE_OR_PIN = 8
AUTH_EXT_MODE_FINGERPRINT_FACE_PIN = 9
# ... 추가 모드들

# Timeout 상수
MIN_MATCH_TIMEOUT = 1   # 초
MAX_MATCH_TIMEOUT = 20  # 초
```

#### 메시지 구조

```python
auth_pb2.AuthConfig(
    authSchedules=[
        auth_pb2.AuthSchedule(
            mode=AUTH_EXT_MODE_FINGERPRINT_PIN,  # 인증 모드
            scheduleID=1                          # 스케줄 ID
        )
    ],
    usePrivateAuth=False,    # 전역/개인 인증 모드
    useGlobalAPB=False,      # 전역 APB 사용
    matchTimeout=5,          # 매칭 타임아웃 (1~20초)
    authTimeout=10           # 인증 타임아웃 (초)
)
```

#### example/auth/auth.py 주요 메서드

```python
class AuthSvc:
    def getConfig(self, deviceID) -> auth_pb2.AuthConfig:
        """인증 설정 조회"""

    def setConfig(self, deviceID, config):
        """인증 설정 변경"""

    def setConfigMulti(self, deviceIDs, config):
        """여러 디바이스 인증 설정 변경"""
```

---

### 3.3 event 카테고리

**관련 파일:**
- `biostar/proto/event.proto`
- `biostar/service/event_pb2.py`
- `example/event/event.py`
- `event_code.json` - 이벤트 코드 매핑

#### 주요 이벤트 코드

| 코드 | 설명 | 사용 시나리오 |
|------|------|--------------|
| `0x1000` | ID 인증 실패 | ID 인증 테스트 |
| `0x1001` | ID+PIN 인증 성공 | ID+PIN 모드 테스트 |
| `0x1300` | 지문 인증 실패 | 지문 인증 실패 검증 |
| `0x1301` | 지문 인증 성공 | 지문 단일 인증 |
| `0x1302` | 지문+PIN 인증 성공 | 지문+PIN 복합 인증 |
| `0x1303` | 카드+지문 인증 성공 | 카드+지문 복합 인증 |
| `0x1304` | 카드+얼굴 인증 성공 | 카드+얼굴 복합 인증 |
| `0x1305` | 얼굴 인증 성공 | 얼굴 단일 인증 |
| `0x1306` | 얼굴+PIN 인증 성공 | 얼굴+PIN 복합 인증 |
| `0x1307` | 지문+얼굴 인증 성공 | 지문+얼굴 복합 인증 |
| `0x1308` | 지문+얼굴+PIN 인증 성공 | 3요소 복합 인증 |
| `0x2200` | 사용자 등록 | 사용자 추가 검증 |
| `0x2201` | 사용자 삭제 | 사용자 삭제 검증 |

자세한 이벤트 코드는 `resources/event_codes.json` 참조

#### example/event/event.py 주요 메서드

```python
class EventSvc:
    def getLog(self, deviceID, startEventID, maxNumOfLog) -> list[event_pb2.EventLog]:
        """이벤트 로그 조회"""

    def getLogWithFilter(self, deviceID, startEventID, maxNumOfLog, filters) -> list[event_pb2.EventLog]:
        """필터 적용 이벤트 로그 조회"""

    def clearLog(self, deviceID):
        """이벤트 로그 삭제"""

    def enableMonitoring(self, deviceID):
        """실시간 모니터링 활성화"""

    def disableMonitoring(self, deviceID):
        """실시간 모니터링 비활성화"""

    def subscribe(self, queueSize) -> iterator:
        """
        이벤트 스트림 구독

        Args:
            queueSize: 큐 크기

        Returns:
            iterator: 이벤트 스트림
        """

    def initCodeMap(self, filename):
        """event_code.json 로드"""

    def getEventString(self, eventCode, subCode) -> str:
        """이벤트 코드 설명 반환"""
```

---

### 3.4 device 카테고리

**관련 파일:**
- `biostar/proto/device.proto`
- `biostar/service/device_pb2.py`
- `example/device/device.py`

#### 주요 디바이스 타입 상수

```python
# device_pb2
UNKNOWN = 0
BIOSTATION_2 = 1
BIOSTATION_A2 = 2
FACESTATION_2 = 3
BIOSTATION_L2 = 4
BIOENTRY_W2 = 5
CORESTATION_40 = 6
FACESTATION_F2_FP = 7
FACESTATION_F2 = 8
XSTATION_2_QR = 9
XSTATION_2 = 10
XSTATION_2_FP = 11
BIOSTATION_3 = 13
BIOSTATION_2A = 14
```

#### CapabilityInfo 주요 속성

```python
capability = svcManager.getDeviceCapability(deviceID)

# 입력 지원 여부 (bool)
capability.cardInputSupported           # 카드
capability.idInputSupported             # ID
capability.fingerprintInputSupported    # 지문
capability.PINInputSupported            # PIN
capability.faceInputSupported           # 얼굴

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
capability.maxCards           # 최대 카드 수
capability.maxFingerprints    # 최대 지문 수
capability.maxFaces           # 최대 얼굴 수
capability.maxUserImages      # 최대 사용자 이미지 수
```

---

## 4. 공식 문서 참조

### 4.1 G-SDK Python 공식 문서

**Base URL**: https://supremainc.github.io/g-sdk/python/

| 문서 URL | 내용 | 참조 시기 |
|---------|------|----------|
| [Quick Start](https://supremainc.github.io/g-sdk/python/quick) | 기본 연결, 서비스 생성 패턴 | 초기 설정 시 |
| [Connect](https://supremainc.github.io/g-sdk/python/connect) | 동기/비동기 연결, 에러 처리 | 연결 문제 발생 시 |
| [User](https://supremainc.github.io/g-sdk/python/user) | 사용자 관리 패턴 | 사용자 등록/조회 시 |
| [Event](https://supremainc.github.io/g-sdk/python/event) | 실시간 구독, 필터링, 이벤트 로그 | 이벤트 처리 시 |
| [Auth](https://supremainc.github.io/g-sdk/python/auth) | 인증 모드 설정, 스케줄 | 인증 설정 변경 시 |
| [Device](https://supremainc.github.io/g-sdk/python/device) | 디바이스 정보, Capability | Capability 확인 시 |
| [Fingerprint](https://supremainc.github.io/g-sdk/python/finger) | 지문 관리 | 지문 테스트 시 |
| [Face](https://supremainc.github.io/g-sdk/python/face) | 얼굴 관리 | 얼굴 테스트 시 |
| [Card](https://supremainc.github.io/g-sdk/python/card) | 카드 관리 | 카드 테스트 시 |
| [Door](https://supremainc.github.io/g-sdk/python/door) | 도어 관리 | 도어 설정 시 |
| [Access](https://supremainc.github.io/g-sdk/python/access) | 접근 제어 | AccessGroup/Level 설정 시 |

---

## 5. 참조 우선순위

테스트 작성 시 다음 순서로 참조하세요:

### 우선순위 1: testCOMMONR.py
헬퍼 메서드가 이미 있는지 먼저 확인
- 디바이스 선택: `getFingerprintInputSupportedDevice()` 등
- 인증 모드 설정: `setAuthmodeEnabled()`, `setCardOnlyAuthMode()` 등
- 경로: `getConfigPath()`, `getDataFilePath()` 등

### 우선순위 2: manager.py
고수준 통합 API 확인
- 사용자 관리: `enrollUsers()`, `getUsers()`, `removeUsers()`
- 인증 설정: `getAuthConfig()`, `setAuthConfig()`
- 디바이스 정보: `getDeviceCapability()`, `getDeviceType()`

### 우선순위 3: util.py
유틸리티 함수 및 EventMonitor
- 이벤트 모니터링: `EventMonitor` 클래스
- 랜덤 데이터: `randomNumericUserID()`, `generateRandomPIN()`
- 디바이스 타입 확인: `kindOfStation()`

### 우선순위 4: example/{category}/*.py
카테고리별 서비스 상세 사용법
- 메서드 시그니처 확인
- 에러 처리 패턴
- 권장 사용 사례

### 우선순위 5: {category}_pb2.py
메시지 구조 및 상수
- 메시지 필드 확인
- Enum 상수값
- 기본값 확인

### 우선순위 6: 공식 문서
표준 패턴 및 Best Practice
- API Reference
- Code Examples
- Troubleshooting

### 우선순위 7: {category}.proto
메시지 필드 상세 정의
- 필드 타입
- 필드 의미
- 제약사항

---

## 예시 시나리오: 지문+PIN 인증 테스트 작성

> **요구사항**: "Master 디바이스에서 지문+PIN 인증 테스트"

### 탐색 순서:

**1단계: testCOMMONR.py 확인**
- `setAuthmodeEnabled()` 메서드 발견 ✅
- 지문+PIN 모드 설정에 사용 가능

**2단계: manager.py 확인**
- `setAuthConfig()` 발견 → 인증 설정 변경
- `detectFingerprint()` 발견 → 지문 인식 시뮬레이션
- `enterKey()` 발견 → PIN 입력 시뮬레이션

**3단계: util.py 확인**
- `EventMonitor` 클래스 발견 → 이벤트 대기
- `generateRandomPIN()` 발견 → PIN 생성

**4단계: example/auth/auth.py 확인**
- `getConfig()`, `setConfig()` 사용 패턴 확인

**5단계: auth_pb2.py 확인**
- `AUTH_EXT_MODE_FINGERPRINT_PIN` 상수 발견
- 이벤트 코드 `0x1302` 확인 (지문+PIN 성공)

**6단계: 공식 문서 확인**
- Auth 페이지에서 인증 모드 조합 규칙 확인

**결과**: 필요한 모든 정보 수집 완료, 테스트 코드 작성 가능!

---

## 마무리

이 참조 가이드를 활용하여:
1. **빠른 검색**: 필요한 API를 우선순위에 따라 빠르게 찾기
2. **정확한 사용**: 공식 예제 및 헬퍼 메서드 활용
3. **효율적 개발**: 중복 코드 작성 방지

**다음 문서**: [03_TEST_DATA_GUIDE.md](./03_TEST_DATA_GUIDE.md) - 테스트 데이터 생성 및 검증 가이드
