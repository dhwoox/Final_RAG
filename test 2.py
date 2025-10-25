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
    max_tokens: int = 2048
    
    def __init__(self, 
                 base_url: str = "http://127.0.0.1:1234/v1",
                 model_name: str = "qwen/qwen3-coder-30b",
                 temperature: float = 0.1,
                 max_tokens: int = 2048,
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
    knowledge_cache_path = "/home/bes/BES_QE_RAG/cached_knowledge.json"

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

    async def _analyze_core_usage(
        self,
        test_case_content: str,
        claude_md_content: str,
        core_contents: str
    ) -> str:
        """
        테스트케이스, CLAUDE.md, Core 파일을 분석하여
        Core 파일들을 어떻게 활용할지 세부 계획 수립
        """

        usage_plan_prompt = f"""당신은 GSDK Python 자동화 테스트 전문가입니다.

=== CLAUDE.md (프로젝트 구조) ===
{claude_md_content}

위 CLAUDE.md를 통해 프로젝트 구조를 먼저 이해하세요.

=== 테스트케이스 ===
{test_case_content}

=== Core 파일들 (testCOMMONR.py, manager.py, util.py) ===
{core_contents}

📝 **분석 목표**:
위 테스트케이스를 구현하기 위해 Core 파일들을 **어떻게 활용할지** 세부 계획을 수립하세요.

**계획 수립 항목:**

1. **testCOMMONR.py 활용 계획**
   - 어떤 헬퍼 메서드를 사용할 것인가?
   - 어떤 capability 체크가 필요한가?
   - setUp/tearDown에서 자동 처리되는 부분은 무엇인가?
   - 예시: "setCardOnlyAuthMode()를 사용하여 Card Only 모드 설정"

2. **manager.py (svcManager) 활용 계획**
   - 어떤 메서드를 호출할 것인가?
   - 호출 순서는 어떻게 되는가?
   - 각 메서드의 파라미터는 무엇인가?
   - 예시: "1. setAuthConfig() → 2. enrollUsers() → 3. getUsers()로 검증"

3. **util.py 활용 계획**
   - 어떤 Builder를 사용할 것인가?
   - 어떤 헬퍼 함수가 필요한가?
   - JSON 로드 패턴은 어떻게 되는가?
   - 예시: "UserBuilder로 ./data/User*.json 로드, 없으면 user_pb2로 생성"

4. **데이터 흐름 계획**
   - 테스트 데이터는 어떤 순서로 준비하는가?
   - 어떤 설정이 선행되어야 하는가?
   - 검증은 어떤 단계로 진행하는가?

5. **구현 전략**
   - 주의사항은 무엇인가?
   - 효율적인 구현 팁은?
   - 에러 처리는 어떻게 하는가?

**출력 형식 (자연어 텍스트):**

## Core 파일 활용 계획

### 1. testCOMMONR.py 활용
- **상속**: TestCOMMONR 클래스를 상속받아 setUp/tearDown 자동 실행
- **Capability 체크**: self.capability를 통한 capability 확인, 없으면 skipTest
- **헬퍼 메서드**: (필요한 경우) setCardOnlyAuthMode() 사용
- **자동 백업**: setUp에서 users, authMode, doors가 자동 백업됨

### 2. manager.py (svcManager) 활용
- **메서드 호출 순서**:
  1. self.svcManager.setAuthConfig(self.targetID, auth_config)
  2. self.svcManager.enrollUsers(self.targetID, [user])
  3. self.svcManager.getUsers(self.targetID, [user.hdr.ID])
- **각 메서드 설명**:
  - setAuthConfig: 인증 모드 설정 (파라미터: deviceID, AuthConfig 객체)
  - enrollUsers: 사용자 등록 (파라미터: deviceID, UserInfo 리스트)
  - getUsers: 사용자 조회 (파라미터: deviceID, 사용자 ID 리스트)

### 3. util.py 활용
- **Builder 사용**:
  - ./data 폴더에서 {{필요한 기능}}.json 파일 검색 및 로드
- **헬퍼 함수**:
  - randomUserID(True): alphanumeric 사용자 ID 생성
  - generateCardID(): 카드 ID 생성
- **JSON 없을 때 대체 방안**:
  - user_pb2.UserInfo() 직접 생성

### 4. 데이터 흐름
1. **준비 단계**: Auth Config 설정 → User 데이터 생성
2. **실행 단계**: User 등록 → 등록 확인
3. **검증 단계**: getUsers()로 조회 → assertEqual로 비교
4. **정리 단계**: tearDown에서 자동 정리

### 5. 구현 전략
- **JSON 우선 원칙**: 항상 ./data 폴더에서 JSON 파일을 먼저 찾기
- **에러 처리**: capability가 없으면 skipTest()로 건너뛰기
- **데이터 검증**: assertEqual 사용
- **주의사항**: User ID는 장치 타입에 따라 alphanumeric/numeric 구분

---

위와 같이 상세하고 실행 가능한 계획을 텍스트 형식으로 작성해주세요.
"""

        try:
            response = await self.llm.ainvoke(usage_plan_prompt)
            # 텍스트 그대로 반환 (JSON 파싱 불필요)
            return str(response)
        except Exception as e:
            print(f"❌ Core 활용 계획 분석 실패: {e}")
            return "Core 활용 계획 분석에 실패했습니다."

    async def _display_analysis_details(self, analysis: Dict[str, Any], stage_name: str):
        """분석 결과 상세 정보를 Chainlit으로 출력"""
        try:
            extracted_info = analysis.get('extracted_info', [])

            if not extracted_info:
                await cl.Message(content=f"⚠️ {stage_name} 분석에서 추출된 항목이 없습니다.").send()
                return

            # 각 단계별 아이콘
            icons = {
                "Proto": "📋",
                "pb2": "🔧",
                "Example": "💡",
                "Core": "⚙️"
            }
            icon = icons.get(stage_name, "📦")

            # 상세 정보 구성
            details = f"## {icon} {stage_name} 분석 상세 결과\n\n"
            details += f"**총 {len(extracted_info)}개 항목 추출됨**\n\n"

            # 각 항목 출력
            for idx, item in enumerate(extracted_info, 1):
                name = item.get('name', item.get('function_name', 'Unknown'))
                item_type = item.get('type', 'unknown')
                description = item.get('description', '설명 없음')
                relevance = item.get('relevance_score', 0)
                file_name = item.get('file', item.get('proto_file', ''))

                details += f"### {idx}. **{name}** ({item_type})\n"
                details += f"- **파일**: `{file_name}`\n"
                details += f"- **설명**: {description}\n"
                details += f"- **관련성 점수**: {relevance}/10\n"

                # 코드 조각이 있으면 표시
                code_snippet = item.get('code_snippet', item.get('fields', ''))
                if code_snippet:
                    # 코드 조각이 너무 길면 앞부분만 표시
                    if len(code_snippet) > 300:
                        code_snippet = code_snippet[:300] + "..."
                    details += f"- **코드 조각**:\n```python\n{code_snippet}\n```\n"

                # 사용 예제가 있으면 표시
                usage = item.get('usage_context', item.get('usage_example', ''))
                if usage and len(usage) > 10:
                    if len(usage) > 200:
                        usage = usage[:200] + "..."
                    details += f"- **사용 예제**: {usage}\n"

                details += "\n"

            # 분석된 파일 목록
            analyzed_files = analysis.get('analyzed_files', [])
            if analyzed_files:
                details += f"\n**분석된 파일 목록** ({len(analyzed_files)}개):\n"
                for file in analyzed_files:
                    details += f"- `{file}`\n"

            # 선별된 서비스/Proto 파일 (있는 경우)
            if stage_name == "Proto":
                identified_services = analysis.get('identified_services', [])
                if identified_services:
                    details += f"\n**식별된 서비스**: {', '.join(identified_services)}\n"

            await cl.Message(content=details).send()

        except Exception as e:
            print(f"⚠️ {stage_name} 분석 상세 정보 출력 실패: {e}")
            import traceback
            traceback.print_exc()

    async def _analyze_proto_files(self, test_case_content: str) -> Dict[str, Any]:
        """1단계: Proto 파일 선별 (파일 목록만 반환)"""
        import os
        import glob

        base_path = "/home/bes/BES_QE_RAG/automation_file_tree_rag/gsdk-client/python/biostar/proto"

        try:
            # CLAUDE.md 파일 읽기
            claude_md_content = ""
            try:
                claude_md_path = "/home/bes/BES_QE_RAG/CLAUDE.md"
                with open(claude_md_path, 'r', encoding='utf-8') as f:
                    claude_md_content = f.read()
                print("   📖 [Proto 선별] CLAUDE.md 로딩 완료")
            except Exception as e:
                print(f"   ⚠️ [Proto 선별] CLAUDE.md 읽기 실패: {e}")
                claude_md_content = "CLAUDE.md 파일을 읽을 수 없습니다."

            # proto 파일 목록 수집
            all_proto_files = glob.glob(os.path.join(base_path, "*.proto"))
            proto_list_str = "\n".join([os.path.basename(f) for f in all_proto_files])

            # AI가 관련 proto 파일 선별
            selection_prompt = f"""당신은 Protocol Buffer 전문가입니다.

=== 프로젝트 구조 이해 (CLAUDE.md) ===
{claude_md_content}

=== 테스트케이스 분석 ===
{test_case_content}

=== 사용 가능한 Proto 파일 목록 ===
{proto_list_str}

📝 **목표**: 테스트케이스에서 필요한 proto 파일을 선별하세요.
- 테스트케이스의 test step, data, expected result 구현에 필요한 파일들
- 넓은 범위로 선정해도 괜찮습니다 (의심스러우면 포함)

**출력 형식 (JSON)**:
{{
    "identified_services": ["auth", "device"],
    "selected_proto_files": ["auth.proto", "device.proto"],
    "reasoning": "선별 이유"
}}

**중요**: 반드시 JSON 형식으로만 응답하세요."""

            selection_response = await self.llm.ainvoke(selection_prompt)
            selection_data = self._safe_parse_json(selection_response, default={
                "identified_services": [],
                "selected_proto_files": []
            })

            selected_proto_files = selection_data.get("selected_proto_files", [])
            identified_services = selection_data.get("identified_services", [])

            print(f"   🎯 [Proto 선별] {len(selected_proto_files)}개 파일 선택: {', '.join(selected_proto_files)}")

            # 파일 경로 리스트 생성
            selected_proto_paths = []
            for proto_file_name in selected_proto_files:
                proto_file_path = os.path.join(base_path, proto_file_name)
                if os.path.exists(proto_file_path):
                    selected_proto_paths.append(proto_file_path)
                    print(f"   ✅ [Proto] {proto_file_name} 확인됨")
                else:
                    print(f"   ⚠️ [Proto] {proto_file_name} 파일이 존재하지 않습니다.")

            return {
                "source_type": "proto",
                "identified_services": identified_services,
                "selected_proto_files": selected_proto_files,
                "selected_proto_paths": selected_proto_paths
            }

        except Exception as e:
            print(f"❌ Proto 파일 선별 실패: {e}")
            return {
                "source_type": "proto",
                "identified_services": [],
                "extracted_info": [],
                "error": str(e)
            }

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



    def load_cached_knowledge(self) -> Optional[str]:
        """캐시된 학습 결과 로드"""
        import json

        # 1. 메모리 캐시 확인
        if RAG_Pipeline.cached_project_knowledge is not None:
            print("✅ [캐시] 메모리에서 학습 결과 로드 (즉시)")
            return RAG_Pipeline.cached_project_knowledge

        # 2. 파일 캐시 확인
        if os.path.exists(RAG_Pipeline.knowledge_cache_path):
            try:
                with open(RAG_Pipeline.knowledge_cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    knowledge = cached_data.get('knowledge', '')
                    timestamp = cached_data.get('timestamp', '')
                    print(f"✅ [캐시] 파일에서 학습 결과 로드 (저장 시각: {timestamp})")
                    # 메모리에도 저장
                    RAG_Pipeline.cached_project_knowledge = knowledge
                    return knowledge
            except Exception as e:
                print(f"⚠️ [캐시] 파일 로드 실패: {e}")
                return None

        print("ℹ️ [캐시] 캐시된 학습 결과 없음 - 새로 학습 필요")
        return None

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

        # 기존 지식이 없으면 간단한 CLAUDE.md만 로드
        if not existing_knowledge:
            try:
                claude_md_path = "/home/bes/BES_QE_RAG/CLAUDE.md"
                with open(claude_md_path, 'r', encoding='utf-8') as f:
                    existing_knowledge = f.read()
                print("   📖 [분석] CLAUDE.md 로딩 완료 (기본 구조 정보)")
            except Exception as e:
                print(f"   ⚠️ [분석] CLAUDE.md 읽기 실패: {e}")
                existing_knowledge = "기존 지식 정보 없음"

        analysis_prompt = f"""당신은 GSDK 테스트 자동화 전문가입니다.

아래 테스트케이스를 분석하여, 이 테스트를 자동화하기 위해 **필요한 지식과 커버리지**를 평가하세요.

=== 기존 프로젝트 지식 (실제 존재하는 파일/API 정보) ===
{existing_knowledge}...

**중요**: 위 프로젝트 지식에 **실제로 존재하는 파일과 API만** 언급하세요. 추측하거나 없는 것을 만들어내지 마세요.

=== 테스트케이스 내용 ===
{test_case_content}

=== 메타데이터 ===
{test_case_metadata}

**분석 항목:**

1. **테스트 목적 이해**
   - 이 테스트는 무엇을 검증하는가?
   - 핵심 시나리오는 무엇인가?

2. **필요한 기술 요소**
   - 어떤 proto 메시지/서비스가 필요한가?
   - 어떤 API 메서드를 호출해야 하는가?
   - 어떤 데이터를 준비해야 하는가?

3. **검증 항목 (Expected Result 기반)**
   - Expected Result의 각 항목을 구체적으로 나열
   - 각 검증 항목을 코드로 구현하기 위해 필요한 것은?

4. **테스트 데이터 요구사항**
   - 어떤 유형의 테스트 데이터가 필요한가? (User, Card, Schedule 등)
   - JSON 파일에서 로드해야 하는 데이터는?
   - 새로 생성해야 하는 데이터는?

5. **테스트 커버리지 요구사항**
   - 이 테스트를 완벽히 구현하기 위해 필요한 **지식의 범위**는?
   - manager.py의 어떤 메서드들을 알아야 하는가?
   - testCOMMONR.py의 어떤 기능을 사용해야 하는가?
   - util.py의 어떤 헬퍼/Builder가 필요한가?

**출력 형식:**
마크다운 형식으로 작성하되, 각 항목을 구체적이고 상세하게 작성하세요.
이 분석 결과는 코드 생성 시 참조되며, 학습 내용의 충족도를 평가하는 기준이 됩니다."""

        print("\n🔍 [테스트케이스 분석] 시작...")

        analysis_result = await self.llm.ainvoke(analysis_prompt)

        print(f"✅ [테스트케이스 분석] 완료 ({len(analysis_result):,}자)")
        await cl.Message(content=f"✅ **테스트케이스 분석 완료**\n\n```markdown\n{analysis_result[:600]}...\n```").send()

        return analysis_result

    async def compare_knowledge_with_requirements(
        self,
        cached_knowledge: str,
        test_case_analysis: str
    ) -> Tuple[str, bool]:
        """
        기존 캐시된 학습 내용과 테스트케이스 요구사항을 비교하여
        재학습이 필요한지 판단

        Returns:
            Tuple[str, bool]: (비교 결과, 재학습 필요 여부)
        """
        if not cached_knowledge:
            return "캐시된 학습 내용이 없습니다. 초기 학습이 필요합니다.", True

        comparison_prompt = f"""당신은 GSDK 테스트 자동화 전문가입니다.

기존에 학습한 내용과 현재 테스트케이스의 요구사항을 비교하여,
**재학습이 필요한지** 판단하세요.

=== 기존 학습 내용 (전체) ===
{cached_knowledge}

=== 테스트케이스 분석 결과 (요구사항) ===
{test_case_analysis}

**비교 및 평가 기준:**

1. **커버리지 충족도**
   - 테스트케이스가 요구하는 proto 메시지/서비스가 학습 내용에 포함되어 있는가?
   - 필요한 API 메서드들이 학습되어 있는가?
   - 데이터 생성/검증 패턴이 충분히 학습되어 있는가?

2. **누락된 지식**
   - 테스트 구현에 필요하지만 학습 내용에 없는 것은?
   - 추가 학습이 필요한 파일이나 기능은?

3. **재학습 필요성 판단**
   - **재학습 필요**: 핵심 기능이 누락되었거나 테스트 커버리지를 충족할 수 없는 경우
   - **재학습 불필요**: 기존 학습 내용만으로 테스트를 구현할 수 있는 경우

**출력 형식:**

## 커버리지 분석
- proto 메시지: [충족/부족]
- API 메서드: [충족/부족]
- 데이터 패턴: [충족/부족]

## 누락된 지식
- (있다면 구체적으로 나열)

## 재학습 필요성 판단
**결론: [재학습 필요/재학습 불필요]**

**이유**: (구체적으로 설명)

**재학습 시 추가할 내용**:
- (재학습이 필요한 경우, 어떤 파일/기능을 추가로 학습해야 하는지)

마지막 줄에 반드시 다음 중 하나를 명시하세요:
- RELEARN_REQUIRED (재학습 필요)
- RELEARN_NOT_REQUIRED (재학습 불필요)"""

        print("\n⚖️ [지식 비교] 시작...")
        await cl.Message(content="**⚖️ 기존 학습 내용과 요구사항 비교 중...**").send()

        comparison_result = await self.llm.ainvoke(comparison_prompt)

        # 재학습 필요 여부 판단
        should_relearn = "RELEARN_REQUIRED" in comparison_result

        print(f"✅ [지식 비교] 완료 - 재학습 필요: {should_relearn}")
        await cl.Message(content=f"✅ **비교 완료**\n\n```markdown\n{comparison_result[:600]}...\n```\n\n**재학습 필요: {'예' if should_relearn else '아니오'}**").send()

        return comparison_result, should_relearn

    def save_knowledge_to_cache(self, knowledge: str):
        """학습 결과를 캐시에 저장"""
        import json
        from datetime import datetime

        try:
            # 1. 메모리 캐시에 저장
            RAG_Pipeline.cached_project_knowledge = knowledge

            # 2. 파일 캐시에 저장
            cache_data = {
                'knowledge': knowledge,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(RAG_Pipeline.knowledge_cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            print(f"✅ [캐시] 학습 결과 저장 완료: {RAG_Pipeline.knowledge_cache_path}")
        except Exception as e:
            print(f"⚠️ [캐시] 저장 실패: {e}")

    async def learn_project_structure(self) -> str:
        """
        ✨ 프로젝트 전체 구조 DEEP LEARNING

        학습 범위:
        1. biostar/proto/ 전체 (.proto 파일들)
        2. biostar/service/ 전체 (__pycache__ 제외)
        3. demo/ 전체 (cli, test 폴더 포함)
        4. example/ 전체
        5. core 파일들 (manager.py, util.py, testCOMMONR.py)
        
        
        """
        import os
        import glob


        print("="*80)
        print("🧠 프로젝트 전체 DEEP LEARNING 시작")
        print("   - biostar/proto/ 전체")
        print("   - biostar/service/ 전체 (__pycache__ 제외)")
        print("   - demo/ 전체 (cli, test 포함)")
        print("   - example/ 전체")
        print("  (이 작업은 최초 1회만 수행되며, 결과는 저장됩니다)")
        print("="*80)

        python_base = "/home/bes/BES_QE_RAG/automation_file_tree_rag/gsdk-client/python"
        conversation_history = []

        # ===== Step 1: CLAUDE.md로 프로젝트 이해 =====
        await cl.Message(content="**📖 Step 1/5: CLAUDE.md 프로젝트 구조 학습 중...**").send()

        claude_md_content = ""
        try:
            claude_md_path = "/home/bes/BES_QE_RAG/CLAUDE.md"
            with open(claude_md_path, 'r', encoding='utf-8') as f:
                claude_md_content = f.read()
            print("   ✅ CLAUDE.md 로딩 완료")
        except Exception as e:
            print(f"   ⚠️ CLAUDE.md 읽기 실패: {e}")
            claude_md_content = "CLAUDE.md 파일을 읽을 수 없습니다."

        step1_prompt = f"""당신은 GSDK Python 자동화 테스트 전문가입니다.

이제부터 프로젝트의 **모든 내용을 깊이 학습**하겠습니다.

=== Step 1: 프로젝트 구조 DEEP LEARNING ===

{claude_md_content}

위 내용을 읽고 **모든 정보를 설명할 수 있도록** 학습하세요.
다음 내용을 **자세히** 설명하세요:

1. **프로젝트 목적과 구조**
   - GSDK란? gRPC 기반 장치 제어 시스템의 특징은?
   - 각 디렉토리(biostar/, example/, demo/)의 역할과 관계는?

2. **파일 역할 상세 분석**
   - biostar/proto/: Protocol Buffer 정의 파일들의 역할
   - biostar/service/: gRPC 서비스 구현 파일들 (*_pb2.py, *_pb2_grpc.py)
   - example/: 각 기능별 실행 가능한 예제 코드
   - demo/: 실제 테스트 실행 위치

3. **테스트 코드 작성 패턴**
   - TestCOMMONR 클래스 상속 구조
   - ServiceManager를 통한 API 호출 패턴
   - 데이터 로드 전략 (JSON → pb2)
   - import 순서와 규칙

4. **주요 컴포넌트**
   - manager.py의 역할과 제공 메서드들
   - util.py의 헬퍼 함수들과 Builder 클래스들
   - testCOMMONR.py의 setUp/tearDown 메커니즘

**중요**: 간결한 요약이 아닌, 이후 코드 생성 시 참고할 수 있도록 **상세하게** 작성하세요."""

        conversation_history.append({"role": "user", "content": step1_prompt})
        step1_response = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": step1_response})

        await cl.Message(content=f"✅ **프로젝트 이해 완료**\n\n{step1_response[:400]}...").send()
        print(f"\n[Step 1 완료] 프로젝트 이해:\n{step1_response[:300]}...\n")


        # ===== Step 2: biostar 폴더 전체 학습 (proto + service) =====
        await cl.Message(content="**📋 Step 2/5: biostar/proto + biostar/service 전체 학습 중...**").send()

        # 2-1: biostar/proto 전체
        proto_dir = os.path.join(python_base, "biostar/proto")
        proto_files = glob.glob(os.path.join(proto_dir, "*.proto"))

        proto_contents = ""
        read_count = 0
        total_proto = len(proto_files)
        print(f"\n   📋 biostar/proto: 총 {total_proto}개 파일")
        for proto_file in proto_files:
            try:
                with open(proto_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    proto_name = os.path.basename(proto_file)
                    proto_contents += f"\n{'='*60}\n파일: biostar/proto/{proto_name}\n{'='*60}\n{content}\n"
                    read_count += 1
                    if read_count % 5 == 0:
                        print(f"   ✅ [Proto] {read_count}/{total_proto} 완료...")
            except Exception as e:
                print(f"   ⚠️ [Proto 실패] {os.path.basename(proto_file)}: {e}")
        print(f"   ✅ [Proto 완료] {read_count}개 파일 ({len(proto_contents):,}자)\n")

        # 2-2: biostar/service 전체 (__pycache__ 제외)
        service_dir = os.path.join(python_base, "biostar/service")
        service_files = glob.glob(os.path.join(service_dir, "*.py"))

        service_contents = ""
        read_count = 0
        total_service = len(service_files)
        print(f"   🔧 biostar/service: 총 {total_service}개 파일")
        for service_file in service_files:
            # __pycache__ 제외
            if "__pycache__" in service_file:
                continue
            try:
                with open(service_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    service_name = os.path.basename(service_file)
                    service_contents += f"\n{'='*60}\n파일: biostar/service/{service_name}\n{'='*60}\n{content}\n"
                    read_count += 1
                    if read_count % 10 == 0:
                        print(f"   ✅ [Service] {read_count}/{total_service} 완료...")
            except Exception as e:
                print(f"   ⚠️ [Service 실패] {os.path.basename(service_file)}: {e}")
        print(f"   ✅ [Service 완료] {read_count}개 파일 ({len(service_contents):,}자)\n")

        # 통합
        biostar_contents = proto_contents + service_contents

        step2_prompt = f"""=== Step 2: biostar 폴더 전체 DEEP LEARNING ===

다음은 **biostar/proto + biostar/service 폴더의 전체 내용**입니다. 모든 내용을 읽고 학습하세요:

{biostar_contents}

위 proto 파일들을 읽고 **상세하게** 다음을 설명하세요:

1. **각 proto 파일의 역할**
   - user.proto: 어떤 메시지들을 정의하는가? (UserInfo, UserHdr 등)
   - auth.proto: 어떤 인증 모드와 enum들이 있는가?
   - device.proto: 장치 타입과 capability는?
   - door.proto, schedule.proto, card.proto 등: 각각의 핵심 메시지는?

2. **메시지 구조 이해**
   - 각 메시지의 필수 필드(required)와 선택 필드(optional)
   - repeated 필드들의 의미 (리스트 데이터)
   - nested 메시지 구조 (메시지 안의 메시지)

3. **Enum 값들**
   - AUTH_MODE, AUTH_EXT_MODE의 각 값들
   - DeviceType, CapabilityInfo의 필드들
   - 기타 중요한 enum들

4. **테스트 코드 작성 시 활용법**
   - 어떤 pb2 모듈을 import해야 하는가?
   - 메시지 객체를 어떻게 생성하는가? (예: user_pb2.UserInfo())
   - 필드 값을 어떻게 설정하는가?

**중요**: 각 proto 파일의 **모든 메시지와 필드**를 설명할 수 있도록 학습하세요.
이후 코드 생성 시 이 지식을 바탕으로 정확한 데이터 구조를 사용합니다."""

        conversation_history.append({"role": "user", "content": step2_prompt})
        step2_response = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": step2_response})

        await cl.Message(content=f"✅ **Proto 파일 역할 학습 완료**\n\n{step2_response[:400]}...").send()
        print(f"\n[Step 2 완료] Proto 파일 이해:\n{step2_response[:300]}...\n")


        # ===== Step 3: example 폴더 전체 학습 =====
        await cl.Message(content="**💡 Step 3/5: example 폴더 전체 학습 중...**").send()

        example_dir = os.path.join(python_base, "example")

        # example 폴더의 모든 하위 폴더에서 .py 파일 찾기
        example_contents = ""
        read_count = 0
        total_files = 0

        print(f"\n   💡 example 폴더: 하위 폴더 탐색 중...")
        for root, dirs, files in os.walk(example_dir):
            # __pycache__ 제외
            dirs[:] = [d for d in dirs if d != '__pycache__']

            for file in files:
                if file.endswith('.py'):
                    total_files += 1
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, python_base)

                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            example_contents += f"\n{'='*60}\n파일: {relative_path}\n{'='*60}\n{content}\n"
                            read_count += 1
                            if read_count % 20 == 0:
                                print(f"   ✅ [Example] {read_count}개 완료...")
                    except Exception as e:
                        print(f"   ⚠️ [Example 실패] {relative_path}: {e}")

        print(f"   ✅ [Example 완료] {read_count}개 파일 ({len(example_contents):,}자)\n")

        step3_prompt = f"""=== Step 3: example 폴더 DEEP LEARNING ===

다음은 **example 폴더의 실제 예제 코드들**입니다. 모든 내용을 읽고 학습하세요:

{example_contents}

위 예제 코드들을 읽고 **상세하게** 다음을 분석하세요:

1. **코드 구조 패턴**
   - import 순서와 사용하는 모듈들
   - 함수 정의 패턴 (파라미터, 반환값)
   - 에러 처리 방식

2. **API 호출 패턴**
   - channel, stub 생성 방법
   - gRPC 서비스 메서드 호출 방법
   - Request/Response 객체 사용법

3. **데이터 생성 및 처리**
   - pb2 객체 생성 패턴
   - 필드 값 설정 방법
   - 응답 데이터 파싱 방법

4. **실용적인 예제 분석**
   - 각 예제가 어떤 기능을 테스트하는가?
   - 어떤 순서로 API를 호출하는가?
   - 검증은 어떻게 수행하는가?

**중요**: 이 예제 코드들의 **모든 패턴과 사용법**을 이해하세요.
테스트 코드 작성 시 이 패턴들을 그대로 활용합니다."""

        conversation_history.append({"role": "user", "content": step3_prompt})
        step3_response = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": step3_response})

        await cl.Message(content=f"✅ **Example 폴더 학습 완료**\n\n{step3_response[:400]}...").send()
        print(f"\n[Step 3 완료] Example 폴더 이해:\n{step3_response[:300]}...\n")


        # ===== Step 4: demo 폴더 전체 학습 (cli, test 포함) =====
        await cl.Message(content="**⚙️ Step 4/5: demo 폴더 전체 학습 중... (cli, test 포함)**").send()

        demo_dir = os.path.join(python_base, "demo")

        # demo 폴더의 모든 .py 파일 (하위 폴더 포함: cli, test)
        demo_contents = ""
        read_count = 0

        print(f"\n   ⚙️ demo 폴더: 하위 폴더 탐색 중...")
        for root, dirs, files in os.walk(demo_dir):
            # __pycache__ 제외
            dirs[:] = [d for d in dirs if d != '__pycache__']

            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, python_base)

                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            demo_contents += f"\n{'='*60}\n파일: {relative_path}\n{'='*60}\n{content}\n"
                            read_count += 1
                            if read_count % 10 == 0:
                                print(f"   ✅ [Demo] {read_count}개 완료...")
                    except Exception as e:
                        print(f"   ⚠️ [Demo 실패] {relative_path}: {e}")

        print(f"   ✅ [Demo 완료] {read_count}개 파일 ({len(demo_contents):,}자)\n")

        step4_prompt = f"""=== Step 4: demo 폴더 핵심 파일들 DEEP LEARNING ===

다음은 **demo 폴더의 핵심 파일들 전체 내용**입니다. 모든 내용을 읽고 학습하세요:

{demo_contents}

위 파일들을 읽고 **상세하게** 다음을 분석하세요:

1. **manager.py (ServiceManager 클래스)**
   - ServiceManager의 모든 메서드 목록과 각 메서드의 역할
   - 각 메서드의 파라미터와 반환값
   - example 폴더의 함수들을 어떻게 활용하는가?
   - 어떤 서비스들을 제공하는가? (user, auth, door, access 등)

2. **testCOMMONR.py (테스트 베이스 클래스)**
   - TestCOMMONR 클래스의 모든 메서드
   - setUp(), tearDown()에서 자동으로 수행하는 작업들
   - self.svcManager, self.targetID 등 제공되는 속성들
   - capability 체크 메커니즘
   - backup/restore 메커니즘

3. **util.py (헬퍼 함수와 Builder)**
   - 모든 헬퍼 함수 목록 (randomUserID, generateCardID 등)
   - 모든 Builder 클래스 목록 (UserBuilder, ScheduleBuilder 등)
   - Builder의 사용법 (json.load(f, cls=UserBuilder))
   - 데이터 생성 전략 패턴

4. **✨ demo/test 폴더의 실제 테스트 예제 파일들 (중요!)**
   - 각 테스트 파일의 구조와 패턴
   - 어떤 기능을 테스트하는가?
   - 데이터 생성 방식 (JSON 로드 + pb2 객체 생성)
   - API 호출 순서와 검증 방법
   - skipTest 사용 패턴
   - assertEqual/assertTrue 등 assertion 사용법
   - 실제 동작하는 완전한 테스트 코드 예제들

5. **테스트 코드 작성 시 활용법**
   - import 방법 (from testCOMMONR import *)
   - svcManager를 통한 API 호출 예시
   - util 함수 사용 예시 (util.randomUserID())
   - Builder를 통한 JSON 로드 패턴
   - **✨ demo/test 예제 파일들의 패턴 활용법**
     - 테스트 클래스 구조 (class명, 함수명 규칙)
     - 데이터 준비 → API 호출 → 검증 흐름
     - 에러 처리 및 skipTest 조건
     - 실제 동작하는 코드 패턴 그대로 활용

**중요**: 
- manager.py, testCOMMONR.py, util.py의 **모든 함수, 클래스, 메서드**를 설명할 수 있도록 학습하세요.
- **✨ demo/test 폴더의 실제 테스트 파일들을 예시로 활용하여**, 테스트 코드 작성 시 이 패턴들을 그대로 참고할 수 있도록 학습하세요.
- 테스트 코드 생성 시 이 지식을 바탕으로 정확한 코드를 작성합니다."""

        conversation_history.append({"role": "user", "content": step4_prompt})
        step4_response = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": step4_response})

        await cl.Message(content=f"✅ **Demo 폴더 전체 학습 완료 (cli, test 포함!)**\n\n{step4_response[:400]}...").send()
        print(f"\n[Step 4 완료] Demo 폴더 이해:\n{step4_response[:300]}...\n")


        # ===== Step 5: 학습 내용 통합 요약 =====
        await cl.Message(content="**🎓 Step 5/5: 프로젝트 전체 학습 통합 중...**").send()

        final_summary_prompt = f"""=== 프로젝트 전체 학습 통합 ===

지금까지 학습한 내용을 바탕으로, 테스트 코드 작성 시 알아야 할 핵심 지식을 정리하세요.

**중요**: 이전 Step 1~4에서 학습한 **모든 내용**을 통합하여 정리하세요. 단순 요약이 아니라 **상세한 통합 지식**을 작성해야 합니다.

**통합해야 할 내용:**
- Step 1: CLAUDE.md 프로젝트 구조 (디렉토리 역할, 파일 관계)
- Step 2: biostar/proto + biostar/service 전체 (모든 proto 메시지, enum, 서비스 구현)
- Step 3: example 폴더 전체 (모든 예제 코드 패턴)
- Step 4: demo 폴더 전체 (manager.py의 모든 메서드, testCOMMONR.py의 모든 기능, util.py의 모든 헬퍼/Builder, 그 외 파일들)

**정리 형식:**

**1. 데이터 구조 (Proto 전체)**
- Step 2에서 학습한 **모든 proto 파일의 메시지 구조**를 정리
- 각 pb2 모듈들의 핵심 메시지와 필드들
- enum 값들과 그 의미
- 메시지 생성 및 필드 설정 패턴

**2. 서비스 구현 (biostar/service 전체)**
- Step 2에서 학습한 **모든 _pb2.py, _pb2_grpc.py 파일의 역할**
- 각 서비스의 gRPC 메서드들
- Request/Response 객체 사용법

**3. 예제 패턴 (example 폴더 전체)**
- Step 3에서 학습한 **모든 예제 코드의 패턴**
- API 호출 순서와 방법
- 데이터 생성 및 검증 패턴
- 에러 처리 방식

**4. 서비스 관리 (manager.py 전체)**
- Step 4에서 학습한 **ServiceManager의 모든 메서드**
- 각 메서드의 파라미터와 반환값
- example 함수들을 어떻게 활용하는지

**5. 테스트 베이스 (testCOMMONR.py 전체)**
- Step 4에서 학습한 **TestCOMMONR 클래스의 모든 기능**
- setUp/tearDown의 자동 처리 내용
- capability 체크, backup/restore 메커니즘
- 상속받을 때 사용 가능한 모든 메서드와 속성

**6. 유틸리티 (util.py 전체)**
- Step 4에서 학습한 **모든 헬퍼 함수**와 **모든 Builder 클래스**
- 데이터 생성 전략 (JSON 로드 패턴, Builder 사용법)
- 랜덤 데이터 생성 함수들

**7. 기타 demo 파일들**
- Step 4에서 학습한 demo.py, deviceMask.py, exception.py 등의 역할
- 이 파일들이 테스트 작성 시 어떻게 활용되는지

**8. 테스트 코드 작성 패턴 (전체 통합)**
- import 순서와 규칙
- 데이터 로드 패턴 (JSON → pb2)
- API 호출 패턴 (channel, stub, 메서드 호출)
- 검증 패턴 (unittest assertions)
- 전체 코드 구조 (클래스 상속, 함수 정의, docstring 등)

**중요**: 각 항목마다 **구체적인 예시와 함께** 작성하세요. 이 통합 지식은 이후 코드 생성 시 **유일한 참조 자료**로 활용됩니다."""

        conversation_history.append({"role": "user", "content": final_summary_prompt})
        final_summary = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": final_summary})

        await cl.Message(content=f"✅ **프로젝트 전체 학습 완료!**\n\n```markdown\n{final_summary[:800]}...\n```").send()
        print(f"\n{'='*80}")
        print(f"[프로젝트 학습 완료] 누적 지식:")
        print(f"{'='*80}")
        print(final_summary)
        print(f"{'='*80}\n")

        # ✨ 학습 결과를 캐시에 저장
        self.save_knowledge_to_cache(final_summary)

        # 학습 결과 반환
        return final_summary
    
    async def learn_additional_content(self, additional_query: str) -> str:
        """
        ✨ 프로젝트 전체 구조 추가 증분 학습 DEEP LEARNING

        학습 범위:
        1. biostar/proto/ 전체 (.proto 파일들)
        2. biostar/service/ 전체 (__pycache__ 제외)
        3. demo/ 전체 (cli, test 폴더 포함)
        4. example/ 전체

        **캐싱**: 한 번 학습하면 결과를 저장하여 재사용
        **추가 학습**: additional_query가 있으면 기존 학습에 추가하여 재학습

        Args:
            additional_query: 사용자가 요청한 추가 학습 내용
        """
        import os
        import glob

        # ✨ 캐시 확인 (추가 쿼리가 없는 경우만)
        if not additional_query:
            cached_knowledge = self.load_cached_knowledge()
            if cached_knowledge:
                return cached_knowledge
        else:
            # 추가 학습이 요청된 경우
            print(f"🔄 [추가 학습] 사용자 요청: {additional_query}")
            await cl.Message(content=f"**🔄 추가 학습 모드**\n\n사용자 요청: {additional_query}").send()

        print("="*80)
        print("🧠 프로젝트 전체 DEEP LEARNING 시작")
        print("   - biostar/proto/ 전체")
        print("   - biostar/service/ 전체 (__pycache__ 제외)")
        print("   - demo/ 전체 (cli, test 포함)")
        print("   - example/ 전체")
        print("  (이 작업은 최초 1회만 수행되며, 결과는 저장됩니다)")
        print("="*80)

        python_base = "/home/bes/BES_QE_RAG/automation_file_tree_rag/gsdk-client/python"
        conversation_history = []

        # ===== Step 1: CLAUDE.md로 프로젝트 이해 =====
        await cl.Message(content="**📖 Step 1/5: CLAUDE.md 프로젝트 구조 학습 중...**").send()

        claude_md_content = ""
        try:
            claude_md_path = "/home/bes/BES_QE_RAG/CLAUDE.md"
            with open(claude_md_path, 'r', encoding='utf-8') as f:
                claude_md_content = f.read()
            print("   ✅ CLAUDE.md 로딩 완료")
        except Exception as e:
            print(f"   ⚠️ CLAUDE.md 읽기 실패: {e}")
            claude_md_content = "CLAUDE.md 파일을 읽을 수 없습니다."

        step1_prompt = f"""당신은 GSDK Python 자동화 테스트 전문가입니다.

이제부터 프로젝트의 **모든 내용을 깊이 학습**하겠습니다.

=== Step 1: 프로젝트 구조 DEEP LEARNING ===

{claude_md_content}

위 내용을 읽고 **모든 정보를 설명할 수 있도록** 학습하세요.
다음 내용을 **자세히** 설명하세요:

1. **프로젝트 목적과 구조**
   - GSDK란? gRPC 기반 장치 제어 시스템의 특징은?
   - 각 디렉토리(biostar/, example/, demo/)의 역할과 관계는?

2. **파일 역할 상세 분석**
   - biostar/proto/: Protocol Buffer 정의 파일들의 역할
   - biostar/service/: gRPC 서비스 구현 파일들 (*_pb2.py, *_pb2_grpc.py)
   - example/: 각 기능별 실행 가능한 예제 코드
   - demo/: 실제 테스트 실행 위치

3. **테스트 코드 작성 패턴**
   - TestCOMMONR 클래스 상속 구조
   - ServiceManager를 통한 API 호출 패턴
   - 데이터 로드 전략 (JSON → pb2)
   - import 순서와 규칙

4. **주요 컴포넌트**
   - manager.py의 역할과 제공 메서드들
   - util.py의 헬퍼 함수들과 Builder 클래스들
   - testCOMMONR.py의 setUp/tearDown 메커니즘

**중요**: 간결한 요약이 아닌, 이후 코드 생성 시 참고할 수 있도록 **상세하게** 작성하세요."""

        conversation_history.append({"role": "user", "content": step1_prompt})
        step1_response = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": step1_response})

        await cl.Message(content=f"✅ **프로젝트 이해 완료**\n\n{step1_response[:400]}...").send()
        print(f"\n[Step 1 완료] 프로젝트 이해:\n{step1_response[:300]}...\n")


        # ===== Step 2: biostar 폴더 전체 학습 (proto + service) =====
        await cl.Message(content="**📋 Step 2/5: biostar/proto + biostar/service 전체 학습 중...**").send()

        # 2-1: biostar/proto 전체
        proto_dir = os.path.join(python_base, "biostar/proto")
        proto_files = glob.glob(os.path.join(proto_dir, "*.proto"))

        proto_contents = ""
        read_count = 0
        total_proto = len(proto_files)
        print(f"\n   📋 biostar/proto: 총 {total_proto}개 파일")
        for proto_file in proto_files:
            try:
                with open(proto_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    proto_name = os.path.basename(proto_file)
                    proto_contents += f"\n{'='*60}\n파일: biostar/proto/{proto_name}\n{'='*60}\n{content}\n"
                    read_count += 1
                    if read_count % 5 == 0:
                        print(f"   ✅ [Proto] {read_count}/{total_proto} 완료...")
            except Exception as e:
                print(f"   ⚠️ [Proto 실패] {os.path.basename(proto_file)}: {e}")
        print(f"   ✅ [Proto 완료] {read_count}개 파일 ({len(proto_contents):,}자)\n")

        # 2-2: biostar/service 전체 (__pycache__ 제외)
        service_dir = os.path.join(python_base, "biostar/service")
        service_files = glob.glob(os.path.join(service_dir, "*.py"))

        service_contents = ""
        read_count = 0
        total_service = len(service_files)
        print(f"   🔧 biostar/service: 총 {total_service}개 파일")
        for service_file in service_files:
            # __pycache__ 제외
            if "__pycache__" in service_file:
                continue
            try:
                with open(service_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    service_name = os.path.basename(service_file)
                    service_contents += f"\n{'='*60}\n파일: biostar/service/{service_name}\n{'='*60}\n{content}\n"
                    read_count += 1
                    if read_count % 10 == 0:
                        print(f"   ✅ [Service] {read_count}/{total_service} 완료...")
            except Exception as e:
                print(f"   ⚠️ [Service 실패] {os.path.basename(service_file)}: {e}")
        print(f"   ✅ [Service 완료] {read_count}개 파일 ({len(service_contents):,}자)\n")

        # 통합
        biostar_contents = proto_contents + service_contents

        step2_prompt = f"""=== Step 2: biostar 폴더 전체 DEEP LEARNING ===

다음은 **biostar/proto + biostar/service 폴더의 전체 내용**입니다. 모든 내용을 읽고 학습하세요:

{biostar_contents}

위 proto 파일들을 읽고 **상세하게** 다음을 설명하세요:

1. **각 proto 파일의 역할**
   - user.proto: 어떤 메시지들을 정의하는가? (UserInfo, UserHdr 등)
   - auth.proto: 어떤 인증 모드와 enum들이 있는가?
   - device.proto: 장치 타입과 capability는?
   - door.proto, schedule.proto, card.proto 등: 각각의 핵심 메시지는?

2. **메시지 구조 이해**
   - 각 메시지의 필수 필드(required)와 선택 필드(optional)
   - repeated 필드들의 의미 (리스트 데이터)
   - nested 메시지 구조 (메시지 안의 메시지)

3. **Enum 값들**
   - AUTH_MODE, AUTH_EXT_MODE의 각 값들
   - DeviceType, CapabilityInfo의 필드들
   - 기타 중요한 enum들

4. **테스트 코드 작성 시 활용법**
   - 어떤 pb2 모듈을 import해야 하는가?
   - 메시지 객체를 어떻게 생성하는가? (예: user_pb2.UserInfo())
   - 필드 값을 어떻게 설정하는가?

**중요**: 각 proto 파일의 **모든 메시지와 필드**를 설명할 수 있도록 학습하세요.
이후 코드 생성 시 이 지식을 바탕으로 정확한 데이터 구조를 사용합니다."""

        conversation_history.append({"role": "user", "content": step2_prompt})
        step2_response = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": step2_response})

        await cl.Message(content=f"✅ **Proto 파일 역할 학습 완료**\n\n{step2_response[:400]}...").send()
        print(f"\n[Step 2 완료] Proto 파일 이해:\n{step2_response[:300]}...\n")


        # ===== Step 3: example 폴더 전체 학습 =====
        await cl.Message(content="**💡 Step 3/5: example 폴더 전체 학습 중...**").send()

        example_dir = os.path.join(python_base, "example")

        # example 폴더의 모든 하위 폴더에서 .py 파일 찾기
        example_contents = ""
        read_count = 0
        total_files = 0

        print(f"\n   💡 example 폴더: 하위 폴더 탐색 중...")
        for root, dirs, files in os.walk(example_dir):
            # __pycache__ 제외
            dirs[:] = [d for d in dirs if d != '__pycache__']

            for file in files:
                if file.endswith('.py'):
                    total_files += 1
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, python_base)

                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            example_contents += f"\n{'='*60}\n파일: {relative_path}\n{'='*60}\n{content}\n"
                            read_count += 1
                            if read_count % 20 == 0:
                                print(f"   ✅ [Example] {read_count}개 완료...")
                    except Exception as e:
                        print(f"   ⚠️ [Example 실패] {relative_path}: {e}")

        print(f"   ✅ [Example 완료] {read_count}개 파일 ({len(example_contents):,}자)\n")

        step3_prompt = f"""=== Step 3: example 폴더 DEEP LEARNING ===

다음은 **example 폴더의 실제 예제 코드들**입니다. 모든 내용을 읽고 학습하세요:

{example_contents}

위 예제 코드들을 읽고 **상세하게** 다음을 분석하세요:

1. **코드 구조 패턴**
   - import 순서와 사용하는 모듈들
   - 함수 정의 패턴 (파라미터, 반환값)
   - 에러 처리 방식

2. **API 호출 패턴**
   - channel, stub 생성 방법
   - gRPC 서비스 메서드 호출 방법
   - Request/Response 객체 사용법

3. **데이터 생성 및 처리**
   - pb2 객체 생성 패턴
   - 필드 값 설정 방법
   - 응답 데이터 파싱 방법

4. **실용적인 예제 분석**
   - 각 예제가 어떤 기능을 테스트하는가?
   - 어떤 순서로 API를 호출하는가?
   - 검증은 어떻게 수행하는가?

**중요**: 이 예제 코드들의 **모든 패턴과 사용법**을 이해하세요.
테스트 코드 작성 시 이 패턴들을 그대로 활용합니다."""

        conversation_history.append({"role": "user", "content": step3_prompt})
        step3_response = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": step3_response})

        await cl.Message(content=f"✅ **Example 폴더 학습 완료**\n\n{step3_response[:400]}...").send()
        print(f"\n[Step 3 완료] Example 폴더 이해:\n{step3_response[:300]}...\n")


        # ===== Step 4: demo 폴더 전체 학습 (cli, test 포함) =====
        await cl.Message(content="**⚙️ Step 4/5: demo 폴더 전체 학습 중... (cli, test 포함)**").send()

        demo_dir = os.path.join(python_base, "demo")

        # demo 폴더의 모든 .py 파일 (하위 폴더 포함: cli, test)
        demo_contents = ""
        read_count = 0

        print(f"\n   ⚙️ demo 폴더: 하위 폴더 탐색 중...")
        for root, dirs, files in os.walk(demo_dir):
            # __pycache__ 제외
            dirs[:] = [d for d in dirs if d != '__pycache__']

            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, python_base)

                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            demo_contents += f"\n{'='*60}\n파일: {relative_path}\n{'='*60}\n{content}\n"
                            read_count += 1
                            if read_count % 10 == 0:
                                print(f"   ✅ [Demo] {read_count}개 완료...")
                    except Exception as e:
                        print(f"   ⚠️ [Demo 실패] {relative_path}: {e}")

        print(f"   ✅ [Demo 완료] {read_count}개 파일 ({len(demo_contents):,}자)\n")

        step4_prompt = f"""=== Step 4: demo 폴더 핵심 파일들 DEEP LEARNING ===

다음은 **demo 폴더의 핵심 파일들 전체 내용**입니다. 모든 내용을 읽고 학습하세요:

{demo_contents}

위 파일들을 읽고 **상세하게** 다음을 분석하세요:

1. **manager.py (ServiceManager 클래스)**
   - ServiceManager의 모든 메서드 목록과 각 메서드의 역할
   - 각 메서드의 파라미터와 반환값
   - example 폴더의 함수들을 어떻게 활용하는가?
   - 어떤 서비스들을 제공하는가? (user, auth, door, access 등)

2. **testCOMMONR.py (테스트 베이스 클래스)**
   - TestCOMMONR 클래스의 모든 메서드
   - setUp(), tearDown()에서 자동으로 수행하는 작업들
   - self.svcManager, self.targetID 등 제공되는 속성들
   - capability 체크 메커니즘
   - backup/restore 메커니즘

3. **util.py (헬퍼 함수와 Builder)**
   - 모든 헬퍼 함수 목록 (randomUserID, generateCardID 등)
   - 모든 Builder 클래스 목록 (UserBuilder, ScheduleBuilder 등)
   - Builder의 사용법 (json.load(f, cls=UserBuilder))
   - 데이터 생성 전략 패턴

4. **✨ demo/test 폴더의 실제 테스트 예제 파일들 (중요!)**
   - 각 테스트 파일의 구조와 패턴
   - 어떤 기능을 테스트하는가?
   - 데이터 생성 방식 (JSON 로드 + pb2 객체 생성)
   - API 호출 순서와 검증 방법
   - skipTest 사용 패턴
   - assertEqual/assertTrue 등 assertion 사용법
   - 실제 동작하는 완전한 테스트 코드 예제들

5. **테스트 코드 작성 시 활용법**
   - import 방법 (from testCOMMONR import *)
   - svcManager를 통한 API 호출 예시
   - util 함수 사용 예시 (util.randomUserID())
   - Builder를 통한 JSON 로드 패턴
   - **✨ demo/test 예제 파일들의 패턴 활용법**
     - 테스트 클래스 구조 (class명, 함수명 규칙)
     - 데이터 준비 → API 호출 → 검증 흐름
     - 에러 처리 및 skipTest 조건
     - 실제 동작하는 코드 패턴 그대로 활용

**중요**: 
- manager.py, testCOMMONR.py, util.py의 **모든 함수, 클래스, 메서드**를 설명할 수 있도록 학습하세요.
- **✨ demo/test 폴더의 실제 테스트 파일들을 예시로 활용하여**, 테스트 코드 작성 시 이 패턴들을 그대로 참고할 수 있도록 학습하세요.
- 테스트 코드 생성 시 이 지식을 바탕으로 정확한 코드를 작성합니다."""

        conversation_history.append({"role": "user", "content": step4_prompt})
        step4_response = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": step4_response})

        await cl.Message(content=f"✅ **Demo 폴더 전체 학습 완료 (cli, test 포함!)**\n\n{step4_response[:400]}...").send()
        print(f"\n[Step 4 완료] Demo 폴더 이해:\n{step4_response[:300]}...\n")


        # ===== Step 5: 학습 내용 통합 요약 =====
        await cl.Message(content="**🎓 Step 5/5: 프로젝트 전체 학습 통합 중...**").send()

        # 사용자 추가 쿼리가 있는 경우 프롬프트에 반영
        additional_instruction = ""
        if additional_query:
            additional_instruction = f"""

**✨ 사용자 추가 학습 요청:**
{additional_query}

위 내용을 **특별히 중점적으로** 학습하고 통합 지식에 포함하세요. 기존 학습 내용에 이 정보를 추가하여 더 완전한 지식 베이스를 구축하세요."""

        final_summary_prompt = f"""=== 프로젝트 전체 학습 통합 ===

지금까지 학습한 내용을 바탕으로, 테스트 코드 작성 시 알아야 할 핵심 지식을 정리하세요.

**중요**: 이전 Step 1~4에서 학습한 **모든 내용**을 통합하여 정리하세요. 단순 요약이 아니라 **상세한 통합 지식**을 작성해야 합니다.{additional_instruction}

**통합해야 할 내용:**
- Step 1: CLAUDE.md 프로젝트 구조 (디렉토리 역할, 파일 관계)
- Step 2: biostar/proto + biostar/service 전체 (모든 proto 메시지, enum, 서비스 구현)
- Step 3: example 폴더 전체 (모든 예제 코드 패턴)
- Step 4: demo 폴더 전체 (manager.py의 모든 메서드, testCOMMONR.py의 모든 기능, util.py의 모든 헬퍼/Builder, 그 외 파일들)

**정리 형식:**

**1. 데이터 구조 (Proto 전체)**
- Step 2에서 학습한 **모든 proto 파일의 메시지 구조**를 정리
- 각 pb2 모듈들의 핵심 메시지와 필드들
- enum 값들과 그 의미
- 메시지 생성 및 필드 설정 패턴

**2. 서비스 구현 (biostar/service 전체)**
- Step 2에서 학습한 **모든 _pb2.py, _pb2_grpc.py 파일의 역할**
- 각 서비스의 gRPC 메서드들
- Request/Response 객체 사용법

**3. 예제 패턴 (example 폴더 전체)**
- Step 3에서 학습한 **모든 예제 코드의 패턴**
- API 호출 순서와 방법
- 데이터 생성 및 검증 패턴
- 에러 처리 방식

**4. 서비스 관리 (manager.py 전체)**
- Step 4에서 학습한 **ServiceManager의 모든 메서드**
- 각 메서드의 파라미터와 반환값
- example 함수들을 어떻게 활용하는지

**5. 테스트 베이스 (testCOMMONR.py 전체)**
- Step 4에서 학습한 **TestCOMMONR 클래스의 모든 기능**
- setUp/tearDown의 자동 처리 내용
- capability 체크, backup/restore 메커니즘
- 상속받을 때 사용 가능한 모든 메서드와 속성

**6. 유틸리티 (util.py 전체)**
- Step 4에서 학습한 **모든 헬퍼 함수**와 **모든 Builder 클래스**
- 데이터 생성 전략 (JSON 로드 패턴, Builder 사용법)
- 랜덤 데이터 생성 함수들

**7. 기타 demo 파일들**
- Step 4에서 학습한 demo.py, deviceMask.py, exception.py 등의 역할
- 이 파일들이 테스트 작성 시 어떻게 활용되는지

**8. 테스트 코드 작성 패턴 (전체 통합)**
- import 순서와 규칙
- 데이터 로드 패턴 (JSON → pb2)
- API 호출 패턴 (channel, stub, 메서드 호출)
- 검증 패턴 (unittest assertions)
- 전체 코드 구조 (클래스 상속, 함수 정의, docstring 등)

**중요**: 각 항목마다 **구체적인 예시와 함께** 작성하세요. 이 통합 지식은 이후 코드 생성 시 **유일한 참조 자료**로 활용됩니다."""

        conversation_history.append({"role": "user", "content": final_summary_prompt})
        final_summary = await self.llm.ainvoke_with_history(conversation_history)
        conversation_history.append({"role": "assistant", "content": final_summary})

        await cl.Message(content=f"✅ **프로젝트 전체 학습 완료!**\n\n```markdown\n{final_summary[:800]}...\n```").send()
        print(f"\n{'='*80}")
        print(f"[프로젝트 학습 완료] 누적 지식:")
        print(f"{'='*80}")
        print(final_summary)
        print(f"{'='*80}\n")

        # 학습 결과 반환
        return final_summary


    async def generate_code(self, test_case_info: List[Dict], selected_files_dict: Dict[str, Any], test_case_analysis: str = "") -> str:
        """
        ✨ 간소화: 학습된 내용만 사용 (파일 재로딩 불필요)
        ✨ 개선: 테스트케이스 분석 내용 포함
        """
        import os
        import json

        try:
            print("--- 3. ⚡ 자동화코드 생성 (캐시된 학습 내용 기반) ---")

            # ✨ 프로젝트 전체 학습 로드 (캐시 사용)
            accumulated_knowledge = await self.load_cached_knowledge()
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

  ✨ === 프로젝트 전체 학습 결과 (사전 학습 완료) ===

  당신은 이미 다음 내용을 학습했습니다:

  {accumulated_knowledge}

  위 내용은 다음 폴더들의 **전체 파일**을 학습한 결과입니다:
  - biostar/proto/ 전체
  - biostar/service/ 전체 (__pycache__ 제외)
  - demo/ 전체 (cli, test 포함)
  - example/ 전체

  이 지식을 바탕으로 코드를 생성하세요.

  ✨ === 테스트케이스 분석 결과 ===

  테스트케이스가 상세히 분석되었습니다:

  {test_case_analysis}

  위 분석 결과를 바탕으로, **모든 검증 항목을 충족**하는 코드를 생성하세요.

  🎯 자동화코드 계획 생성 요청:

  테스트 케이스 내용:

  {test_case_content}

  메타데이터 정보:

  {test_case_metadata}

   #제발 이것만은 지켜주세요
   util안의 기능들을 사용했다면 import란에 util만 적고 util.{{사용한 기능}}로 적어주세요

  📝 생성 지침:
  0. util 안의 함수나 클래스, 라이브러리를 사용했다면 util.~로 생성하면 됩니다. import쪽에 util에서 사용한 것들을 import하지마세요
  1. 먼저 claude.md 파일의 구조와 테스트케이스의 내용을 통해서 proto 파일과 core 파일들을 어떻게 활용할지 생각해주세요
  2. proto 파일들과 Core 파일들에는 어디서 가져왔는지에 대해서 경로가 각각 명시되어 있어서 claude.md 파일의 내용을 통해서 어떻게 활용할지에 대해서 이해하고 활용하면 됩니다.
  3. 테스트케이스의 test step, data, expected result가 완벽하게 충족되도록 계획을 세워야합니다.
  4. 하나의 step_index의 하위 number들마다 테스트데이터 생성 지침에 따라야합니다.
  5. 한 번에 통과될만큼 완벽하고 정말 좋은 계획이어야합니다. 기대하고 있습니다.
  6. 테스트 데이터 생성하는 부분이 아래의 지침을 아예 따르지 않고 있습니다. 데이터 생성이 되어야 완전한 테스트 자동화 코드를 생성할 수 있으므로
  아래의 테스트 데이터 생성 전략을 꼭 따라주세요
  7. 테스트 데이터 생성 전략

            ✅ 테스트데이터 생성 전략 1: 기존 JSON 파일 활용

                    데이터 생성의 예시 : 하나의 step_index의 각 number 함수들마다 테스트데이터 생성 지침에 따라야합니다.
                    # 데이터 생성 전략 : 기존 json 파일 활용 우선
                    ## 활용할 수 있는 데이터는 util.py의 import란의 builder 부분에서 확인 가능
                    {{사용하려는 data}} = None
                    for entry in os.listdir("./data"):
                        if entry.startswith("{{사용하려는 data}}") and entry.endswith(".json"):
                            with open("./data/" + entry, encoding='UTF-8') as f:
                                user = json.load(f, cls={{사용하려는 data}}Builder)
                                break
                                
                    ## 중요 ! : 위의 데이터로 검증할 수 없어 새로 데이터를 생성해야되는 경우 위의 json 파일의 값을 이용하여 생성할 것
                    ### 예시 : 지문 + PIN 유저를 생성해야하는 경우 위 위의 유저의 지문 + PIN 값을 이용하여 생성
                    

  8. pb2를 사용하려고 import했으면 꼭 사용할 것 pb2 import 되어있는데 코드 상에 작성되어 있지 않으면 벌을 받아야함
  
  ### 🏗️ 파일명 및 클래스 구조:
  - **파일명**: `testCOMMONR_{{issue_number}}_{{step_index}}.py`
  - **클래스명**: `testCOMMONR_{{issue_number}}_{{step_index}}(TestCOMMONR)`
  - **함수명**: `testCommonr_{{issue_number}}_{{step_index}}_{{number}}_{{description}}()`

  ### 📦 필수 Import 패턴 :
  ### 아래의 4개 import는 반드시 import 후 사용
  import unittest
  import util
  from testCOMMONR import *
  from manager import ServiceManager
  
  ### 여기서부터는 실제로 사용되면 import
  **외부 함수나 모듈, 클래스들을 활용했다면 꼭 import에 해당 파일을 import할 것**
  import {{service}}_pb2 #사용한 pb2와 관련된 모듈은 필수로 import해서 사용할 것

  🔧 기본 구조 템플릿 (공통):

  class testCOMMONR_{{issue_number}}_{{step_index}}(TestCOMMONR):
      \"\"\"
          전체 테스트 시나리오 설명 (테스트케이스 기반)
      \"\"\"
      def testCommonr_{{issue_number}}_{{step_index}}_{{number}}_{{description}}(self):
          
          \"\"\"
          해당 함수 테스트 시나리오 설명 (테스트케이스 기반)
          테스트케이스의 Test Step, Data, Expected Result에서 어떤 부분을 충족시키는지 작성
          \"\"\"
          # skiptest 체크 (필요한 경우, 검증하는데 필요한 것들 체크 후 없으면 skiptest)

          # 데이터 생성 전략 : 기존 json 파일 활용 우선
          ## 중요 ! : 위의 데이터로 검증할 수 없어 새로 데이터를 생성해야되는 경우 위의 json 파일의 값을 이용하여 생성할 것
          ## 활용할 수 있는 데이터는 util.py의 import란의 builder 부분에서 확인 가능
          ### 예시 : 지문 + PIN 유저를 생성해야하는 경우 위 유저의 지문 + PIN 값을 이용하여 생성
          ### 중요 !  : 하나의 step_index의 각 number 함수들마다 테스트데이터 생성 지침에 따라야합니다, number 1번만 잘 따르는 경향이 있습니다.

        # 중요 ! : 여기에 가장 중요한 검증과 관련된 자동화 코드 작성! test step, data, expected result를 바탕으로 완벽한 결과가 나와야함
            

  🔢 메타데이터에서 추출할 정보:

  - issue_key: COMMONR-XX 형식에서 숫자 부분 추출 (예: "COMMONR-12" → "12")
  - step_index: 스텝 인덱스 (예: "1", "2")
  - service_name: 서비스명 (테스트 내용에서 추론)
  - function_name: 기능명 (테스트 내용에서 추론)

  📋 생성 요구사항:
  중요 ! : 테스트케이스 구현할 때, Expected Result의 결과가 충족되도록 작성되어야합니다. Expected Result을 중복해서 만족할 필요는 없습니다
  0. 테스트케이스에 따른 검증이 가장 중요합니다. 테스트케이스를 할 수 있는 최대한으로 구현해주세요, 데이터 전략도 잘 준수하고 검증도 잘 챙겨주세요 제발
  1. 파일명: testCOMMONR_{{issue_key에서 추출한 숫자}}_{{step_index}}.py
    - 예: issue_key="COMMONR-12", step_index="1" → testCOMMONR_12_1.py
  2. 클래스명: testCOMMONR_{{issue_key에서 추출한 숫자}}_{{step_index}}(TestCOMMONR)
    - 예: testCOMMONR_12_1(TestCOMMONR)
  3. 함수명들: testCommonr_{{issue_key에서 추출한 숫자}}_{{step_index}}_N_{{scenario_description}}()
    - 예: testCommonr_12_1_1_general(), testCommonr_12_1_2_specific_case()
    중요 ! : 위의 파일,클래스,함수명 예시를 참고하되 예시를 아예 똑같이하면 안 됩니다.
  4. unittest를 이용한 검증
  5. json 폴더 안에 있는 data를 바탕으로 생성 (user,schedule 등등)
  6. docstring - 각 함수의 테스트 목적 명시
  7. 테스트케이스 내용을 기반으로 한 요구사항에 맞는 자동화 테스트 결과 생성, 테스트케이스의 test step, data, expected result가 완벽하게 충족되어야함
  8. 테스트케이스를 보고 skip할 수 있는 조건들은 묶어서 skip.test를 하도록 생성
  9. 외부 라이브러리나 모듈을 사용했다면 꼭 import란에 넣을 것
  10. pb2를 사용할거라면 꼭 function 내에 사용되어야합니다
  

  ⚠️ 필수 요구사항:
  - builder 클래스를 직접 import해서 사용하지말고 util.py를 활용하세요
  - 메타데이터에서 issue_key의 숫자 부분과 step_index를 정확히 추출하여 사용
  - 기존 GSDK testCOMMONR 패턴 완전히 준수
  - setUp/tearDown 메서드 생성하지 말 것
  - ServiceManager API를 통한 모든 디바이스 통신
  - 데이터 생성 전략을 잘 준수할 것
  - 현재 검증 부분이 매우 부족하므로 테스트케이스를 할 수 있는 최대한으로 구현해서 검증할 것, 코드가 길어져도 됩니다.
  - 데이터 생성 전략과 검증 부분이 함께 잘 작성되어야함, 가끔 한쪽으로 치우칠 떄가 있음
  - 코드의 정확도가 중요하므로 길게 생각해서 생성해주세요. 본인이 전문가라고 생각하고 코드가 완벽히 pass로 성공해야합니다.

  메타데이터의 issue_key와 step_index에서 번호를 추출하고, 참조 코드 조각을 참고하여 테스트 케이스의 테스트케이스의 test step, data, expected result가 완벽하게 충족되도록 완전한 testCOMMONR 스타일 테스트 코드를 생성해주세요
  testCOMMONR 스타일 테스트 코드 생성 계획을 꼼꼼하게 세워주세요 시간이 오래 걸려도 괜찮습니다. think step by step
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

  ✨ === 프로젝트 전체 학습 결과 (사전 학습 완료) ===

  당신은 이미 다음 내용을 학습했습니다:

  {accumulated_knowledge}

  위 내용은 다음 폴더들의 **전체 파일**을 학습한 결과입니다:
  - biostar/proto/ 전체
  - biostar/service/ 전체 (__pycache__ 제외)
  - demo/ 전체 (cli, test 포함)
  - example/ 전체

  이 지식을 바탕으로 코드를 생성하세요.

  ✨ === 테스트케이스 분석 결과 ===

  테스트케이스가 상세히 분석되었습니다:

  {test_case_analysis}

  위 분석 결과의 **모든 검증 항목**을 코드에 반영하세요.

  🎯 자동화코드 생성 요청:

  테스트 케이스 내용:

  {test_case_content}

  === 자동화코드 계획 정보 ===

  {generated_plan}

  #제발 이것만은 지켜주세요
   util안의 기능들을 사용했다면 import란에 util만 적고 util.{{사용한 기능}}로 적어주세요

  📝 생성 지침:
  0. util 안의 함수나 클래스, 라이브러리를 사용했다면 util.~로 생성하면 됩니다. import쪽에 util에서 사용한 것들을 import하지마세요
  1. 먼저 claude.md 파일의 구조와 테스트케이스의 내용을 통해서 proto 파일과 core 파일들을 어떻게 활용할지 생각해주세요
  2. proto 파일들과 Core 파일들에는 어디서 가져왔는지에 대해서 경로가 각각 명시되어 있어서 claude.md 파일의 내용을 통해서 어떻게 활용할지에 대해서 이해하고 활용하면 됩니다.
  3. 테스트케이스의 test step, data, expected result가 완벽하게 충족되도록 계획을 세워야합니다.
  4. 하나의 step_index의 하위 number들마다 테스트데이터 생성 지침에 따라야합니다.
  5. 한 번에 통과될만큼 완벽하고 정말 좋은 계획이어야합니다. 기대하고 있습니다.
  6. 테스트 데이터 생성하는 부분이 아래의 지침을 아예 따르지 않고 있습니다. 데이터 생성이 되어야 완전한 테스트 자동화 코드를 생성할 수 있으므로
  아래의 테스트 데이터 생성 전략을 꼭 따라주세요
  7. 테스트 데이터 생성 전략

            ✅ 테스트데이터 생성 전략 1: 기존 JSON 파일 활용

                    데이터 생성의 예시 : 하나의 step_index의 각 number 함수들마다 테스트데이터 생성 지침에 따라야합니다.
                    # 데이터 생성 전략 : 기존 json 파일 활용 우선
                    ## 활용할 수 있는 데이터는 util.py의 import란의 builder 부분에서 확인 가능
                    {{사용하려는 data}} = None
                    for entry in os.listdir("./data"):
                        if entry.startswith("{{사용하려는 data}}") and entry.endswith(".json"):
                            with open("./data/" + entry, encoding='UTF-8') as f:
                                user = json.load(f, cls={{사용하려는 data}}Builder)
                                break
                                
                    ## 중요 ! : 위의 데이터로 검증할 수 없어 새로 데이터를 생성해야되는 경우 위의 json 파일의 값을 이용하여 생성할 것
                    ### 예시 : 지문 + PIN 유저를 생성해야하는 경우 위 유저의 지문 + PIN 값을 이용하여 생성
                    
  8. pb2를 사용하려고 import했으면 꼭 사용할 것 pb2 import 되어있는데 코드 상에 작성되어 있지 않으면 벌을 받아야함
  
  ### 🏗️ 파일명 및 클래스 구조:
  - **파일명**: `testCOMMONR_{{issue_number}}_{{step_index}}.py`
  - **클래스명**: `testCOMMONR_{{issue_number}}_{{step_index}}(TestCOMMONR)`
  - **함수명**: `testCommonr_{{issue_number}}_{{step_index}}_{{number}}_{{description}}()`

  ### 📦 필수 Import 패턴 :
  ### 아래의 4개 import는 반드시 import 후 사용
  import unittest
  import util
  from testCOMMONR import *
  from manager import ServiceManager
  
  ### 여기서부터는 실제로 사용되면 import
  **외부 함수나 모듈, 클래스들을 활용했다면 꼭 import에 해당 파일을 import할 것**
  import {{service}}_pb2 #사용한 pb2와 관련된 모듈은 필수로 import해서 사용할 것
  

  🔧 기본 구조 템플릿 (공통):

  class testCOMMONR_{{issue_number}}_{{step_index}}(TestCOMMONR):
      \"\"\"
          전체 테스트 시나리오 설명 (테스트케이스 기반)
      \"\"\"
      def testCommonr_{{issue_number}}_{{step_index}}_{{number}}_{{description}}(self):
          
          \"\"\"
          해당 함수 테스트 시나리오 설명 (테스트케이스 기반)
          테스트케이스의 Test Step, Data, Expected Result에서 어떤 부분을 충족시키는지 작성
          \"\"\"
          # skiptest 체크 (필요한 경우, 검증하는데 필요한 것들 체크 후 없으면 skiptest)

        # 데이터 생성 전략 : 기존 json 파일 활용 우선
        ## 중요 ! : 위의 데이터로 검증할 수 없어 새로 데이터를 생성해야되는 경우 위의 json 파일의 값을 이용하여 생성할 것
        ## 활용할 수 있는 데이터는 util.py의 import란의 builder 부분에서 확인 가능
        ### 예시 : 지문 + PIN 유저를 생성해야하는 경우 위 유저의 지문 + PIN 값을 이용하여 생성
        ### 중요 !  : 하나의 step_index의 각 number 함수들마다 테스트데이터 생성 지침에 따라야합니다, number 1번만 잘 따르는 경향이 있습니다.

        # 중요 ! : 여기에 가장 중요한 검증과 관련된 자동화 코드 작성! test step, data, expected result를 바탕으로 완벽한 결과가 나와야함
  

  📋 생성 요구사항:
  중요 ! : 테스트케이스 구현할 때, Expected Result의 결과가 충족되도록 작성되어야합니다. Expected Result을 중복해서 만족할 필요는 없습니다
  0. 테스트케이스에 따른 검증이 가장 중요합니다. 테스트케이스를 할 수 있는 최대한으로 구현해주세요, 데이터 전략도 잘 준수하고 검증도 잘 챙겨주세요 제발
  1. 파일명: testCOMMONR_{{issue_key에서 추출한 숫자}}_{{step_index}}.py
    - 예: issue_key="COMMONR-12", step_index="1" → testCOMMONR_12_1.py
  2. 클래스명: testCOMMONR_{{issue_key에서 추출한 숫자}}_{{step_index}}(TestCOMMONR)
    - 예: testCOMMONR_12_1(TestCOMMONR)
  3. 함수명들: testCommonr_{{issue_key에서 추출한 숫자}}_{{step_index}}_N_{{scenario_description}}()
    - 예: testCommonr_12_1_1_general(), testCommonr_12_1_2_specific_case()
  중요 ! : 위의 파일,클래스,함수명 예시를 참고하되 예시를 아예 똑같이하면 안 됩니다.
  4. unittest를 이용한 검증
  5. docstring - 각 함수의 테스트 목적 명시
  6. 테스트케이스 내용을 기반으로 한 요구사항에 맞는 자동화 테스트 결과 생성, 테스트케이스의 test step, data, expected result가 완벽하게 충족되어야함
  7. 테스트케이스를 보고 skip할 수 있는 조건들은 묶어서 skip.test를 하도록 생성
  8. 외부 라이브러리나 모듈을 사용했다면 꼭 import란에 넣을 것
  9. pb2를 사용할거라면 꼭 function 내에 사용되어야합니다
  
  ⚠️ 필수 요구사항:
  - builder 클래스를 직접 import해서 사용하지말고 util.py를 활용하세요
  - 기존 GSDK testCOMMONR 패턴 완전히 준수
  - setUp/tearDown 메서드 생성하지 말 것
  - backup 사용하지 말 것
  - ServiceManager API를 통한 모든 디바이스 통신
  - 데이터 생성 전략을 잘 준수할 것
  - 코드의 정확도가 중요하므로 길게 생각해서 생성해주세요. 본인이 전문가라고 생각하고 코드가 완벽히 pass로 성공해야합니다.
  - 현재 검증 부분이 매우 부족하므로 테스트케이스를 할 수 있는 최대한으로 구현해서 검증할 것, 코드가 길어져도 됩니다.
  - 데이터 생성 전략과 검증 부분이 함께 잘 작성되어야함, 가끔 한쪽으로 치우칠 떄가 있음
  - 자동화 코드 파일의 내용 맨 위 상단에 # testCOMMONR_21_1.py 같은 거 생성해주지마세요 unittest 돌렸을 때 방해가됩니다.

  생성 계획을 참고하여 테스트 케이스의 테스트케이스의 test step, data, expected result가 완벽하게 충족되도록 완전한 testCOMMONR 스타일 테스트 코드를 생성해주세요
  시간이 오래 걸려도 괜찮습니다. think step by step
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
    user_feedback: str                      # 사용자 피드백 (재학습 선택 등)
    final_code: str                         # 최종 생성된 자동화 코드
    reasoning_process: str                  # 코드 생성 시 LLM의 추론 과정
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
            existing_knowledge = self.load_cached_knowledge()

            # 캐시가 없으면 CLAUDE.md만 사용 (analyze_test_case_coverage 내부에서 처리)
            knowledge_to_use = existing_knowledge if existing_knowledge else ""

            # 테스트케이스 분석 수행 (기존 지식과 함께)
            analysis_result = await self.analyze_test_case_coverage(test_case_info, knowledge_to_use)

            return {"test_case_analysis": analysis_result}

        except Exception as e:
            error_msg = f"analyze_testcase_node 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "test_case_analysis": "분석 중 오류 발생",
                "error": error_msg
            }
        

    async def compare_knowledge_node(self, state: GraphState) -> Dict[str, Any]:
        """기존 학습 내용과 요구사항 비교 노드 - ✅ 사용자 선택 기능 추가"""
        print("✅ current node : compare_knowledge_node")
        await cl.Message(content="**3. ⚖️ 학습 내용 vs 요구사항 비교 중...**").send()

        try:
            test_case_analysis = state.get("test_case_analysis", "")
            cached_knowledge = self.load_cached_knowledge()

            # ✅ 비교 수행
            comparison_result, llm_recommendation = await self.compare_knowledge_with_requirements(
                cached_knowledge if cached_knowledge else "",
                test_case_analysis
            )

            # ✅ 비교 결과를 사용자에게 명확하게 표시
            comparison_display = f"""## 📊 학습 내용 비교 결과

    {comparison_result}

    ---

    **LLM 권장사항:** {'🔄 재학습 권장' if llm_recommendation else '✅ 기존 학습 충분'}
    """
            await cl.Message(content=comparison_display).send()

            # ✅ 사용자 선택 대기
            if llm_recommendation:
                prompt_msg = "⚠️ **LLM이 재학습을 권장합니다.** 어떻게 하시겠습니까?"
            else:
                prompt_msg = "✅ **기존 학습으로 충분합니다.** 그래도 추가 학습하시겠습니까?"

            res = await cl.AskActionMessage(
                content=prompt_msg,
                actions=[
                    cl.Action(name="add_learning", value="yes", label="🔄 추가 학습 수행", payload={"relearn": True}),
                    cl.Action(name="skip", value="no", label="⏭️ 기존 지식으로 진행", payload={"relearn": False}),
                ],
                timeout=120
            ).send()

            # ✅ 디버깅: 응답 확인
            print(f"🔍 [디버깅] AskActionMessage 응답: {res}")
            
            # ✅ Chainlit 응답 파싱 수정
            if res:
                # name 필드로 판단
                user_choice = "yes" if res.get("name") == "add_learning" else "no"
            else:
                user_choice = "no"

            print(f"🔍 [디버깅] 사용자 선택: {user_choice}")

            # ✅ 사용자 선택 결과 표시
            if user_choice == "yes":
                await cl.Message(content="🔄 **추가 학습을 진행합니다.**").send()
            else:
                await cl.Message(content="⏭️ **기존 지식으로 코드 생성을 진행합니다.**").send()

            return {
                "cached_knowledge": cached_knowledge if cached_knowledge else "",
                "knowledge_comparison": comparison_result,
                "should_relearn": (user_choice == "yes")
            }

        except Exception as e:
            error_msg = f"compare_knowledge_node 오류: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "cached_knowledge": "",
                "knowledge_comparison": "비교 중 오류 발생",
                "should_relearn": False,
                "error": error_msg
            }

    async def user_feedback_node(self, state: GraphState) -> Dict[str, Any]:
        """사용자 피드백 노드 - 추가 학습 쿼리 입력"""
        print("✅ current node : user_feedback_node")

        should_relearn = state.get("should_relearn", False)
        
        # ✅ 디버깅
        print(f"🔍 [디버깅] should_relearn: {should_relearn}")

        if not should_relearn:
            # ✅ 메시지 제거 (compare_knowledge_node에서 이미 출력)
            return {"user_feedback": ""}

        # 사용자가 "추가 학습 수행" 선택 → 쿼리 입력받기
        await cl.Message(content="📝 **추가로 학습할 내용을 입력해주세요.**").send()

        query_res = await cl.AskUserMessage(
            content="**예시:**\n- 'door.proto와 door 관련 API 메서드 추가 학습'\n- 'schedule.proto와 Schedule 관련 모든 기능 학습'\n- 'APB Zone 관련 proto와 API 전체 학습'\n\n**입력:**",
            timeout=180
        ).send()

        if query_res and query_res.get("output", "").strip():
            user_query = query_res.get("output", "").strip()
            await cl.Message(content=f"✅ **추가 학습 내용:** {user_query}").send()

            return {"user_feedback": user_query}
        else:
            # 쿼리 입력 안 함 → 기존 지식으로 진행
            await cl.Message(content="⏭️ **입력 없음. 기존 학습 내용으로 진행합니다.**").send()
            return {"user_feedback": ""}
    
    
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
        cached_knowledge = self.load_cached_knowledge()
        
        if cached_knowledge:
            print("✅ [캐시] 기존 학습 내용 사용")
            await cl.Message(content="✅ **기존 학습 내용을 불러왔습니다.**").send()
            return {"cached_knowledge": cached_knowledge}
        
        # 캐시 없음 → 최초 학습
        print("🔄 [학습] 캐시 없음 - 프로젝트 최초 학습 시작")
        await cl.Message(content="**🔄 프로젝트 최초 학습 시작...**").send()
        
        # additional_query 없이 호출 (최초 학습)
        learned_knowledge = await self.learn_project_structure()
        
        return {"cached_knowledge": learned_knowledge}
    
    async def additional_learn_project_node(self, state: GraphState) -> Dict[str, Any]:
        """프로젝트 추가 학습 노드 - 캐시 확인 후 필요 시 학습"""
        print("✅ current node : additional_learn_project_node")
    
        # 추가 학습
        print("🔄 [추가 학습] - 프로젝트 추가 학습 시작")
        await cl.Message(content="**🔄 프로젝트 추가 학습 시작...**").send()
        
        user_feedback = state.get("user_feedback", [])
        if user_feedback:
            print(f"🔄 [재학습] 사용자 요청 반영: {user_feedback}")
            learned_knowledge = await self.learn_additional_content(additional_query=user_feedback)
            self.save_knowledge_to_cache(learned_knowledge)
            
        else :
            #피드백 없으면 기존 학습 데이터로 진행
            cached_knowledge = self.load_cached_knowledge()
            return {"cached_knowledge": cached_knowledge}

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
        """자동화코드 함수 검색 결과에 따라 다음 노드 결정"""
        print("✅ current node : retry_learn_project")
        user_feedback = state.get("user_feedback", [])
        if not user_feedback:
            return "generate_code"
        else:
            return "additional_learn"
    
    
    # 3. 그래프 빌드 메서드
    def _build_graph(self):
        workflow = StateGraph(GraphState)

        # 모든 노드들 추가
        workflow.add_node("learn_project", self.learn_project_node)
        workflow.add_node("retrieve_test_case", self.testcase_rag_node)
        workflow.add_node("analyze_testcase", self.analyze_testcase_node)
        workflow.add_node("compare_knowledge", self.compare_knowledge_node)
        workflow.add_node("user_feedback", self.user_feedback_node)
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
        # 3. 지식 비교 (캐시 파일 vs 테스트케이스 요구사항)
        workflow.add_edge("compare_knowledge", "user_feedback")
        # 4. 사용자 피드백 (추가 학습 쿼리 입력 또는 스킵)
        workflow.add_conditional_edges(
            "user_feedback",
            self.retry_learn_project,  # 조건 함수
            {
                "additional_learn": "additional_learn_project",  # 추가 학습 수행
                "generate_code": "generate_automation_code"      # 기존 지식으로 코드 생성
            }
        )
        workflow.add_edge("additional_learn_project", "generate_automation_code")
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
    
