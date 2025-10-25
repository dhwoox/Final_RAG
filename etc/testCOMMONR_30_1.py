import json
import unittest
from testCOMMONR import *
import user_pb2
import auth_pb2
import finger_pb2
import event_pb2
from manager import ServiceManager
import util

class testCOMMONR_30_1(TestCOMMONR):
    """
    COMMONR-30 테스트 케이스: 지문 인증 모드 설정 및 복합 인증 시나리오 검증
    - User> Add User (지문 + PIN 포함)
    - Device> 지문인증모드 설정 (AUTH_MODE_FINGERPRINT_ONLY, AUTH_MODE_FINGERPRINT_PIN)
    - 해당 사용자로 인증시도
    """

    def testCommonr_30_1_1_fingerprint_only_mode(self):
        """
        테스트 시나리오: 지문Only 모드에서 지문 인증 시도
        Test Step:
            1. User> Add User (지문 + PIN 포함)
            2. Device> 지문인증모드 설정 (AUTH_MODE_FINGERPRINT_ONLY)
            3. 해당 사용자로 지문 인증 시도
        Expected Result:
            - 인증 성공 이벤트가 발생해야 함 (0x1301)
            - Master에서 복합인증 수행시, 인증결과 출력 혹은 취소 버튼, 타임아웃 후 새로운 Credential 입력 가능
        """
        # skiptest 체크
        if not self.capability.fingerprintInputSupported:
            self.skipTest("fingerprint input not supported")

        # 데이터 생성 전략 : 기존 json 파일 활용 우선
        user = None
        for entry in os.listdir("./data"):
            if entry.startswith("user") and entry.endswith(".json"):
                with open("./data/" + entry, encoding='UTF-8') as f:
                    user = json.load(f, cls=util.UserBuilder)
                    break

        # 지문 + PIN 유저 생성 (기존 데이터 활용)
        if not user:
            userId = util.randomAlphanumericUserID()
            user = user_pb2.UserInfo()
            user.hdr.ID = userId
            user.PIN = util.generateRandomPIN()
            # 지문 템플릿은 빈 값으로 설정 (실제로는 실제 지문 데이터를 가져와야 함)
            fingerprint = finger_pb2.FingerprintTemplate()
            fingerprint.index = 0
            fingerprint.templates.append(b"fake_fingerprint_data")
            user.fingers.append(fingerprint)

        # 사용자 등록
        self.svcManager.enrollUsers(self.targetID, [user])
        
        # 인증 모드 설정: 지문Only
        authConf = self.svcManager.getAuthConfig(self.targetID)
        authConf.authSchedules.clear()
        authSchedule = auth_pb2.AuthSchedule()
        authSchedule.mode = auth_pb2.AUTH_MODE_FINGERPRINT_ONLY
        authSchedule.scheduleID = 1
        authConf.authSchedules.append(authSchedule)
        
        # 인증 모드 적용
        self.svcManager.setAuthConfig(self.targetID, authConf)

        # 이벤트 모니터링 설정 (인증 성공 이벤트 코드: 0x1301)
        with util.EventMonitor(self.svcManager, self.targetID, eventCode=0x1301) as m:
            # 지문 인증 시도
            self.svcManager.detectFingerprint(self.targetID, user.fingers[0])
            
            # 인증 성공 이벤트 확인
            self.assertTrue(m.caught(), "지문 인증 성공 이벤트가 발생하지 않았습니다.")

    def testCommonr_30_1_2_fingerprint_pin_mode(self):
        """
        테스트 시나리오: 지문+PIN 모드에서 지문 및 PIN 인증 시도
        Test Step:
            1. User> Add User (지문 + PIN 포함)
            2. Device> 지문인증모드 설정 (AUTH_MODE_FINGERPRINT_PIN)
            3. 해당 사용자로 지문 및 PIN 인증 시도
        Expected Result:
            - 인증 성공 이벤트가 발생해야 함 (0x1301)
            - Master에서 복합인증 수행시, 인증결과 출력 혹은 취소 버튼, 타임아웃 후 새로운 Credential 입력 가능
        """
        # skiptest 체크
        if not self.capability.fingerprintInputSupported:
            self.skipTest("fingerprint input not supported")

        # 데이터 생성 전략 : 기존 json 파일 활용 우선
        user = None
        for entry in os.listdir("./data"):
            if entry.startswith("user") and entry.endswith(".json"):
                with open("./data/" + entry, encoding='UTF-8') as f:
                    user = json.load(f, cls=util.UserBuilder)
                    break

        # 지문 + PIN 유저 생성 (기존 데이터 활용)
        if not user:
            userId = util.randomAlphanumericUserID()
            user = user_pb2.UserInfo()
            user.hdr.ID = userId
            user.PIN = util.generateRandomPIN()
            # 지문 템플릿은 빈 값으로 설정 (실제로는 실제 지문 데이터를 가져와야 함)
            fingerprint = finger_pb2.FingerprintTemplate()
            fingerprint.index = 0
            fingerprint.templates.append(b"fake_fingerprint_data")
            user.fingers.append(fingerprint)

        # 사용자 등록
        self.svcManager.enrollUsers(self.targetID, [user])
        
        # 인증 모드 설정: 지문+PIN
        authConf = self.svcManager.getAuthConfig(self.targetID)
        authConf.authSchedules.clear()
        authSchedule = auth_pb2.AuthSchedule()
        authSchedule.mode = auth_pb2.AUTH_MODE_FINGERPRINT_PIN
        authSchedule.scheduleID = 1
        authConf.authSchedules.append(authSchedule)
        
        # 인증 모드 적용
        self.svcManager.setAuthConfig(self.targetID, authConf)

        # 이벤트 모니터링 설정 (인증 성공 이벤트 코드: 0x1301)
        with util.EventMonitor(self.svcManager, self.targetID, eventCode=0x1301) as m:
            # 지문 인증 시도
            self.svcManager.detectFingerprint(self.targetID, user.fingers[0])
            
            # 인증 성공 이벤트 확인
            self.assertTrue(m.caught(), "지문+PIN 인증 성공 이벤트가 발생하지 않았습니다.")

    def testCommonr_30_1_3_slave_device_fingerprint_only_mode(self):
        """
        테스트 시나리오: Slave 장치에서 지문Only 모드로 인증 시도
        Test Step:
            1. User> Add User (지문 + PIN 포함)
            2. Device> 지문인증모드 설정 (AUTH_MODE_FINGERPRINT_ONLY) - Slave 장치
            3. 해당 사용자로 Slave 장치에서 지문 인증 시도
        Expected Result:
            - 인증 성공 이벤트가 발생해야 함 (0x1301)
            - Slave에서 복합인증 수행시, 인증 결과 출력 혹은 타임아웃 발생 후 새로운 Credential 입력 가능
        """
        # skiptest 체크
        if not self.capability.fingerprintInputSupported:
            self.skipTest("fingerprint input not supported")
        if not self.slaveIDs:
            self.skipTest("slave device not available")

        # 데이터 생성 전략 : 기존 json 파일 활용 우선
        user = None
        for entry in os.listdir("./data"):
            if entry.startswith("user") and entry.endswith(".json"):
                with open("./data/" + entry, encoding='UTF-8') as f:
                    user = json.load(f, cls=util.UserBuilder)
                    break

        # 지문 + PIN 유저 생성 (기존 데이터 활용)
        if not user:
            userId = util.randomAlphanumericUserID()
            user = user_pb2.UserInfo()
            user.hdr.ID = userId
            user.PIN = util.generateRandomPIN()
            # 지문 템플릿은 빈 값으로 설정 (실제로는 실제 지문 데이터를 가져와야 함)
            fingerprint = finger_pb2.FingerprintTemplate()
            fingerprint.index = 0
            fingerprint.templates.append(b"fake_fingerprint_data")
            user.fingers.append(fingerprint)

        # 사용자 등록
        self.svcManager.enrollUsers(self.targetID, [user])
        
        # 인증 모드 설정: 지문Only (Slave 장치)
        authConf = self.svcManager.getAuthConfig(self.slaveIDs[0])
        authConf.authSchedules.clear()
        authSchedule = auth_pb2.AuthSchedule()
        authSchedule.mode = auth_pb2.AUTH_MODE_FINGERPRINT_ONLY
        authSchedule.scheduleID = 1
        authConf.authSchedules.append(authSchedule)
        
        # 인증 모드 적용
        self.svcManager.setAuthConfig(self.slaveIDs[0], authConf)

        # 이벤트 모니터링 설정 (인증 성공 이벤트 코드: 0x1301)
        with util.EventMonitor(self.svcManager, self.slaveIDs[0], eventCode=0x1301) as m:
            # 지문 인증 시도
            self.svcManager.detectFingerprint(self.slaveIDs[0], user.fingers[0])
            
            # 인증 성공 이벤트 확인
            self.assertTrue(m.caught(), "Slave 장치에서 지문 인증 성공 이벤트가 발생하지 않았습니다.")

    def testCommonr_30_1_4_slave_device_fingerprint_pin_mode(self):
        """
        테스트 시나리오: Slave 장치에서 지문+PIN 모드로 인증 시도
        Test Step:
            1. User> Add User (지문 + PIN 포함)
            2. Device> 지문인증모드 설정 (AUTH_MODE_FINGERPRINT_PIN) - Slave 장치
            3. 해당 사용자로 Slave 장치에서 지문 및 PIN 인증 시도
        Expected Result:
            - 인증 성공 이벤트가 발생해야 함 (0x1301)
            - Slave에서 복합인증 수행시, 인증 결과 출력 혹은 타임아웃 발생 후 새로운 Credential 입력 가능
        """
        # skiptest 체크
        if not self.capability.fingerprintInputSupported:
            self.skipTest("fingerprint input not supported")
        if not self.slaveIDs:
            self.skipTest("slave device not available")

        # 데이터 생성 전략 : 기존 json 파일 활용 우선
        user = None
        for entry in os.listdir("./data"):
            if entry.startswith("user") and entry.endswith(".json"):
                with open("./data/" + entry, encoding='UTF-8') as f:
                    user = json.load(f, cls=util.UserBuilder)
                    break

        # 지문 + PIN 유저 생성 (기존 데이터 활용)
        if not user:
            userId = util.randomAlphanumericUserID()
            user = user_pb2.UserInfo()
            user.hdr.ID = userId
            user.PIN = util.generateRandomPIN()
            # 지문 템플릿은 빈 값으로 설정 (실제로는 실제 지문 데이터를 가져와야 함)
            fingerprint = finger_pb2.FingerprintTemplate()
            fingerprint.index = 0
            fingerprint.templates.append(b"fake_fingerprint_data")
            user.fingers.append(fingerprint)

        # 사용자 등록
        self.svcManager.enrollUsers(self.targetID, [user])
        
        # 인증 모드 설정: 지문+PIN (Slave 장치)
        authConf = self.svcManager.getAuthConfig(self.slaveIDs[0])
        authConf.authSchedules.clear()
        authSchedule = auth_pb2.AuthSchedule()
        authSchedule.mode = auth_pb2.AUTH_MODE_FINGERPRINT_PIN
        authSchedule.scheduleID = 1
        authConf.authSchedules.append(authSchedule)
        
        # 인증 모드 적용
        self.svcManager.setAuthConfig(self.slaveIDs[0], authConf)

        # 이벤트 모니터링 설정 (인증 성공 이벤트 코드: 0x1301)
        with util.EventMonitor(self.svcManager, self.slaveIDs[0], eventCode=0x1301) as m:
            # 지문 인증 시도
            self.svcManager.detectFingerprint(self.slaveIDs[0], user.fingers[0])
            
            # 인증 성공 이벤트 확인
            self.assertTrue(m.caught(), "Slave 장치에서 지문+PIN 인증 성공 이벤트가 발생하지 않았습니다.")