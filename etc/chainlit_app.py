"""
G-SDK Python 자동화 코드 생성 시스템 - Chainlit UI

LangGraph + LM Studio + gsdk_rag_context 통합
"""

import chainlit as cl
import sys
import os
import json
from pathlib import Path

# BES_test3 모듈 import를 위한 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from BES_test3 import RAG_Graph


# ============================================================================
# 전역 설정
# ============================================================================

RAG_CONFIG = {
    "testcase_db_path": "/Users/admin/Documents/2025_project/QE_RAG_COMPANY/QE_RAG_2025/chroma_db",
    "testcase_collection_name": "jira_test_cases",
    "testcase_embedding_model": "intfloat/multilingual-e5-large",
    "lm_studio_url": "http://127.0.0.1:1234/v1",
    "lm_studio_model": "qwen/qwen3-8b"
}


# ============================================================================
# Chainlit 이벤트 핸들러
# ============================================================================

@cl.on_chat_start
async def start():
    """
    앱 시작 시 RAG 시스템 초기화
    """
    # 환영 메시지
    await cl.Message(
        content="🚀 **G-SDK Python 자동화 코드 생성 시스템**\n\n시스템 초기화 중..."
    ).send()

    try:
        # RAG_Graph 인스턴스 생성
        await cl.Message(content="📦 RAG Pipeline 초기화 중...").send()
        graph = RAG_Graph(**RAG_CONFIG)

        # 세션에 저장
        cl.user_session.set("graph", graph)

        # 성공 메시지
        await cl.Message(
            content="""
✅ **시스템 준비 완료!**

---

## 📖 사용 방법

### 1️⃣ 테스트케이스 쿼리 입력
다음과 같은 형식으로 입력하세요:
- `COMMONR-30의 스텝 4번`
- `COMMONR-21의 모든 스텝`
- `COMMONR-30 step 4`

### 2️⃣ 코드 생성 과정 확인
시스템이 자동으로:
- ✓ 테스트케이스 검색
- ✓ 관련 리소스 탐색 (gsdk_rag_context 활용)
- ✓ 코드 계획 생성
- ✓ 최종 코드 생성

### 3️⃣ 결과 확인 및 다운로드
- 생성된 Python 코드를 확인
- 파일 저장 위치 안내

---

## 🎯 지원 기능

- ✅ **LM Studio**: 로컬 LLM (qwen3-coder-30b)
- ✅ **gsdk_rag_context**: 자율적 리소스 탐색
- ✅ **LangGraph**: 상태 관리 워크플로우
- ✅ **실시간 진행 표시**: 각 단계별 상태 업데이트

---

💡 **Tip**: 구체적인 쿼리일수록 더 정확한 코드가 생성됩니다!
"""
        ).send()

    except Exception as e:
        await cl.Message(
            content=f"❌ **시스템 초기화 실패**\n\n에러: {str(e)}\n\n**해결 방법**:\n1. LM Studio가 실행 중인지 확인 (http://127.0.0.1:1234)\n2. VectorDB 경로가 올바른지 확인\n3. 필요한 패키지가 설치되었는지 확인"
        ).send()


