async def analyze_test_case_coverage(self, test_case_info: List[Dict], existing_knowledge: str = "") -> str:
        """
        테스트케이스를 분석하여 어떤 내용들이 필요한지 파악하고,
        현재 학습 내용으로 커버 가능한지 평가

        Args:
            test_case_info: 테스트케이스 정보
            existing_knowledge: 기존 학습된 지식 (실제 존재하는 파일/API 정보)
        """
        if not test_case_info:
            return "테스트케이스 정보가 없습니다."

        test_case_content = test_case_info[0]['content']
        test_case_metadata = test_case_info[0]['metadata']

        # CLAUDE.md 파일 읽기
        try:
            claude_md_path = "/home/bes/BES_QE_RAG/CLAUDE.md"
            with open(claude_md_path, 'r', encoding='utf-8') as f:
                claude_md_content = f.read()
            print("   📖 [분석] CLAUDE.md 로딩 완료")
        except Exception as e:
            print(f"   ⚠️ [분석] CLAUDE.md 읽기 실패: {e}")
            claude_md_content = "CLAUDE.md 파일을 읽을 수 없습니다."

        # 기존 지식이 없으면 기본 메시지
        if not existing_knowledge:
            existing_knowledge = "기존 학습 내용 없음 (초기 분석)"

        analysis_prompt = f"""당신은 GSDK 테스트 자동화 전문가입니다.

아래 테스트케이스를 분석하여, 자동화 구현에 필요한 지식과 커버리지를 평가하세요.

=== 프로젝트 구조 이해 (CLAUDE.md) ===
{claude_md_content}

---

## 📋 분석 가이드 (자동화 스크립트 분석 가이드 + CLAUDE.md 통합)

1. **프로젝트 구조 파악**
   - `demo/test/` 폴더: 실제 성공한 테스트 코드 (참조 대상)
   - `example/` 폴더: 기능별 API 사용 예시 (참조용)
   - 같은 TC 번호의 다른 파일 존재 여부 확인

2. **기반 클래스 및 API 확인** (CLAUDE.md 워크플로우)
   - `demo/test/testCOMMONR.py`: TC 구현에 필요한 상속 메서드들
   - `demo/test/util.py`: TC 구현에 필요한 헬퍼 함수들
   - `demo/manager.py`: TC 구현에 필요한 ServiceManager API

3. **proto/service 구조 확인** (CLAUDE.md 워크플로우 2-4단계)
   - `biostar/proto/`: 필요한 proto 메시지 정의
   - `biostar/service/`: pb2.py 파일의 실제 구현
   - `example/`: 해당 기능의 API 사용 패턴

4. **TC 문서 원본 확인**
   - 정확한 Test Step, Data, Expected Result 파악
   - 각 Step별 세부 절차 이해

5. **CLAUDE.md 규칙 준수**
   - setUp/tearDown 재정의 금지
   - util.py 함수는 util.함수명() 형태로 사용
   - pb2 import 후 반드시 사용

6. **완전 구현 예시 참조 (demo/test/안의 COMMONR 테스트 파이썬 파일들)**
   - 유사 TC 파일의 패턴 참조

---

=== 기존 프로젝트 지식 (실제 존재하는 파일/API 정보) ===
{existing_knowledge}...

**중요**: 위 프로젝트 지식에 **실제로 존재하는 파일과 API만** 언급하세요. 추측하거나 없는 것을 만들어내지 마세요.

=== 테스트케이스 내용 ===
{test_case_content}

=== 메타데이터 ===
{test_case_metadata}

---

## 📊 분석 항목 (CLAUDE.md 워크플로우 통합)

### 1. 테스트 목적 이해 (CLAUDE.md 1단계: 요구사항 분석)
   - 이 테스트는 무엇을 검증하는가?
   - 핵심 시나리오는 무엇인가?
   - Expected Result의 각 항목을 구체적으로 나열

### 2. 필요한 proto/service (CLAUDE.md 2-3단계)
   - **proto 메시지**: `biostar/proto/`에서 필요한 .proto 파일
   - **service 구현**: `biostar/service/`에서 필요한 pb2.py 파일
   - **API 메서드**: `demo/manager.py`의 ServiceManager 메서드

### 3. example/ 참조 패턴 (CLAUDE.md 4단계) (사용 예시들)
   - 관련 기능의 파일 확인
   - API 사용법 확인

### 4. testCOMMONR.py 상속 (CLAUDE.md 5단계)
   - 상속받을 메서드
   - Capability 체크 사항
   - 필요한 헬퍼 메서드

### 5. util.py 활용 (CLAUDE.md 6단계)
   - 필요한 Helper 함수
   - EventMonitor 사용 여부
   - 필요한 Builder

### 6. 실행 가능성 검증

### 7. 테스트 데이터 요구사항
   - 어떤 유형의 테스트 데이터가 필요한가? (User, Card, Schedule 등)
   - JSON 파일에서 로드해야 하는 데이터는? (`demo/data/` 참조)
   - 새로 생성해야 하는 데이터는?

### 8. demo/test/ 참조 예시 검색 (unittest에서 성공한 case)
   - 유사한 TC 번호 또는 기능의 파일이 있는가?
   - 참조해야 할 구현 패턴은?

---

## 📋 출력 형식

### 1. 테스트 목적 및 시나리오
(간단 명료하게)

### 2. CLAUDE.md 워크플로우 체크 (6단계)
| 단계 | 필요 여부 | 구체적 항목 |
|------|-----------|-------------|
| 1. 요구사항 분석 | ✅ | (구체적으로) |
| 2. 프로토콜 확인 | ✅ | (필요한 proto 파일명) |
| 3. 서비스 구현 확인 | ✅ | (필요한 API 메서드) |
| 4. 예제 패턴 적용 | ✅ | (참조할 example 파일) |
| 5. 클래스 상속 | ✅ | (testCOMMONR 메서드) |
| 6. 유틸리티 활용 | ✅ | (util 함수 목록) |

### 3. 필요한 지식 상세 목록
- **proto 파일**: (필요한 proto 파일 목록)
- **service 파일**: (필요한 pb2 파일 목록)
- **API 메서드**: (testCOMMONR, manager, util에서 필요한 메서드)
- **데이터 요구사항**: (필요한 데이터 타입)

### 4. 실행 가능성 체크
- Capability 체크 필요: [예/아니오]
- EventMonitor 사용 필요: [예/아니오]
- Master/Slave 테스트: [예/아니오]

### 5. 참조 가능 예시
- **demo/test/**: (유사한 TC 파일명)
- **example/**: (관련 기능 파일명)

### 6. 검증 항목 (Test Step, Data, Expected Result 기반)
(각 Test Step, Data, Expected Result의 테스트 커버리지를 100% 충족하기 위해 자동화 코드로 구현할 구체적 방법)

---

⚠️ **중요**:
- 위 기존 프로젝트 지식에서 TC와 실제로 관련 있는 파일과 API만 식별하세요
- TC 내용을 먼저 분석한 후, 필요한 것만 나열하세요
- 관련 없는 파일이나 API는 언급하지 마세요

---

이 분석 결과는 코드 생성 시 참조되며, 학습 내용의 충족도를 평가하는 기준이 됩니다."""

        print("\n🔍 [테스트케이스 분석] 시작...")

        analysis_result = await self.llm.ainvoke(analysis_prompt)

        print(f"✅ [테스트케이스 분석] 완료 ({len(analysis_result):,}자)")
        await cl.Message(content=f"✅ **테스트케이스 분석 완료**\n\n```markdown\n{analysis_result[:600]}...\n```").send()

        return analysis_result