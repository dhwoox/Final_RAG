from langgraph.graph import StateGraph, END
import chromadb
from langchain.llms.base import LLM
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.prompts import PromptTemplate
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
from typing import List, Dict, Any, Optional, Tuple, TypedDict, Annotated
import json
import requests
import warnings
import datetime
import os
import re
import operator
import chainlit as cl

# FutureWarning 무시
warnings.filterwarnings("ignore", category=FutureWarning)

class LMStudioLLM(LLM):
    """LM Studio와 연동하는 LangChain 호환 LLM 클래스"""
    
    base_url: str = "http://127.0.0.1:1234/v1"
    model_name: str = "qwen/qwen3-coder-30b"
    temperature: float = 0.1
    max_tokens: int = 70000  # 자동화 코드 생성을 위해 토큰 수 증가
    
    def __init__(self, 
                 base_url: str = "http://127.0.0.1:1234/v1",
                 model_name: str = "qwen/qwen3-coder-30b",
                 temperature: float = 0.1,
                 max_tokens: int = 70000,
                 **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._test_connection()
    
    def _test_connection(self):
        """LM Studio 연결 테스트"""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            if response.status_code == 200:
                models = response.json()
                print(f"✅ LM Studio 연결 성공! 사용 가능한 모델: {len(models.get('data', []))}개")
            else:
                print(f"⚠️ LM Studio 연결 상태 확인 필요: {response.status_code}")
        except Exception as e:
            print(f"❌ LM Studio 연결 실패: {e}")
    
    @property
    def _llm_type(self) -> str:
        return "lm_studio"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        try:
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False
            }

            if stop:
                payload["stop"] = stop

            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10000000  # 1000초 (16분 40초)로 설정
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                return f"Error: LM Studio 응답 오류 (status: {response.status_code})"

        except Exception as e:
            return f"Error: LM Studio 통신 오류 - {str(e)}"

    async def ainvoke_with_history(self, messages: List[Dict[str, str]]) -> str:
        """
        대화 히스토리를 포함하여 LM Studio에 요청
        messages: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
        """
        try:
            payload = {
                "model": self.model_name,
                "messages": messages,  # ✨ 전체 대화 히스토리
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10000000
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                return f"Error: LM Studio 응답 오류 (status: {response.status_code})"

        except Exception as e:
            return f"Error: LM Studio 통신 오류 - {str(e)}"

class RAG_Pipeline :
    """
    Vector DB, Embedding Model, LM Studio를 연결하여 RAG를 수행하는 클래스.
    """

    # ✨ 클래스 변수: 프로젝트 학습 결과 캐시
    cached_project_knowledge = None
    learn_summary_info_path = "/home/bes/BES_QE_RAG/learn_summary_info.json"
    learn_all_info_path = "/home/bes/BES_QE_RAG/learn_all_info.json"

    def __init__(self,
                testcase_db_path="/home/bes/BES_QE_RAG/testcase_rag/testcase_vectordb",           # 테스트케이스 DB 폴더
                automation_db_path="/home/bes/BES_QE_RAG/automation_rag/automation_vectordb",       # 자동화 코드 DB 폴더
                testcase_collection_name="testcase_vectordb",        # 테스트케이스 컬렉션명
                automation_collection_name="test_automation_functions",     # 자동화 코드 컬렉션명
                testcase_embedding_model="intfloat/multilingual-e5-large",        # 테스트케이스용 임베딩 모델
                automation_embedding_model="BAAI/bge-m3", # 자동화 코드용 임베딩 모델
                lm_studio_url: str = "http://127.0.0.1:1234/v1",
                lm_studio_model: str = "qwen/qwen3-coder-30b"
                ):
        
        self.testcase_db_path = testcase_db_path
        self.automation_db_path = automation_db_path
        self.testcase_collection_name = testcase_collection_name
        self.automation_collection_name = automation_collection_name
        self.testcase_embedding_model = testcase_embedding_model
        self.automation_embedding_model = automation_embedding_model
        self.lm_studio_url = lm_studio_url
        self.lm_studio_model = lm_studio_model
        
        self.llm = LMStudioLLM(
            base_url=lm_studio_url,
            model_name=lm_studio_model,
            temperature=0.1,
            max_tokens=70000  # 자동화 코드 생성을 위해 토큰 수 증가
        )
    
        # 폴더 존재 확인
        self._check_db_directories()
        
        # 테스트케이스용 임베딩 모델 설정 (GPU 사용)
        print(f"🔧 테스트케이스용 임베딩 모델 로딩: {testcase_embedding_model}")
        testcase_model_kwargs = {'device': 'cuda', 'trust_remote_code': True}
        testcase_encode_kwargs = {'normalize_embeddings': True, 'batch_size': 4}
        
        self.testcase_embeddings = HuggingFaceEmbeddings(
            model_name=testcase_embedding_model,
            model_kwargs=testcase_model_kwargs,
            encode_kwargs=testcase_encode_kwargs
        )
        print(f"✅ 테스트케이스 임베딩 모델 로딩 완료")
        
        # 자동화 코드용 임베딩 모델 설정 (GPU 사용)
        print(f"🔧 자동화 코드용 임베딩 모델 로딩: {automation_embedding_model}")
        automation_model_kwargs = {'device': 'cuda', 'trust_remote_code': True}
        automation_encode_kwargs = {'normalize_embeddings': True, 'batch_size': 4}
        
        self.automation_embeddings = HuggingFaceEmbeddings(
            model_name=automation_embedding_model,
            model_kwargs=automation_model_kwargs,
            encode_kwargs=automation_encode_kwargs
        )
        print(f"✅ 자동화 코드 임베딩 모델 로딩 완료")
        
        # 2개의 벡터 저장소 연결 (각각 다른 폴더와 다른 임베딩 모델)
        self.testcase_vectorstore = self._connect_to_chroma(
            self.testcase_db_path, 
            self.testcase_collection_name, 
            self.testcase_embeddings,
            "테스트케이스",
            testcase_embedding_model
        )
        self.automation_vectorstore = self._connect_to_chroma(
            self.automation_db_path, 
            self.automation_collection_name, 
            self.automation_embeddings,
            "자동화 코드",
            automation_embedding_model
        )
        
    
    def _check_db_directories(self):
        """DB 디렉터리 존재 확인"""
        print("📁 ChromaDB 디렉터리 확인 중...")
        
        if not os.path.exists(self.testcase_db_path):
            print(f"⚠️ 테스트케이스 DB 디렉터리가 없습니다: {self.testcase_db_path}")
            print(f"   디렉터리를 생성하거나 올바른 경로를 지정해주세요.")
        else:
            print(f"✅ 테스트케이스 DB 디렉터리 확인: {self.testcase_db_path}")
        
        if not os.path.exists(self.automation_db_path):
            print(f"⚠️ 자동화 코드 DB 디렉터리가 없습니다: {self.automation_db_path}")
            print(f"   디렉터리를 생성하거나 올바른 경로를 지정해주세요.")
        else:
            print(f"✅ 자동화 코드 DB 디렉터리 확인: {self.automation_db_path}")
    
    def _connect_to_chroma(self, persist_directory: str, collection_name: str, 
                          embedding_function, db_type: str, embedding_model_name: str) -> Chroma:
        """개별 ChromaDB 폴더의 컬렉션에 특정 임베딩 모델로 연결"""
        try:
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=embedding_function,
                persist_directory=persist_directory  # 각각 다른 경로 사용
            )
            print(f"✅ ChromaDB '{persist_directory}/{collection_name}' ({db_type}) 연결 완료")
            print(f"   🧠 임베딩 모델: {embedding_model_name}")
            
            # 컬렉션 정보 확인
            try:
                collection = vectorstore.get()
                doc_count = len(collection.get('ids', []))
                print(f"   📊 {db_type} 문서 수: {doc_count}개")
            except Exception as e:
                print(f"   ℹ️ 컬렉션 정보 확인 불가: {e}")
            
            return vectorstore
        except Exception as e:
            print(f"❌ ChromaDB '{persist_directory}' 연결 실패: {e}")
            raise
    

