# 🚀 G-SDK Python 자동화 코드 생성 시스템

LangGraph + LM Studio + Chainlit + gsdk_rag_context 통합 시스템

---

## 📋 시스템 개요

이 시스템은 다음 기술들을 통합하여 G-SDK Python 자동화 테스트 코드를 자동 생성합니다:

- **LangGraph**: 상태 관리 워크플로우 오케스트레이션
- **LM Studio**: 로컬 LLM 실행 (qwen3-coder-30b)
- **Chainlit**: 대화형 웹 UI
- **gsdk_rag_context**: 자율적 리소스 탐색 시스템
- **ChromaDB**: 벡터 데이터베이스 (테스트케이스 + 자동화 코드)

---

## 🎯 주요 기능

### 1. 자율적 리소스 탐색 (README.md 기반)
```
Phase 1: 요구사항 분석
  → 키워드 추출 → category_map.json 조회

Phase 2: 리소스 탐색
  → testCOMMONR.py → manager.py → util.py → example/

Phase 3: 코드 생성
  → 7단계 워크플로우 적용 → 최종 코드 생성
```

### 2. 실시간 진행 상황 표시
```
[1/4] 테스트케이스 검색 중...
[2/4] gsdk_rag_context 리소스 탐색 중...
[3/4] 코드 계획 생성 중... (LM Studio)
[4/4] 최종 코드 생성 중... (LM Studio)
```

### 3. 동적 컨텍스트 주입
- 테스트케이스 분석 → 관련 카테고리 자동 추출
- 필요한 Manager API만 필터링
- 관련 Event 코드만 제공

---

## 📦 설치

### 1. 필수 패키지 설치

```bash
pip install chainlit langgraph langchain-chroma langchain-huggingface
```

### 2. LM Studio 설정

1. **LM Studio 다운로드**: https://lmstudio.ai/
2. **모델 다운로드**: `qwen/qwen3-coder-30b`
3. **로컬 서버 시작**:
   - LM Studio 실행
   - 모델 로드
   - "Local Server" 탭에서 서버 시작
   - 기본 주소: `http://127.0.0.1:1234`

### 3. VectorDB 경로 설정

[chainlit_app.py](chainlit_app.py)의 `RAG_CONFIG` 수정:

```python
RAG_CONFIG = {
    "testcase_db_path": "/your/path/testcase_vectordb",  # 수정 필요
    "automation_db_path": "/your/path/automation_vectordb",  # 수정 필요
    ...
}
```

---

## ▶️ 실행 방법

### 1. LM Studio 실행

```bash
# LM Studio 앱 실행 후
# 1. qwen3-coder-30b 모델 로드
# 2. "Local Server" 탭에서 서버 시작
# 3. http://127.0.0.1:1234 연결 확인
```

### 2. Chainlit 앱 실행

```bash
cd /Users/admin/Documents/2025_project/QE_RAG_COMPANY/QE_RAG_2025/etc

chainlit run chainlit_app.py -w
```

### 3. 브라우저 접속

```
http://localhost:8000
```

---

## 🎨 사용 방법

### 쿼리 형식

다음과 같은 형식으로 입력하세요:

```
COMMONR-30의 스텝 1번
COMMONR-21의 모든 스텝
COMMONR-30 step 1
```

### 시스템 응답

```
📝 쿼리 수신: COMMONR-30의 스텝 1번

🔍 [1/4] 테스트케이스 검색 중...
  ✓ 테스트케이스 1개 검색됨

📚 [2/4] gsdk_rag_context 리소스 탐색 중...
  🔍 Phase 1: 키워드 추출
    추출된 키워드: fingerprint, auth, user, enroll, ...

  📦 Phase 2: 카테고리 매칭
    매칭된 카테고리 (4개): user, auth, finger, event

  🔧 Phase 2: Manager API 필터링
    관련 API 그룹: 3개

  📊 Phase 2: Event 코드 필터링
    관련 이벤트: 2개

📝 [3/4] 코드 계획 생성 중... (LM Studio)
  ✓ 계획 생성 완료

⚙️ [4/4] 최종 코드 생성 중... (LM Studio)
  ✓ 코드 생성 완료

✅ 코드 생성 완료!

---

## 생성된 코드

파일 경로: `generated_codes/testCOMMONR_30_1.py`

[Python 코드 블록 표시]
```

---

## 📁 파일 구조

```
QE_RAG_2025/
├── etc/
│   ├── chainlit_app.py          # Chainlit 웹 UI (신규)
│   ├── BES_test3.py              # RAG 파이프라인 (개선됨)
│   └── README_CHAINLIT.md        # 이 파일
│
├── gsdk_rag_context/             # RAG 컨텍스트 시스템
│   ├── README.md                 # 자율적 탐색 가이드
│   ├── 01_WORKFLOW_GUIDE.md      # 7단계 워크플로우
│   ├── 02_REFERENCE_GUIDE.md     # 리소스 참조 가이드
│   ├── 03_TEST_DATA_GUIDE.md     # 데이터 생성 가이드
│   └── resources/
│       ├── category_map.json     # 46개 카테고리 매핑
│       ├── manager_api_index.json # Manager API 색인
│       └── event_codes.json      # Event 코드 참조
│
└── generated_codes/              # 출력 폴더 (자동 생성)
    └── testCOMMONR_XX_Y.py
```

