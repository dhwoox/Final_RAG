LM Studio 스킬 시스템
=====================

Suprema 데모 자동화 자산을 **Claude Code** 스타일로 재구성한 도구 모음입니다.  
Python 클래스로 작성된 스킬과 Markdown 매니페스트 기반 스킬을 모두 지원하여,  
LM Studio 또는 로컬 LLM이 테스트 워크플로우·데이터 생성·명령 실행을 일관되게 다룰 수 있습니다.

## 파이썬 스킬 빠른 시작

```bash
# 포함된 파이썬 스킬 목록
python -m lm_studio_skills list

# 특정 스킬 상세 정보 확인
python -m lm_studio_skills describe fingerprint_auth_success

# 지문 Only 시나리오 실행 (타임아웃 8초)
python -m lm_studio_skills run fingerprint_auth_success --param timeout=8
```

기본적으로 `demo/demo/config.json`과 `demo/demo/test/environ.json`을 사용합니다.  
다른 경로를 사용하려면 다음처럼 옵션을 지정하세요.

```bash
python -m lm_studio_skills --config ./demo/demo/config.json \
  --environ ./demo/demo/test/environ.json \
  run list_devices --param only_connected=false
```

## Markdown 매니페스트 스킬

`skills.md`와 같은 Markdown 파일에 테스트 절차를 선언하고 실행할 수 있습니다.

```bash
# 매니페스트 요약
python -m lm_studio_skills list-md lm_studio_skills/skills.md

# 매니페스트 상세 출력
python -m lm_studio_skills describe-md lm_studio_skills/skills.md

# 매니페스트 실행
python -m lm_studio_skills run-md lm_studio_skills/skills.md
```

매니페스트는 다음 순서를 권장합니다.

1. `메타데이터` – 이름·설명 등 스킬 정보를 기술
2. `사전준비` – Capability 확인, 백업 등 명령어 나열 (`set_target`, `require_capability`, `backup_*`)
3. `테스트데이터` – `build_random_user`, `load_user_json`, `ensure_*` 등 데이터 준비
4. `워크플로우` – Markdown 표로 Step/설명/API/데이터/이벤트를 배치
5. `검증` – `assert_true`, `assert_equal` 등 표현식 기반 검증
6. `복구` – `restore_auth_config`, `restore_users` 등 롤백
7. `명령어` – `run`, `log` 등을 사용해 CLI 명령 실행 또는 메시지 기록

`lm_studio_skills/skills.md` 파일은 COMMONR-30 지문 인증 시나리오를 예시로 제공합니다.

## 명령어 실행기

`run` 명령은 화이트리스트가 아닌 일반 명령 호출을 지원하므로,  
테스트 레포지토리 루트(`--base-path`) 기준으로 실행됩니다. 실패 시 즉시 `SkillError`가 발생합니다.

예시:

```
- run python -m unittest demo.test.testCOMMONR_30_1
```

## 확장 가이드

### 파이썬 스킬

1. `lm_studio_skills/skills/` 하위에 새 모듈을 추가합니다.
2. `lm_studio_skills.base.Skill`을 상속하고 `name`, `description`, `parameters`, `run`을 구현합니다.
3. `@register_skill` 데코레이터로 레지스트리에 등록합니다.

### Markdown 스킬

1. `skills.md` 템플릿을 복사하여 Step, API, 검증 항목을 수정합니다.
2. `테스트데이터`/`검증`/`복구` 섹션에서 사용할 명령은 `manifest_runner`가 제공하는 핸들러 이름을 사용합니다.
3. 새 파일은 `python -m lm_studio_skills describe-md ...` 로 검토한 뒤 `run-md` 로 실행합니다.

필요한 명령어나 헬퍼가 부족하면 `manifest_runner.py`의 핸들러를 확장해 주세요.
