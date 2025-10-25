# Markdown 스킬: COMMONR-30 Fingerprint Only

## 메타데이터
이름: fingerprint_auth_manifest
설명: COMMONR-30 지문 Only 인증 시나리오를 Markdown 스킬로 자동화합니다.

## 사전준비
- set_target 0
- require_capability fingerprintInputSupported
- backup_auth_config
- backup_users

## 테스트데이터
- build_random_user user_info
- ensure_hashed_pin user_info
- ensure_fingerprint_template user_info

## 워크플로우
| Step | 설명 | API | 데이터 | 이벤트 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 인증 모드를 지문 Only로 전환 | set_fingerprint_only_mode() |  |  |
| 2 | 테스트 사용자 등록 | enroll_user(user_info) | user_info |  |
| 3 | 인증 성공 이벤트 모니터 시작 | start_monitor("auth_success", 0x1301, user="user_info") |  | 0x1301 |
| 4 | 지문 인증 시나리오 실행 | (detect_result := detect_fingerprint(user_info)) | user_info | 0x1301 |
| 5 | 이벤트 수신 검증 | verify_monitor("auth_success", timeout=5.0) |  | 0x1301 |

## 검증
- assert_true detect_result
- assert_equal observed_event("auth_success") 0x1301
- assert_true observed_description("auth_success")

## 복구
- restore_auth_config
- restore_users

## 명령어
- log unittest가 필요하면 `run python -m unittest ...` 형태로 명령을 선언하세요.