#RAG_Pipeline(RAG 기본값)을 상속받아 테스트와 관련된 함수를 생성
class RAG_Function(RAG_Pipeline) :
    async def retrieve_test_case(self, query: str) -> List[Dict]:
        try:
            # 쿼리에서 issue_key, step_index, number 추출
            # 예시:
            # "COMMONR-30의 테스트 스텝 2번" -> issue_key="COMMONR-30", step_index="2", number=None
            # "COMMONR-30의 테스트 스텝 1_2번" -> issue_key="COMMONR-30", step_index="1", number="2"
            # "COMMONR-30의 테스트 스텝 1번의 2번" -> issue_key="COMMONR-30", step_index="1", number="2"

            issue_key_match = re.search(r'(COMMONR-\d+)', query)

            # step_index_number 형식 (예: "스텝 1_2")
            step_number_match = re.search(r'스텝\s*(\d+)_(\d+)', query)
            # step_index만 (예: "스텝 1")
            step_index_match = re.search(r'스텝\s*(\d+)', query)
            # "스텝 1번의 2번" 형식
            step_of_number_match = re.search(r'스텝\s*(\d+).*?(\d+)번', query)

            if not issue_key_match:
                print(f"⚠️ 쿼리에서 issue_key를 찾을 수 없습니다: {query}")
                return []

            issue_key = issue_key_match.group(1)
            step_index = None
            number = None

            # number 추출 우선순위
            if step_number_match:
                # "스텝 1_2" 형식
                step_index = step_number_match.group(1)
                number = step_number_match.group(2)
                print(f"   🔍 검색 조건: issue_key={issue_key}, step_index={step_index}, number={number}")
            elif step_of_number_match:
                # "스텝 1번의 2번" 형식
                step_index = step_of_number_match.group(1)
                number = step_of_number_match.group(2)
                print(f"   🔍 검색 조건: issue_key={issue_key}, step_index={step_index}, number={number}")
            elif step_index_match:
                # "스텝 1" 형식 (number 없음)
                step_index = step_index_match.group(1)
                print(f"   🔍 검색 조건: issue_key={issue_key}, step_index={step_index} (전체)")
            else:
                print(f"   🔍 검색 조건: issue_key={issue_key} (모든 스텝)")

            # 메타데이터 필터 구성 (step_index까지만 필터링, number는 나중에 LLM에게 전달)
            if step_index:
                where_filter = {
                    "$and": [
                        {"issue_key": {"$eq": issue_key}},
                        {"step_index": {"$eq": step_index}}
                    ]
                }
            else:
                where_filter = {"issue_key": {"$eq": issue_key}}

            # ChromaDB에서 직접 메타데이터 필터로 검색
            collection = self.testcase_vectorstore.get(where=where_filter)

            if not collection or not collection.get('ids'):
                print(f"   ⚠️ 검색 결과가 없습니다.")
                return []

            # 결과를 딕셔너리 형태로 변환
            testcase_results = []
            ids = collection.get('ids', [])
            documents = collection.get('documents', [])
            metadatas = collection.get('metadatas', [])

            for i in range(len(ids)):
                testcase_results.append({
                    "content": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                })

            print(f"   📚 테스트케이스 DB에서 {len(testcase_results)}개 검색됨")
            print(f"📊 최종 검색 결과: 테스트케이스 {len(testcase_results)}개")
            return testcase_results

        except Exception as e:
            print(f"❌ 벡터 DB 검색 중 오류: {e}")
            return []


    def _safe_parse_json(self, response_text: str, default: dict) -> dict:
        """안전한 JSON 파싱 헬퍼"""
        import re
        import json

        try:
            # 응답 텍스트가 str이 아닌 경우 처리
            if hasattr(response_text, 'content'):
                response_text = response_text.content

            response_str = str(response_text)

            # 디버깅: 응답 앞부분 출력
            print(f"   🔍 [JSON 파싱] 응답 길이: {len(response_str)}자")
            print(f"   🔍 [JSON 파싱] 응답 앞 200자: {response_str[:200]}")

            # JSON 블록 찾기 - greedy 방식으로 변경
            patterns = [
                r'```json\s*(\{.*\})\s*```',  # ✅ .* 는 최대 매칭 - 중첩된 { } 처리 가능
                r'```\s*(\{.*\})\s*```',
                r'(\{.*\})'
            ]

            for i, pattern in enumerate(patterns):
                match = re.search(pattern, response_str, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
                    try:
                        parsed = json.loads(json_str)
                        print(f"   ✅ [JSON 파싱] 패턴 {i+1}로 성공, extracted_info 개수: {len(parsed.get('extracted_info', []))}")
                        return parsed
                    except json.JSONDecodeError as je:
                        print(f"   ⚠️ [JSON 파싱] 패턴 {i+1} 매칭되었으나 파싱 실패: {je}")
                        continue

            # 파싱 실패 시 기본값 반환
            print(f"   ❌ [JSON 파싱] 모든 패턴 실패, 기본값 반환")
            return default

        except Exception as e:
            print(f"⚠️ JSON 파싱 오류: {e}")
            import traceback
            traceback.print_exc()
            return default



    def load_learn_summary_info(self) -> Optional[str]:
        """Step 5 최종 요약 정보 로드"""
        import json

        # 1. 메모리 캐시 확인
        if RAG_Pipeline.cached_project_knowledge is not None:
            print("✅ [Step 5 요약] 메모리에서 로드 (즉시)")
            return RAG_Pipeline.cached_project_knowledge

        # 2. 파일 캐시 확인
        if os.path.exists(RAG_Pipeline.learn_summary_info_path):
            try:
                with open(RAG_Pipeline.learn_summary_info_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    knowledge = cached_data.get('knowledge', '')
                    timestamp = cached_data.get('timestamp', '')
                    print(f"✅ [Step 5 요약] 파일에서 로드 (저장 시각: {timestamp})")
                    # 메모리에도 저장
                    RAG_Pipeline.cached_project_knowledge = knowledge
                    return knowledge
            except Exception as e:
                print(f"⚠️ [Step 5 요약] 파일 로드 실패: {e}")
                return None

        print("ℹ️ [Step 5 요약] 캐시 없음 - 새로 학습 필요")
        return None


    async def generate_code(self, test_case_info: List[Dict], test_case_analysis: str = "") -> str:
        """
        ✨ 간소화: 학습된 내용만 사용 (파일 재로딩 불필요)
        ✨ 개선: 테스트케이스 분석 내용 포함
        """
        import os
        import json

        try:
            print("--- 3. ⚡ 자동화코드 생성 (캐시된 학습 내용 기반) ---")

            # ✨ 프로젝트 전체 학습 로드 (캐시 사용)
            accumulated_knowledge = self.load_learn_summary_info()
            print(f"   ✅ 학습 내용 로드 완료 ({len(accumulated_knowledge):,}자)")

            # ❌ Proto/Core 파일 재로딩 제거 (이미 accumulated_knowledge에 포함됨)

            #테스트케이스 info를 쿼리 형태로 바꿈
            self.automation_plan_prompt_template = PromptTemplate(
                input_variables=[
              "accumulated_knowledge",  # ✨ 모든 파일 학습 결과
              "test_case_content",
              "test_case_metadata",
              "test_case_analysis"  # ✨ 테스트케이스 분석 결과
          ],
          template="""
당신은 GSDK Python 자동화 테스트 코드 전문가입니다.

---

## 📚 학습 내용 (이미 학습 완료)

{accumulated_knowledge}

위 내용은 다음을 **전체 학습**한 결과입니다:
- `biostar/proto/` - Proto 메시지 정의
- `biostar/service/` - gRPC 서비스 구현 (pb2)
- `demo/test/` - 실제 성공한 테스트 코드 **⭐ 주요 참조**
- `demo/manager.py` - ServiceManager API
- `demo/test/util.py` - 헬퍼 함수
- `example/` - API 사용 패턴

**이 학습 내용에서 찾은 것만 사용하세요. 추측하지 마세요.**

---

## 🔍 테스트케이스 분석 결과

{test_case_analysis}

위 분석의 **8개 항목 전체**를 코드에 반영하세요:
1. 테스트 목적 이해
2. 필요한 기술 요소 (Proto, gRPC, example, ServiceManager, 데이터)
3. 검증 항목 (Expected Result)
4. 테스트 데이터 요구사항
5. 테스트 베이스 클래스 요구사항
6. 유틸리티 요구사항
7. 실제 코드 패턴 참조
8. 전체 커버리지 요구사항

---

## 📋 테스트케이스 내용

{test_case_content}

**메타데이터**:
{test_case_metadata}

---

## 🎯 코드 생성 지침

### 1️⃣ 분석 결과 기반 구현
- 테스트케이스 분석 결과의 요구사항을 **학습 내용에서 매칭**
- 학습 내용에서 찾은 파일, 함수, API만 사용
- demo/test/의 성공한 코드 패턴 참조

### 2️⃣ 필수 구조 (CLAUDE.md 워크플로우)
```python
# 📦 필수 Import (항상 포함)
import unittest
import util
from testCOMMONR import *
from manager import ServiceManager

# 📦 사용하는 경우만 Import
import {{service}}_pb2  # 학습 내용에서 찾은 pb2만
# import os, json 등 (필요 시)

# 🏗️ 클래스 구조
class testCOMMONR_{{issue_number}}_{{step_index}}(TestCOMMONR):
    \"\"\"전체 테스트 시나리오 설명\"\"\"

    def testCommonr_{{issue_number}}_{{step_index}}_{{number}}_{{description}}(self):
        \"\"\"
        해당 테스트 시나리오 설명
        - TC의 Test Step X 구현
        - TC의 Expected Result Y 검증
        \"\"\"

        # 1. Capability 체크 (필요 시)
        # 분석 결과에서 요구된 capability만 체크

        # 2. 테스트 데이터 생성 (JSON 우선)
        # 학습 내용에서 찾은 Builder 패턴 사용
        {{data}} = None
        for entry in os.listdir("./data"):
            if entry.startswith("{{data}}") and entry.endswith(".json"):
                with open("./data/" + entry, encoding='UTF-8') as f:
                    {{data}} = json.load(f, cls=util.{{Data}}Builder)
                    break

        # 3. API 호출 (학습 내용의 ServiceManager 메서드 사용)
        # 분석 결과에서 찾은 API만 호출

        # 4. 검증 (Expected Result 전체 구현)
        # unittest.assertEqual, assertTrue 등 사용
```

### 3️⃣ 데이터 생성 전략
- **우선순위 1**: JSON 파일 로드 (util.py의 Builder 사용)
- **우선순위 2**: 기존 데이터 수정 (JSON 값 기반)
- **util.py 사용법**: `util.함수명()` 형태 (직접 import 금지)

### 4️⃣ 검증 구현
- **Expected Result의 모든 항목 검증**
- unittest assertion 사용
- EventMonitor 필요 시 사용 (분석 결과 참조)

### 5️⃣ 금지 사항
- ❌ setUp/tearDown 재정의 금지
- ❌ 학습 내용에 없는 함수/API 사용 금지
- ❌ Builder 직접 import 금지 (util 사용)
- ❌ pb2 import 후 미사용 금지
- ❌ 구체적 함수명 예시를 그대로 복사 금지

---

## 📝 출력 요구사항

1. **파일명**: `testCOMMONR_{{숫자}}_{{step_index}}.py`
   - 예: COMMONR-21 → testCOMMONR_21_1.py

2. **클래스명**: `testCOMMONR_{{숫자}}_{{step_index}}(TestCOMMONR)`

3. **함수명**: `testCommonr_{{숫자}}_{{step_index}}_{{N}}_{{설명}}()`
   - N: 1, 2, 3... (순차 증가)
   - 설명: 테스트 내용 요약

4. **완전한 Python 코드 생성**
   - 모든 Test Step 구현
   - 모든 Expected Result 검증
   - 데이터 생성 전략 준수

---

⚠️ **최종 체크**
- [ ] 테스트케이스 분석 결과의 8개 항목 전체 반영
- [ ] 학습 내용에서 찾은 것만 사용 (추측 금지)
- [ ] demo/test/의 성공 패턴 참조
- [ ] Expected Result 전체 검증
- [ ] util.함수명() 형태 사용
- [ ] pb2 import 시 반드시 사용

**완전한 testCOMMONR 스타일 테스트 코드 계획을 생성하세요.**
Think step by step. 시간이 오래 걸려도 괜찮습니다.
""")
            
            
            self.automation_prompt_template = PromptTemplate(
                input_variables=[
              "accumulated_knowledge",  # ✨ 모든 파일 학습 결과
              "test_case_content",
              "test_case_analysis",  # ✨ 테스트케이스 분석 결과
              "generated_plan"
          ],
          template="""
당신은 GSDK Python 자동화 테스트 코드 전문가입니다.

---

## 📚 학습 내용 (이미 학습 완료)

{accumulated_knowledge}

위 내용은 다음을 **전체 학습**한 결과입니다:
- `biostar/proto/` - Proto 메시지 정의
- `biostar/service/` - gRPC 서비스 구현 (pb2)
- `demo/test/` - 실제 성공한 테스트 코드 **⭐ 주요 참조**
- `demo/manager.py` - ServiceManager API
- `demo/test/util.py` - 헬퍼 함수
- `example/` - API 사용 패턴

**이 학습 내용에서 찾은 것만 사용하세요. 추측하지 마세요.**

---

## 🔍 테스트케이스 분석 결과

{test_case_analysis}

위 분석의 **8개 항목 전체**를 코드에 반영하세요:
1. 테스트 목적 이해
2. 필요한 기술 요소 (Proto, gRPC, example, ServiceManager)
3. **검증 항목** ⭐ **가장 중요** (Test Step 절차, Test Data 반영, Expected Result 검증)
4. 테스트 데이터 요구사항
5. 테스트 베이스 클래스 요구사항
6. 유틸리티 요구사항
7. 실제 코드 패턴 참조
8. 전체 테스트 커버리지 요구사항

**특히 항목 3이 가장 중요합니다:**
- TC의 Test Step 절차대로 코드를 작성했는가?
- TC의 Test Data 값을 반영했는가?
- TC의 Expected Result대로 검증했는가?

---

## 📋 테스트케이스 내용

{test_case_content}

---

## 📋 자동화코드 계획

{generated_plan}

위 계획을 기반으로 코드를 생성하세요.

---

## 🎯 코드 생성 지침

### 1️⃣ 분석 결과 기반 구현 (8개 항목 체크)

**항목 3: Test Step / Data / Expected Result 구현** ⭐ 최우선
- TC의 **Test Step 절차**를 순서대로 구현
- TC의 **Test Data** 값을 정확히 반영
- TC의 **Expected Result** 모든 항목을 검증

**항목 2: 필요한 기술 요소 활용**
- 학습 내용에서 찾은 Proto 메시지만 사용
- 학습 내용에서 찾은 gRPC 서비스/메서드만 호출
- ServiceManager API 활용

**항목 4: 테스트 데이터 생성**
- JSON 파일 로드 우선 (util.py의 Builder 활용)
- 필요 시 기존 데이터 수정 (JSON 값 기반)

**항목 7: demo/test/ 성공 패턴 참조**
- import 패턴
- 데이터 처리 방식
- API 호출 흐름
- 검증 방법

---

### 2️⃣ 필수 구조 (CLAUDE.md 워크플로우)

```python
# 📦 필수 Import (항상 포함)
import unittest
import util
from testCOMMONR import *
from manager import ServiceManager

# 📦 사용하는 경우만 Import
import {{service}}_pb2  # 학습 내용에서 찾은 pb2만
import os, json  # 필요 시

# 🏗️ 클래스 구조
class testCOMMONR_{{issue_number}}_{{step_index}}(TestCOMMONR):
    \"\"\"전체 테스트 시나리오 설명\"\"\"

    def testCommonr_{{issue_number}}_{{step_index}}_{{number}}_{{description}}(self):
        \"\"\"
        해당 테스트 시나리오 설명
        - TC의 Test Step X 구현
        - TC의 Test Data 반영
        - TC의 Expected Result Y 검증
        \"\"\"

        # 1. Capability 체크 (필요 시)
        # 분석 결과 항목 2에서 요구된 capability만 체크

        # 2. 테스트 데이터 생성 (항목 4 반영)
        # JSON 우선, 학습 내용에서 찾은 Builder 패턴 사용
        {{data}} = None
        for entry in os.listdir("./data"):
            if entry.startswith("{{data}}") and entry.endswith(".json"):
                with open("./data/" + entry, encoding='UTF-8') as f:
                    {{data}} = json.load(f, cls=util.{{Data}}Builder)
                    break

        # 필요 시 기존 데이터 수정 (JSON 값 기반)

        # 3. API 호출 (항목 2 반영)
        # 학습 내용의 ServiceManager 메서드 사용
        # TC의 Test Step 절차대로 호출

        # 4. 검증 (항목 3 반영)
        # TC의 Expected Result 전체 구현
        # unittest.assertEqual, assertTrue 등 사용
```

---

### 3️⃣ 데이터 생성 전략 (항목 4)

**우선순위 1: JSON 파일 로드**
```python
{{data}} = None
for entry in os.listdir("./data"):
    if entry.startswith("{{data}}") and entry.endswith(".json"):
        with open("./data/" + entry, encoding='UTF-8') as f:
            {{data}} = json.load(f, cls=util.{{Data}}Builder)
            break
```

**우선순위 2: 기존 데이터 수정**
- JSON 값을 기반으로 필요한 데이터 생성
- 예: 지문+PIN 유저 필요 → 기존 유저의 지문+PIN 값 활용

**util.py 사용법:**
- `util.함수명()` 형태로 사용
- Builder 직접 import 금지

---

### 4️⃣ Test Step / Data / Expected Result 구현 (항목 3) ⭐ 최우선

**TC의 Test Step 절차 구현:**
- TC의 각 Step을 순서대로 코드로 작성
- 학습 내용에서 찾은 API/함수만 사용

**TC의 Test Data 반영:**
- TC의 Data 항목에 명시된 데이터 값 사용
- JSON 파일 또는 Builder로 생성

**TC의 Expected Result 검증:**
- TC의 모든 Expected Result 항목 검증
- unittest assertion 사용 (assertEqual, assertTrue 등)
- EventMonitor 필요 시 사용

---

### 5️⃣ 금지 사항

- ❌ setUp/tearDown 재정의 금지
- ❌ 학습 내용에 없는 함수/API 사용 금지
- ❌ Builder 직접 import 금지 (util 사용)
- ❌ pb2 import 후 미사용 금지
- ❌ 파일 맨 위에 주석 (# testCOMMONR_21_1.py) 금지

---

## 📝 출력 요구사항

1. **파일명**: `testCOMMONR_{{숫자}}_{{step_index}}.py`
   - 예: COMMONR-21 → testCOMMONR_21_1.py

2. **클래스명**: `testCOMMONR_{{숫자}}_{{step_index}}(TestCOMMONR)`

3. **함수명**: `testCommonr_{{숫자}}_{{step_index}}_{{N}}_{{설명}}()`
   - N: 1, 2, 3... (순차 증가)
   - 설명: 테스트 내용 요약

4. **완전한 Python 코드 생성**
   - TC의 모든 Test Step 구현
   - TC의 Test Data 반영
   - TC의 모든 Expected Result 검증
   - 데이터 생성 전략 준수
   - demo/test/ 패턴 참조

---

⚠️ **최종 체크**

**핵심 체크 (항목 3: Test Step / Data / Expected Result)** ⭐ 가장 중요
- [ ] TC의 Test Step 절차대로 구현
- [ ] TC의 Test Data 값 반영
- [ ] TC의 Expected Result 전체 검증

**기타 체크**
- [ ] 테스트케이스 분석 결과의 8개 항목 전체 반영
- [ ] 학습 내용에서 찾은 것만 사용 (추측 금지)
- [ ] demo/test/의 성공 패턴 참조
- [ ] util.함수명() 형태 사용
- [ ] pb2 import 시 반드시 사용
- [ ] 데이터 생성 전략 준수 (각 number 함수마다)
- [ ] 검증 코드 충분히 작성 (길어져도 됨)

**생성 계획과 TC 분석 결과를 기반으로, Test Step/Data/Expected Result가 완벽하게 충족되는 완전한 testCOMMONR 스타일 테스트 코드를 생성하세요.**

Think step by step. 시간이 오래 걸려도 괜찮습니다.
""")

            # 계획 프롬프트 포맷팅 (간소화)
            formatted_plan_prompt = self.automation_plan_prompt_template.format(
                accumulated_knowledge=accumulated_knowledge,
                test_case_content=test_case_info[0]['content'],
                test_case_metadata=test_case_info[0]['metadata'],
                test_case_analysis=test_case_analysis if test_case_analysis else "분석 내용 없음"
            )

            print("--- 자동화코드 계획 프롬프트 길이 ---")
            print(f"글자 수: {len(formatted_plan_prompt):,}자 (간소화됨!)")

            # LLM 호출 - 계획 생성
            await cl.Message(content="**3-1. 📝 자동화코드 계획 생성 중...**").send()
            print("   🔧 [코드 생성] 자동화코드 계획 생성 중...")
            generated_plans = await self.llm.ainvoke(formatted_plan_prompt)
            print("   ✅ [코드 생성] 자동화코드 계획 생성 완료")
            await cl.Message(content=f"✅ **계획 생성 완료**\n\n```markdown\n{generated_plans[:500]}...\n```").send()

            # 실제 코드 생성 프롬프트 포맷팅 (간소화)
            formatted_prompt = self.automation_prompt_template.format(
                accumulated_knowledge=accumulated_knowledge,
                test_case_content=test_case_info[0]['content'],
                test_case_analysis=test_case_analysis if test_case_analysis else "분석 내용 없음",
                generated_plan=generated_plans
            )

            print("--- 자동화코드 생성 프롬프트 길이 ---")
            print(f"글자 수: {len(formatted_prompt):,}자 (간소화됨!)")

            # LLM 호출
            await cl.Message(content="**3-2. ⚡ 최종 코드 생성 중...**").send()
            print("   🔧 [코드 생성] 최종 자동화코드 생성 중...")
            generated_code = await self.llm.ainvoke(formatted_prompt)
            print("   ✅ [코드 생성] 최종 자동화코드 생성 완료")
            await cl.Message(content="✅ **코드 생성 완료!**").send()

            # 코드 반환
            return generated_code
            
        except Exception as e:
            print(f"❌ 자동화코드 계획 생성 중 오류: {e}")
            return "자동화 코드 계획 생성에 실패했습니다."

class GraphState(TypedDict):
    # 필수 상태들
    original_query: str                     # 사용자의 최초 질문
    test_case_info: List[Dict]              # 테스트케이스 RAG에서 찾은 정보
    test_case_analysis: str                 # 테스트케이스 분석 결과 (커버리지 포함)
    retrieved_code_snippets: List[Dict]     # LLM이 선별한 자동화 코드 조각들
    cached_knowledge: str                   # 기존 캐시된 학습 내용
    knowledge_comparison: str               # 기존 지식과 새 학습 내용 비교 결과
    should_relearn: bool                    # 재학습 필요 여부
    missing_knowledge: str                  # 학습 비교 결과에서 추출한 누락된 지식
    user_feedback: str                      # 사용자 피드백 (재학습 선택 등)
    final_code: str                         # 최종 생성된 자동화 코드
    reasoning_process: str                  # 코드 생성 시 LLM의 추론 과정
    # ✨ 추가
    conversation_history: List[Dict[str, str]]  # [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    error: str                              # 에러 발생 시 메시지


class RAG_Graph(RAG_Function) :
    def __init__(self, **kwargs):
        # **kwargs로 모든 인자를 받아 부모 클래스에 전달
        super().__init__(**kwargs)
        self.graph = self._build_graph()
        
    # 1. 노드 정의 메서드
    async def testcase_rag_node(self, state: GraphState) -> Dict[str, Any]:
        """테스트 케이스 검색 노드"""
        await cl.Message(content=" **1. 🔍 테스트케이스 검색 시작...**").send()
        query = state['original_query']
        # 상속받은 retrieve_test_case 메서드 호출
        results = await self.retrieve_test_case(query)
        #chainlit에 실시간 결과값 표시
        await cl.Message(content=f"✅ **테스트케이스 검색 완료** \n```json\n{json.dumps(results, ensure_ascii=False, indent=2, default=str)}\n```").send()
        return {"test_case_info": results}

    async def analyze_testcase_node(self, state: GraphState) -> Dict[str, Any]:
        """테스트케이스 분석 노드 - 커버리지 평가 포함"""
        print("✅ current node : analyze_testcase_node")
        await cl.Message(content="**2. 🔍 테스트케이스 상세 분석 중...**").send()

        try:
            test_case_info = state.get("test_case_info", [])

            if not test_case_info:
                return {
                    "test_case_analysis": "테스트케이스 정보가 없습니다.",
                    "error": "테스트케이스 정보 누락"
                }

            # 기존 캐시된 지식 로드 (실제 존재하는 파일/API 정보)
            learn_all_info_list = self.load_learn_all_info()  # List[Dict]

            # 대화 배열을 텍스트로 변환 (프롬프트 삽입용 - content만 추출)
            learn_all_info_text = "\n\n".join([
                msg.get('content', '')
                for msg in learn_all_info_list
            ])

            # 테스트케이스 분석 수행 (기존 지식과 함께)
            analysis_result = await self.analyze_test_case(test_case_info, learn_all_info_text)

            return {"test_case_analysis": analysis_result}

        except Exception as e:
            error_msg = f"analyze_testcase_node 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "test_case_analysis": "분석 중 오류 발생",
                "error": error_msg
            }
        

    async def compare_knowledge_node(self, state: GraphState) -> Dict[str, Any]:
        """기존 학습 내용과 요구사항 비교 노드 - ✅ 사용자 선택 기능 추가 (3가지 옵션)"""
        print("✅ current node : compare_knowledge_node")
        await cl.Message(content="**3. ⚖️ 학습 내용 vs 요구사항 비교 중...**").send()

        try:
            test_case_analysis = state.get("test_case_analysis", "")
            cached_knowledge = self.load_learn_summary_info()

            # ✅ 비교 수행 (누락된 지식 포함)
            comparison_result, should_relearn, missing_knowledge = await self.compare_knowledge_with_requirements(
                cached_knowledge if cached_knowledge else "",
                test_case_analysis
            )

            # ✅ 비교 결과를 사용자에게 명확하게 표시
            comparison_display = f"""## 📊 학습 내용 비교 결과

    {comparison_result}

    ---

    **AI 판단:** {'🔄 증분 학습 필요' if should_relearn else '✅ 기존 지식으로 충분'}

    **누락된 지식:**
    ```
    {missing_knowledge if missing_knowledge else '없음'}
    ```
    """
            await cl.Message(content=comparison_display).send()

            # ✅ 사용자에게 2가지 버튼만 제공
            if should_relearn and missing_knowledge:
                # AI가 증분 학습 필요하다고 판단
                prompt_msg = "⚠️ **AI가 증분 학습이 필요하다고 판단했습니다.** 진행하시겠습니까?"
            else:
                # 기존 지식으로 충분
                prompt_msg = "✅ **기존 학습으로 충분합니다.** 어떻게 하시겠습니까?"

            res = await cl.AskActionMessage(
                content=prompt_msg,
                actions=[
                    cl.Action(name="use_missing", value="missing", label="🔄 증분 학습 (AI 추천)", payload={"choice": "missing"}),
                    cl.Action(name="skip", value="skip", label="⏭️ 기존 지식으로 진행", payload={"choice": "skip"}),
                ],
                timeout=120
            ).send()

            # ✅ 디버깅: 응답 확인
            print(f"🔍 [디버깅] AskActionMessage 응답: {res}")

            # ✅ Chainlit 응답 파싱 (timeout 시 기본값 "skip")
            if res:
                user_choice = res.get("name", "skip")  # "skip" 또는 "use_missing"
            else:
                # timeout 또는 응답 없음 → 기존 지식으로 진행
                user_choice = "skip"
                await cl.Message(content="⏱️ **시간 초과 - 기존 지식으로 진행합니다.**").send()

            print(f"🔍 [디버깅] 사용자 선택: {user_choice}")

            # ✅ 사용자 선택 결과 표시
            if user_choice == "skip":
                await cl.Message(content="⏭️ **기존 지식으로 코드 생성을 진행합니다.**").send()
                return {
                    "cached_knowledge": cached_knowledge if cached_knowledge else "",
                    "knowledge_comparison": comparison_result,
                    "missing_knowledge": "",
                    "should_relearn": False,
                    "user_feedback": ""  # ✨ 빈 문자열 → generate_code
                }
            elif user_choice == "use_missing":
                await cl.Message(content="🔄 **AI가 제안한 누락된 지식으로 증분 학습을 시작합니다.**").send()
                return {
                    "cached_knowledge": cached_knowledge if cached_knowledge else "",
                    "knowledge_comparison": comparison_result,
                    "missing_knowledge": missing_knowledge,
                    "should_relearn": True,
                    "user_feedback": missing_knowledge  # ✨ 누락된 지식 → additional_learn
                }

        except Exception as e:
            error_msg = f"compare_knowledge_node 오류: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "cached_knowledge": "",
                "knowledge_comparison": "비교 중 오류 발생",
                "missing_knowledge": "",
                "should_relearn": False,
                "user_feedback": "",
                "error": error_msg
            }
    
    
    async def generate_code_rag_node(self, state: GraphState) -> Dict[str, Any]:
        """자동화코드 생성 노드 - 테스트케이스 분석 결과 포함"""
        print("✅ current node : generate_code_rag_node")

        try:
            # GraphState에서 필요한 정보들 가져오기
            test_case_info = state.get("test_case_info", [])
            test_case_analysis = state.get("test_case_analysis", "")

            if not test_case_info:
                return {
                    "final_code": "테스트케이스 정보가 없어 코드를 생성할 수 없습니다.",
                    "error": "테스트케이스 정보 누락"
                }

            # 자동화 코드 생성 (테스트케이스 분석 결과 포함)
            generation_result = await self.generate_code(
                test_case_info,
                test_case_analysis
            )

            final_code = generation_result
            result = {
                "final_code": final_code
            }

            return result

        except Exception as e:
            error_msg = f"generate_code_rag_node 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "final_code": "코드 생성 중 오류가 발생했습니다.",
                "error": error_msg
            }
            
    async def learn_project_node(self, state: GraphState) -> Dict[str, Any]:
        """프로젝트 최초 학습 노드 - 캐시 확인 후 필요 시 학습"""
        print("✅ current node : learn_project_node")

        # 캐시 확인
        learn_summary_info = self.load_learn_summary_info()
        learn_all_info = self.load_learn_all_info()

        if learn_summary_info is not None and len(learn_all_info) > 0:
            print("✅ [캐시] 기존 학습 내용 사용")
            await cl.Message(content="✅ **기존 학습 내용을 불러왔습니다.**").send()
            # ✨ conversation_history도 로드
            return {
                "cached_knowledge": learn_summary_info,
                "conversation_history": learn_all_info
            }

        # 캐시 없음 → 최초 학습
        print("🔄 [학습] 캐시 없음 - 프로젝트 최초 학습 시작")
        await cl.Message(content="**🔄 프로젝트 최초 학습 시작...**").send()

        try:
            # additional_query 없이 호출 (최초 학습)
            learned_knowledge, conversation_history = await self.learn_project_structure()
            return {"cached_knowledge": learned_knowledge,
                    "conversation_history": conversation_history}
        except Exception as e:
            error_msg = f"❌ 학습 중 오류 발생: {str(e)}\n\nLM Studio 서버가 실행 중인지 확인하세요 (http://127.0.0.1:1234)"
            print(error_msg)
            await cl.Message(content=error_msg).send()
            return {
                "cached_knowledge": "",
                "conversation_history": [],
                "error": str(e)
            }
    
    async def additional_learn_project_node(self, state: GraphState) -> Dict[str, Any]:
        """프로젝트 추가 학습 노드 - 사용자 피드백 기반 추가 학습"""
        print("✅ current node : additional_learn_project_node")

        user_feedback = state.get("user_feedback", "")
        missing_knowledge = state.get("missing_knowledge", "")

        # 디버깅
        print(f"🔍 [additional_learn_project_node] user_feedback: '{user_feedback}' (type: {type(user_feedback)})")

        # 피드백이 없으면 기존 학습 데이터로 진행 (이 노드에 올 일이 없어야 함)
        if not user_feedback or user_feedback.strip() == "":
            print("⚠️ [경고] additional_learn_project_node에 피드백 없이 도착 - 기존 캐시 반환")
            cached_knowledge = self.load_learn_summary_info()
            return {"cached_knowledge": cached_knowledge}

        # 추가 학습 수행
        print("🔄 [추가 학습] - 프로젝트 추가 학습 시작")
        await cl.Message(content="**🔄 프로젝트 추가 학습 시작...**").send()

        # ✨ conversation_history를 파일에서 직접 로드 (GraphState가 아닌!)
        # 이유: 프로그램 재시작 또는 중간 진입 시 GraphState에 없을 수 있음
        conversation_history = self.load_learn_all_info()

        if not conversation_history:
            print("⚠️ [경고] conversation_history 없음 - 증분 학습 불가, 기존 캐시 반환")
            cached_knowledge = self.load_learn_summary_info()
            return {"cached_knowledge": cached_knowledge}

        # ✨ conversation_history 전달
        learned_knowledge = await self.learn_additional_content(
            additional_query=missing_knowledge,
            conversation_history=conversation_history  # ✨ 파일에서 로드한 이력 전달
        )
        self.save_learn_summary_info(learned_knowledge)

        return {"cached_knowledge": learned_knowledge}

    # 2. 조건부 엣지 함수 (노드 아님)
    #테스트케이스 전용 조건부 엣지 노드
    def testcase_decide_to_retry(self, state: GraphState) -> str:
        """테스트 케이스 검색 결과에 따라 다음 노드 결정"""
        test_cases = state.get("test_case_info", [])
        if not test_cases:
            return "retry_query"
        else:
            return "continue_workflow"
    

    #자동화코드 함수 전용 조건부 엣지 노드
    def automation_function_decide_to_retry(self, state: GraphState) -> str:
        """자동화코드 함수 검색 결과에 따라 다음 노드 결정"""
        print("✅ current node : automation_function_decide_to_retry")
        code_snippets = state.get("retrieved_code_snippets", [])
        if not code_snippets:
            return "retry_automation_function"
        else:
            return "generate_code"
        
    #자동화코드 함수 전용 조건부 엣지 노드
    def retry_learn_project(self, state: GraphState) -> str:
        """사용자 피드백에 따라 추가 학습 또는 코드 생성 결정"""
        print("✅ current node : retry_learn_project")
        user_feedback = state.get("user_feedback", "")

        # 디버깅
        print(f"🔍 [retry_learn_project] user_feedback: '{user_feedback}' (type: {type(user_feedback)})")

        # 빈 문자열이거나 None이면 코드 생성으로
        if not user_feedback or user_feedback.strip() == "":
            print("🔍 [retry_learn_project] → generate_code (기존 지식 사용)")
            return "generate_code"
        else:
            print("🔍 [retry_learn_project] → additional_learn (추가 학습)")
            return "additional_learn"
    
    
    # 3. 그래프 빌드 메서드
    def _build_graph(self):
        workflow = StateGraph(GraphState)

        # 모든 노드들 추가
        workflow.add_node("learn_project", self.learn_project_node)
        workflow.add_node("retrieve_test_case", self.testcase_rag_node)
        workflow.add_node("analyze_testcase", self.analyze_testcase_node)
        workflow.add_node("compare_knowledge", self.compare_knowledge_node)
        workflow.add_node("generate_automation_code", self.generate_code_rag_node)
        workflow.add_node("additional_learn_project", self.additional_learn_project_node)

        # 진입하는 노드 지정
        workflow.set_entry_point("learn_project")

        # 그래프 플로우:
        # 0. 학습 데이터 생성 (없으면 통과)
        workflow.add_edge("learn_project", "retrieve_test_case")
        # 1. 테스트케이스 검색
        workflow.add_edge("retrieve_test_case", "analyze_testcase")
        # 2. 테스트케이스 분석
        workflow.add_edge("analyze_testcase", "compare_knowledge")
        # ✨ 3. 지식 비교 → 사용자 버튼 선택 → 바로 분기
        workflow.add_conditional_edges(
            "compare_knowledge",
            self.retry_learn_project,  # 조건 함수 (수정 불필요)
            {
                "additional_learn": "additional_learn_project",  # missing_knowledge로 증분 학습
                "generate_code": "generate_automation_code"      # 기존 지식으로 코드 생성
            }
        )
        workflow.add_edge("additional_learn_project", "compare_knowledge")
        # 5. 코드 생성 (재학습 + 코드 생성)
        workflow.add_edge("generate_automation_code", END)

        return workflow.compile()
    
    # run_graph 메서드를 비동기 함수로 변경
    async def run_graph(self, query: str) -> GraphState:
        print("🚀 LangGraph 실행 시작")

        # ✨ 쿼리 파싱: step_index가 명시되어 있는지 확인
        import re
        issue_key_match = re.search(r'(COMMONR-\d+)', query)
        step_index_match = re.search(r'스텝\s*(\d+)', query)

        if not issue_key_match:
            print(f"⚠️ 쿼리에서 issue_key를 찾을 수 없습니다: {query}")
            return []

        issue_key = issue_key_match.group(1)
        specific_step = step_index_match.group(1) if step_index_match else None

        if specific_step:
            print(f"🎯 특정 스텝만 생성: {issue_key} 스텝 {specific_step}번")
        else:
            print(f"📚 모든 스텝 생성: {issue_key}")

        # ChromaDB에서 직접 검색
        if specific_step:
            # 특정 스텝만 검색
            where_filter = {
                "$and": [
                    {"issue_key": {"$eq": issue_key}},
                    {"step_index": {"$eq": specific_step}}
                ]
            }
        else:
            # 모든 스텝 검색
            where_filter = {"issue_key": {"$eq": issue_key}}

        collection = self.testcase_vectorstore.get(where=where_filter)

        if not collection or not collection.get('ids'):
            print(f"⚠️ {query}에 해당하는 테스트 스텝을 찾을 수 없습니다.")
            return []

        # 결과를 딕셔너리 형태로 변환
        testcase_results = []
        ids = collection.get('ids', [])
        metadatas = collection.get('metadatas', [])

        for i in range(len(ids)):
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    issue_key_meta = metadata.get('issue_key', query)
                    step_index_meta = metadata.get('step_index', i+1)

                    # 각 스텝에 대한 쿼리 생성
                    step_query = f"{issue_key_meta}의 스텝 {step_index_meta}번"

                    testcase_results.append({
                        "query": step_query,  # 재구성된 쿼리 추가
                        "metadata": metadata,
                    })

        # step_index로 정렬
        testcase_results.sort(key=lambda x: int(x['metadata'].get('step_index', 0)))
        
        for i in testcase_results :
            query = i['query']
            metadata = i['metadata']

            # 메타데이터에서 issue_key와 step_index 추출
            issue_key = metadata.get('issue_key', 'UNKNOWN')
            step_index = metadata.get('step_index', '0')

            # COMMONR-21 → 21 추출
            import re
            match = re.search(r'COMMONR-(\d+)', issue_key)
            issue_number = match.group(1) if match else 'UNKNOWN'

            initial_state = {
            "original_query": query
            }
            # invoke 대신 ainvoke 사용
            final_state = await self.graph.ainvoke(initial_state)
            
            output_dir = "/home/bes/BES_QE_SDK/generated_codes"
            #폴더가 없으면 생성
            os.makedirs(output_dir, exist_ok=True)
            # 파일명 생성: testCOMMONR21_1.py
            output_file = os.path.join(output_dir, f"testCOMMONR_{issue_number}_{step_index}.py")
            
            # 마크다운 코드 블록(```python, ```) 제거
            cleaned_code = re.sub(r'^```python\s*\n|^```\s*\n|\n```\s*$', '', final_state['final_code'], flags=re.MULTILINE).strip()
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(cleaned_code)
            print(f"✅ 저장 완료: {output_file}")
            
        
        print("✅ LangGraph 실행 완료")
        return final_state
        
async def process_query(user_query):
    """
    사용자의 쿼리를 받아 RAG_Graph를 실행하고 결과를 반환하는 함수
    """
    graph_run = RAG_Graph(
        testcase_db_path="/home/bes/BES_QE_RAG/testcase_rag/testcase_vectordb",
        automation_db_path="/home/bes/BES_QE_RAG/automation_rag/automation_vectordb",
        testcase_collection_name="testcase_vectordb",
        automation_collection_name="test_automation_functions",
        testcase_embedding_model="intfloat/multilingual-e5-large",
        automation_embedding_model="BAAI/bge-m3",
        lm_studio_url="http://127.0.0.1:1234/v1",
        lm_studio_model="qwen/qwen3-coder-30b"
    )

    final_state = await graph_run.run_graph(user_query)
    
    return final_state
    
