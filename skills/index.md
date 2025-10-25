# 스킬 카탈로그 (Claude 스타일)

이 디렉터리는 기능(역할) 단위로 분리된 스킬 폴더 모음입니다. 각 폴더는:
- `SKILL.md`: 스킬 설명(메타데이터/입출력/선행조건/사용 API/단계/예시)
- `scripts/`: 필요 시 실행 가능한 스크립트(테스트 실행 보조, 점검 등)

아래 스킬들은 `demo/demo/manager.py`, `demo/demo/test/util.py`, `demo/example/*`, `demo/demo/event_code.json`을 1급 리소스로 사용합니다.

## 스킬 목록

- prep_capabilities — 대상 장치 Capability 점검/Skip 기준 정의
- generate_user_data — 테스트 사용자 생성(JSON/Builder/랜덤)
- apply_auth_mode — 인증 모드 적용(지문 Only/지문+PIN/extended)
- trigger_inputs — 입력 트리거(지문/핀/카드/얼굴)
- monitor_event — EventMonitor 시작/중지/파라미터 규칙
- verify_event_code — 이벤트 코드/설명/상태 검증 규칙
- backup_restore — 사용자/설정 백업 및 복구 절차

각 스킬은 Claude가 필요 시 자동으로 조합해 사용할 수 있도록 기능 중심으로 작성되어 있습니다.