---

## 🔧 주요 개선 사항

### BES_test3.py 개선

#### 1. gsdk_rag_context 통합

```python
class RAG_Pipeline:
    def __init__(self, ...):
        # ✨ NEW: gsdk_rag_context 로딩
        self._load_gsdk_context()

        # 가이드 문서 로드
        self.guides = {
            'readme': ...,
            'workflow': ...,
            'reference': ...,
            'test_data': ...
        }

        # 리소스 JSON 로드
        self.resources = {
            'category_map': ...,
            'manager_api': ...,
            'event_codes': ...
        }
```

#### 2. 동적 컨텍스트 추출

```python
def _extract_relevant_context(self, test_case_content):
    """
    README.md의 Phase 1-2 자율적 탐색 프로세스 구현
    """
    # Phase 1: 키워드 추출 → 카테고리 매칭
    keywords = self._extract_keywords(test_case_content)
    relevant_categories = ...

    # Phase 2: Manager API 필터링
    relevant_apis = self._filter_apis_by_categories(categories)

    # Phase 2: Event 코드 필터링
    relevant_events = self._filter_events_by_keywords(keywords)

    return {
        'keywords': keywords,
        'categories': relevant_categories,
        'apis': relevant_apis,
        'events': relevant_events
    }
```

#### 3. 프롬프트 재구성

```python
automation_plan_prompt_template = PromptTemplate(
    template="""
# G-SDK Python 자동화 코드 계획 생성

## 🔍 자율적 탐색 프로세스 (README.md 기반)

### Phase 1: 요구사항 분석
1. 키워드 추출
2. category_map.json 조회
3. 리소스 목록 생성

### Phase 2: 리소스 탐색
우선순위: testCOMMONR.py → manager.py → util.py → example/

### Phase 3: 코드 계획 생성
1. 7-Phase Workflow 적용
2. Test Data Strategy
3. Verification Strategy

---

## 📚 gsdk_rag_context 리소스

{context_summary}  # ✨ 동적으로 주입됨

---

[상세 지침...]
"""
)
```

---

## 🐛 트러블슈팅

### 문제: LM Studio 연결 실패

**증상**:
```
❌ LM Studio 연결 실패: Connection refused
```

**해결**:
1. LM Studio가 실행 중인지 확인
2. 로컬 서버가 시작되었는지 확인 (http://127.0.0.1:1234)
3. 방화벽 설정 확인

---

### 문제: VectorDB 경로 오류

**증상**:
```
⚠️ 테스트케이스 DB 디렉터리가 없습니다
```

**해결**:
1. `chainlit_app.py`의 `RAG_CONFIG` 수정
2. 올바른 경로로 변경:
```python
RAG_CONFIG = {
    "testcase_db_path": "/actual/path/to/testcase_vectordb",
    "automation_db_path": "/actual/path/to/automation_vectordb",
    ...
}
```

---

### 문제: gsdk_rag_context 로딩 실패

**증상**:
```
⚠️ gsdk_rag_context 폴더를 찾을 수 없습니다
```

**해결**:
1. 프로젝트 루트에 `gsdk_rag_context/` 폴더 확인
2. 폴더 구조 검증:
```
QE_RAG_2025/
├── gsdk_rag_context/
│   ├── README.md
│   ├── 01_WORKFLOW_GUIDE.md
│   ├── 02_REFERENCE_GUIDE.md
│   ├── 03_TEST_DATA_GUIDE.md
│   └── resources/
│       ├── category_map.json
│       ├── manager_api_index.json
│       └── event_codes.json
```

---

### 문제: 코드 생성 시간이 너무 오래 걸림

**해결**:
1. LM Studio의 GPU 가속 확인
2. 모델 크기 확인 (30B 모델은 시간이 걸릴 수 있음)
3. `max_tokens` 설정 확인 (BES_test3.py):
```python
self.llm = LMStudioLLM(
    max_tokens=70000  # 너무 크면 시간이 오래 걸림
)
```

---

## 📊 성능 및 제한사항

### 성능
- **평균 코드 생성 시간**: 2-5분 (모델 및 하드웨어에 따라 다름)
- **테스트케이스 검색 시간**: < 1초
- **컨텍스트 추출 시간**: < 1초

### 제한사항
- **LM Studio**: 로컬 실행 필요 (클라우드 미지원)
- **VectorDB**: 사전 구축 필요
- **모델 크기**: 최소 30B 권장 (코드 품질)

---

## 🎯 예상 효과

1. **자동화 효율**: 수동 작성 대비 5-10배 빠른 코드 생성
2. **품질 향상**: gsdk_rag_context 가이드 적용으로 일관성 증가
3. **사용성**: 웹 UI로 누구나 쉽게 사용
4. **확장성**: 새 카테고리/API 추가 시 JSON만 업데이트

---

## 📝 라이선스

Copyright (c) 2023-2025 Suprema Co., Ltd. All Rights Reserved.

This automation system is for internal use in G-SDK Python test automation.

---

## 🤝 기여

버그 리포트 및 기능 제안은 이슈 트래커를 사용하세요.

---

**Happy Coding! 🚀**