@cl.on_message
async def main(message: cl.Message):
    """
    사용자 쿼리 처리 및 코드 생성
    """
    query = message.content.strip()
    graph = cl.user_session.get("graph")

    if not graph:
        await cl.Message(
            content="❌ RAG 시스템이 초기화되지 않았습니다. 페이지를 새로고침해주세요."
        ).send()
        return

    try:
        # 쿼리 검증 메시지
        await cl.Message(
            content=f"📝 **쿼리 수신**: `{query}`\n\n코드 생성을 시작합니다..."
        ).send()

        # Step 1: 테스트케이스 검색
        step_msg = await cl.Message(
            content="🔍 **[1/4]** 테스트케이스 검색 중..."
        ).send()

        # RAG 파이프라인 실행
        # 비동기로 실행하되, 진행 상황을 추적
        final_state = await run_graph_with_progress(graph, query)

        # Step 4: 완료 메시지
        await step_msg.update()
        await cl.Message(
            content="✅ **[4/4]** 코드 생성 완료!"
        ).send()

        # 최종 결과 표시 (새로운 Phase 구조)
        if final_state and final_state.get('generated_code'):
            generated_code = final_state.get('generated_code', '')
            generated_plan = final_state.get('generated_plan', '')
            resource_plan = final_state.get('resource_plan', {})
            resource_context = final_state.get('resource_context', '')
            file_path = final_state.get('file_path', 'N/A')

            # 새로운 필드
            coverage = final_state.get('coverage', 0)
            validation_result = final_state.get('validation_result', {})
            needs_refinement = final_state.get('needs_refinement', False)

            # 리소스 계획 표시
            if resource_plan:
                categories = resource_plan.get('categories', [])
                manager_methods = resource_plan.get('manager_methods', [])
                event_codes = resource_plan.get('event_codes', [])

                await cl.Message(
                    content=f"""
## 🧭 리소스 계획

**카테고리**: {', '.join(categories) if categories else '없음'}
**Manager 메서드**: {len(manager_methods)}개
**이벤트 코드**: {len(event_codes)}개

```json
{json.dumps(resource_plan, ensure_ascii=False, indent=2)}
```
"""
                ).send()

            # 커버리지 및 검증 결과 표시
            coverage_emoji = "✅" if coverage >= 90 else "⚠️" if coverage >= 70 else "❌"
            refinement_status = "재생성됨 (Phase 5)" if needs_refinement else "통과"

            await cl.Message(
                content=f"""
## 📊 코드 생성 결과

{coverage_emoji} **커버리지**: {coverage}%
🔍 **검증 상태**: {refinement_status}

**누락된 스텝**: {len(validation_result.get('missing_steps', []))}개
**존재하지 않는 함수**: {len(validation_result.get('invalid_functions', []))}개
"""
            ).send()

            # 최종 코드 표시
            await cl.Message(
                content=f"""
## 🎉 생성된 코드

**파일 경로**: `{file_path}`

```python
{generated_code[:3000]}{'...\n(코드가 너무 길어 생략됨)' if len(generated_code) > 3000 else ''}
```

✅ 코드가 성공적으로 생성되었습니다!

**다음 단계**:
1. 생성된 코드를 검토하세요
2. 필요한 경우 수정하세요
3. 테스트 실행: `python {file_path}`
"""
            ).send()

        else:
            await cl.Message(
                content="⚠️ 코드 생성이 완료되었지만 결과를 가져오는 데 문제가 발생했습니다."
            ).send()

    except Exception as e:
        await cl.Message(
            content=f"""
❌ **에러 발생**

```
{str(e)}
```

**가능한 원인**:
1. LM Studio 연결 문제
2. VectorDB 검색 실패
3. 프롬프트 처리 오류

**해결 방법**:
- LM Studio가 실행 중인지 확인
- 쿼리 형식을 확인 (예: "COMMONR-30의 스텝 1번")
- 로그를 확인하여 상세 에러 메시지 파악
"""
        ).send()


async def run_graph_with_progress(graph, query):
    """
    RAG 그래프를 실행하면서 진행 상황을 표시 (새로운 Phase 구조)

    Args:
        graph: RAG_Graph 인스턴스
        query: 사용자 쿼리

    Returns:
        final_state: 최종 상태 딕셔너리
    """
    # Phase 안내는 BES_test3.py의 각 Node에서 직접 표시
    # 여기서는 전체 진행 상황만 간략히 안내

    await cl.Message(content="""
🚀 **코드 생성 워크플로우 시작**

**Phase 0**: 테스트케이스 검색
**Phase 1**: 리소스 계획 수립 (카테고리 분석)
**Phase 2**: 기본 구조 생성 (manager.py, testCOMMONR.py, util.py 분석)
**Phase 3**: 카테고리별 상세 코드 생성 (example, pb2, proto 분석)
**Phase 4**: 코드 통합 및 검증 (커버리지 분석)
**Phase 5**: 코드 재생성 (필요시)

⚙️ LangGraph 실행 중...
""").send()

    # LangGraph 실행 (각 Node에서 진행 상황을 Chainlit으로 표시)
    final_state = await graph.run_graph(query)

    return final_state


# ============================================================================
# 앱 설정
# ============================================================================

@cl.set_starters
async def set_starters():
    """
    시작 쿼리 예시 제공
    """
    return [
        cl.Starter(
            label="COMMONR-30 스텝 1",
            message="COMMONR-30의 스텝 1번 자동화 코드 생성",
            icon="/public/idea.svg",
        ),
        cl.Starter(
            label="COMMONR-21 모든 스텝",
            message="COMMONR-21의 모든 스텝 자동화 코드 생성",
            icon="/public/learn.svg",
        ),
        cl.Starter(
            label="도움말",
            message="사용 방법을 알려주세요",
            icon="/public/help.svg",
        ),
    ]


if __name__ == "__main__":
    # Chainlit 앱 실행
    # 커맨드: chainlit run chainlit_app.py -w
    pass
