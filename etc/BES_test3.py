from langgraph.graph import StateGraph, END
import chromadb
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun

# 6. typing 및 pathlib (변경 없음)
from typing import List, Dict, Any, Optional, Tuple, TypedDict, Annotated
from pathlib import Path
import json
import requests
import warnings
import datetime
import os
import re
import chainlit as cl

# FutureWarning 무시
warnings.filterwarnings("ignore", category=FutureWarning)

class GraphState(TypedDict, total=False):
    original_query: str                     # 사용자의 최초 질문
    test_case_info: List[Dict[str, Any]]    # 테스트케이스 RAG에서 찾은 정보

    # 리소스 탐색 결과
    resource_plan_text: str
    resource_plan: Dict[str, Any]

    # Phase 2: 기본 구조 생성 결과
    base_structure: str                     # 핵심 3파일 기반 기본 클래스 구조
    core_files_loaded: bool                 # 핵심 파일 로드 완료 여부

    # Phase 3: 카테고리별 상세 코드
    category_codes: Dict[str, Any]          # 카테고리별 상세 코드 딕셔너리

    # Phase 4: 통합 및 검증 결과
    final_code: str                         # 최종 통합된 코드
    coverage: int                           # 테스트케이스 커버리지 (%)
    validation_result: Dict[str, Any]       # 검증 결과 상세
    needs_refinement: bool                  # 재생성 필요 여부

    # 코드 생성 결과 (최종)
    generated_plan: str
    generated_code: str
    artifact_info: Dict[str, str]
    file_path: str

    # 오류
    error: str


class LMStudioLLM(LLM):
    """LM Studio와 연동하는 LangChain 호환 LLM 클래스"""
    
    base_url: str = "http://127.0.0.1:1234/v1"
    model_name: str = "qwen/qwen3-8b"
    temperature: float = 0.1
    max_tokens: int = 8192  # 자동화 코드 생성을 위해 토큰 수 증가
    
    def __init__(self, 
                 base_url: str = "http://127.0.0.1:1234/v1",
                 model_name: str = "qwen/qwen3-8b",
                 temperature: float = 0.1,
                 max_tokens: int = 8192,
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
                error_detail = response.text[:500]  # 에러 상세 정보
                print(f"❌ LM Studio 400 에러 상세:\n{error_detail}")
                return f"Error: LM Studio 응답 오류 (status: {response.status_code})\n상세: {error_detail}"

        except Exception as e:
            return f"Error: LM Studio 통신 오류 - {str(e)}"

class RAG_Pipeline :
    """
    Vector DB, Embedding Model, LM Studio를 연결하여 RAG를 수행하는 클래스.
    """

    def __init__(self,
                testcase_db_path="/Users/admin/Documents/2025_project/QE_RAG_COMPANY/QE_RAG_2025/chroma_db",           # 테스트케이스 DB 폴더
                testcase_collection_name="jira_test_cases",        # 테스트케이스 컬렉션명
                testcase_embedding_model="intfloat/multilingual-e5-large",        # 테스트케이스용 임베딩 모델
                lm_studio_url: str = "http://127.0.0.1:1234/v1",
                lm_studio_model: str = "qwen/qwen3-8b"
                ):
        
        self.testcase_db_path = testcase_db_path
        self.testcase_collection_name = testcase_collection_name
        self.testcase_embedding_model = testcase_embedding_model
        self.lm_studio_url = lm_studio_url
        self.lm_studio_model = lm_studio_model
        
        self.llm = LMStudioLLM(
            base_url=lm_studio_url,
            model_name=lm_studio_model,
            temperature=0.1,
            max_tokens=8192  # 자동화 코드 생성을 위해 토큰 수 증가
        )
    
        # 폴더 존재 확인
        self._check_db_directories()
        
        # 테스트케이스용 임베딩 모델 설정 (GPU 사용)
        print(f"🔧 테스트케이스용 임베딩 모델 로딩: {testcase_embedding_model}")
        testcase_model_kwargs = {'device': 'cpu', 'trust_remote_code': True}
        testcase_encode_kwargs = {'normalize_embeddings': True, 'batch_size': 4}
        
        self.testcase_embeddings = HuggingFaceEmbeddings(
            model_name=testcase_embedding_model,
            model_kwargs=testcase_model_kwargs,
            encode_kwargs=testcase_encode_kwargs
        )
        print(f"✅ 테스트케이스 임베딩 모델 로딩 완료")
        
        # 2개의 벡터 저장소 연결 (각각 다른 폴더와 다른 임베딩 모델)
        self.testcase_vectorstore = self._connect_to_chroma(
            self.testcase_db_path, 
            self.testcase_collection_name, 
            self.testcase_embeddings,
            "테스트케이스",
            testcase_embedding_model
        )

        # ✨ NEW: gsdk_rag_context 로딩
        print("\n📚 gsdk_rag_context 시스템 로딩 중...")
        self._load_gsdk_context()


    def _check_db_directories(self):
        """DB 디렉터리 존재 확인"""
        print("📁 ChromaDB 디렉터리 확인 중...")
        
        if not os.path.exists(self.testcase_db_path):
            print(f"⚠️ 테스트케이스 DB 디렉터리가 없습니다: {self.testcase_db_path}")
            print(f"   디렉터리를 생성하거나 올바른 경로를 지정해주세요.")
        else:
            print(f"✅ 테스트케이스 DB 디렉터리 확인: {self.testcase_db_path}")
        
    
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


    def _load_gsdk_context(self):
        """
        gsdk_rag_context 시스템 로딩
        - README.md: 자율적 탐색 프로세스 가이드
        - 3개 가이드 문서: WORKFLOW, REFERENCE, TEST_DATA
        - 3개 리소스 JSON: category_map, manager_api_index, event_codes
        """
        try:
            # 프로젝트 루트에서 gsdk_rag_context 폴더 찾기
            current_dir = Path(__file__).parent
            project_root = current_dir.parent
            gsdk_context_dir = project_root / "gsdk_rag_context"

            if not gsdk_context_dir.exists():
                print(f"⚠️ gsdk_rag_context 폴더를 찾을 수 없습니다: {gsdk_context_dir}")
                print(f"   기본 프롬프트를 사용합니다.")
                self.guides = {}
                self.resources = {}
                return

            # 가이드 문서 로드
            self.guides = {
                'readme': self._read_file(gsdk_context_dir / "README.md"),
                'workflow': self._read_file(gsdk_context_dir / "01_WORKFLOW_GUIDE.md"),
                'reference': self._read_file(gsdk_context_dir / "02_REFERENCE_GUIDE.md"),
                'test_data': self._read_file(gsdk_context_dir / "03_TEST_DATA_GUIDE.md"),
            }

            # 리소스 JSON 로드
            resources_dir = gsdk_context_dir / "resources"
            self.resources = {
                'category_map': self._read_json(resources_dir / "category_map.json"),
                'manager_api': self._read_json(resources_dir / "manager_api_index.json"),
                'event_codes': self._read_json(resources_dir / "event_codes.json"),
            }

            # 로딩 성공 메시지
            print(f"✅ gsdk_rag_context 로딩 완료")
            print(f"   📖 가이드 문서: {len(self.guides)}개")
            print(f"   📦 리소스 파일: {len(self.resources)}개")
            print(f"   🏷️  카테고리: {len(self.resources.get('category_map', {}).get('categories', []))}개")

        except Exception as e:
            print(f"⚠️ gsdk_rag_context 로딩 중 오류: {e}")
            print(f"   기본 프롬프트를 사용합니다.")
            self.guides = {}
            self.resources = {}


    def _read_file(self, file_path: Path) -> str:
        """파일 읽기 헬퍼"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"   ✓ {file_path.name} 로드 완료")
            return content
        except Exception as e:
            print(f"   ✗ {file_path.name} 로드 실패: {e}")
            return ""


    def _read_json(self, file_path: Path) -> dict:
        """JSON 파일 읽기 헬퍼"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"   ✓ {file_path.name} 로드 완료")
            return data
        except Exception as e:
            print(f"   ✗ {file_path.name} 로드 실패: {e}")
            return {}


    def _extract_keywords(self, text: str) -> List[str]:
        """
        텍스트에서 키워드 추출
        - 영문 키워드 (소문자)
        - 한글 키워드 (원본)
        """
        # 영문 키워드 추출 (알파벳만)
        english_keywords = re.findall(r'\b[a-zA-Z]+\b', text.lower())

        # 한글 키워드 추출 (한글만)
        korean_keywords = re.findall(r'[가-힣]+', text)

        # 중복 제거 및 결합
        all_keywords = list(set(english_keywords + korean_keywords))

        return all_keywords

    # ------------------------------------------------------------------
    # 리소스 도우미 (LLM이 선택한 항목을 실데이터로 변환)
    # ------------------------------------------------------------------

    def _get_category_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        if not name or not self.resources.get('category_map'):
            return None

        target = name.strip().lower()
        for cat in self.resources['category_map'].get('categories', []):
            if cat.get('name', '').lower() == target:
                return cat

        # 부분 일치도 허용
        for cat in self.resources['category_map'].get('categories', []):
            if target in cat.get('name', '').lower():
                return cat
        return None

    async def resource_planner_node(self, state: GraphState) -> Dict[str, Any]:
        """LLM에게 리소스 선택을 맡기고 결과를 정리"""
        test_case_info = state.get("test_case_info", [])
        if not test_case_info:
            message = "⚠️ 테스트케이스가 없어 리소스 계획을 세울 수 없습니다."
            await cl.Message(content=message).send()
            return {"resource_plan_text": message, "resource_plan": {}, "selected_resources": {}}

        # 테스트케이스 텍스트와 키워드
        combined_text = "\n\n".join(tc.get("content", "") for tc in test_case_info)
        keywords = self._extract_keywords(combined_text)

        # 🆕 전체 리소스 데이터 준비 (샘플이 아닌 전체)
        # category_map.json 전체 (keywords, description, manager_methods 포함)
        category_map_full = json.dumps(
            self.resources.get("category_map", {}).get("categories", []),
            ensure_ascii=False,
            indent=2
        )

        # manager_api_index.json 전체 (너무 길면 잘라내기)
        manager_api_full = json.dumps(
            self.resources.get("manager_api", {}),
            ensure_ascii=False,
            indent=2
        )

        # event_codes 전체
        event_codes_full = json.dumps(
            self.resources.get("event_codes", {}).get("commonly_monitored_events", []),
            ensure_ascii=False,
            indent=2
        )

        resource_prompt = (
            f"당신은 30년 경력의 GSDK 자동화 전문가입니다. 아래 테스트케이스를 분석하여 **관련된 모든 리소스를 선택**하세요.\n\n"
            "## 🎯 중요 원칙\n\n"
            "- 테스트케이스와 **조금이라도 관련 있는** 모든 카테고리를 선택하세요\n"
            "- 각 카테고리의 keywords, description, manager_methods를 보고 관련성을 판단하세요\n"
            "- **불확실하면 포함**하는 것이 좋습니다 (나중에 Phase 2-3에서 필터링됨)\n"
            "- Manager API는 해당 카테고리의 manager_methods를 **모두** 포함하세요\n"
            "- Event codes는 테스트 검증에 필요한 모든 이벤트를 포함하세요\n"
            "- 충분히 많은 리소스를 선택하는 것이 코드 생성 품질을 높입니다\n\n"
            "---\n\n"
            "## 📋 테스트케이스\n\n"
            "\"\"\"\n"
            f"{combined_text}\n"
            "\"\"\"\n\n"
            f"**추출된 키워드**: {', '.join(keywords[:40])}\n\n"
            "---\n\n"
            "## 📚 사용 가능한 전체 카테고리 목록\n"
            "(각 카테고리의 keywords, description, manager_methods를 확인하여 관련성 판단)\n\n"
            "```json\n"
            f"{category_map_full}\n"
            "```\n\n"
            "---\n\n"
            "## 📋 Manager API 인덱스 (전체)\n\n"
            "```json\n"
            f"{manager_api_full}\n"
            "```\n\n"
            "---\n\n"
            "## 📋 감시 가능한 이벤트 목록 (전체)\n\n"
            "```json\n"
            f"{event_codes_full}\n"
            "```\n\n"
            "---\n\n"
            "## 🎯 출력 형식\n\n"
            "JSON 형식으로만 답변하세요. **관련된 모든 리소스를 충분히 포함**하세요.\n\n"
            "```json\n"
            "{{\n"
            "  \"categories\": [\"user\", \"auth\", \"card\", \"finger\"],\n"
            "  \"manager_methods\": [\"enrollUsers\", \"deleteUser\", \"setAuthConfig\", \"getAuthConfig\", \"verifyUser\"],\n"
            "  \"event_codes\": [\"EVENT_USER_ENROLLED\", \"EVENT_AUTH_SUCCESS\", \"EVENT_VERIFY_SUCCESS\"],\n"
            "  \"resource_files\": [\"demo/example/user/user.py\", \"demo/example/auth/auth.py\"],\n"
            "  \"notes\": \"user: 사용자 등록/삭제, auth: 인증 설정, card/finger: 검증 관련\"\n"
            "}}\n"
            "```\n\n"
            "**주의**: 설명 문장 없이 JSON만 출력하세요."
        )

        # 🔍 디버깅: 프롬프트 길이 출력
        prompt_length = len(resource_prompt)
        estimated_tokens = prompt_length // 4
        print(f"\n🔍 [DEBUG] resource_planner_node 프롬프트 통계:")
        print(f"   - 프롬프트 길이: {prompt_length:,} 글자")
        print(f"   - 예상 토큰: ~{estimated_tokens:,} 토큰")
        print(f"   - category_map_full 길이: {len(category_map_full):,} 글자")
        print(f"   - manager_api_full 길이: {len(manager_api_full):,} 글자")
        print(f"   - event_codes_full 길이: {len(event_codes_full):,} 글자")

        plan_text = await self.llm.ainvoke(resource_prompt)
        default_plan = {
            "categories": [],
            "manager_methods": [],
            "event_codes": [],
            "resource_files": [],
            "notes": ""
        }
        parsed_plan = self._safe_parse_json(plan_text, {"resource_plan": default_plan})
        resource_plan = parsed_plan.get("resource_plan", parsed_plan if parsed_plan != {} else default_plan)

        await cl.Message(
            content=f"✅ **리소스 계획 수립 완료**\n```json\n{json.dumps(resource_plan, ensure_ascii=False, indent=2)}\n```"
        ).send()

        return {
            "resource_plan_text": plan_text,
            "resource_plan": resource_plan
        }



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


    def _read_full_file(self, file_path: str, max_lines: int = None) -> str:
        """
        파일 전체를 읽어 문자열로 반환

        Args:
            file_path: 읽을 파일 경로 (프로젝트 루트 기준 상대 경로)
            max_lines: 최대 라인 수 (None이면 전체)

        Returns:
            파일 내용 (문자열)
        """
        try:
            project_root = Path(__file__).parent.parent
            full_path = project_root / file_path

            if not full_path.exists():
                print(f"   ⚠️ 파일을 찾을 수 없습니다: {file_path}")
                return f"# 파일 없음: {file_path}"

            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                if max_lines:
                    lines = []
                    for idx, line in enumerate(f):
                        if idx >= max_lines:
                            lines.append(f"... (생략: {max_lines}라인 초과)")
                            break
                        lines.append(line.rstrip('\n'))
                    content = '\n'.join(lines)
                else:
                    content = f.read()

            print(f"   ✓ {file_path} 로드 완료 ({len(content)} chars)")
            return content

        except Exception as e:
            print(f"   ✗ {file_path} 로드 실패: {e}")
            return f"# 파일 로드 실패: {file_path}\n# 오류: {e}"


    def _load_category_files_full(self, category_name: str) -> Dict[str, str]:
        """
        카테고리의 모든 관련 파일을 통째로 로드

        Args:
            category_name: 카테고리 이름 (예: "user", "auth", "finger")

        Returns:
            Dict[파일타입, 파일내용] - {"example": "...", "pb2": "...", "proto": "..."}
        """
        files = {}

        # category_map.json에서 파일 경로 조회
        category_info = self._get_category_by_name(category_name)
        if not category_info:
            print(f"   ⚠️ 카테고리를 찾을 수 없습니다: {category_name}")
            return files

        print(f"\n📂 카테고리 '{category_name}' 파일 로드 중...")

        # example 파일
        example_file = category_info.get("example_file")
        if example_file:
            files['example'] = self._read_full_file(example_file)

        # pb2 파일
        pb2_file = category_info.get("pb2_file")
        if pb2_file:
            files['pb2'] = self._read_full_file(pb2_file)

        # proto 파일
        proto_file = category_info.get("proto_file")
        if proto_file:
            files['proto'] = self._read_full_file(proto_file)

        # pb2_grpc 파일 (선택적)
        pb2_grpc_file = category_info.get("pb2_grpc_file")
        if pb2_grpc_file:
            files['pb2_grpc'] = self._read_full_file(pb2_grpc_file)

        print(f"   ✅ 카테고리 '{category_name}' 파일 {len(files)}개 로드 완료")
        return files


    def _extract_guide_section(self, guide_text: str, section_marker: str) -> str:
        """
        가이드 문서에서 특정 섹션만 추출

        Args:
            guide_text: 전체 가이드 문서
            section_marker: 섹션 시작 마커 (예: "### 3.1 user 카테고리")

        Returns:
            해당 섹션 내용 (다음 섹션 전까지)
        """
        import re

        if not guide_text or not section_marker:
            return ""

        # section_marker 이후부터 다음 ### 전까지 추출
        pattern = rf"{re.escape(section_marker)}(.*?)(?=\n### |\Z)"
        match = re.search(pattern, guide_text, re.DOTALL | re.MULTILINE)

        if match:
            return match.group(1).strip()

        # 정확한 매칭 실패 시 유사 검색
        pattern_loose = rf".*{re.escape(section_marker.split()[-1])}.*\n(.*?)(?=\n### |\Z)"
        match = re.search(pattern_loose, guide_text, re.DOTALL | re.MULTILINE)

        if match:
            return match.group(1).strip()

        return ""


    def _get_relevant_guide_sections(self, guide_type: str, categories: List[str]) -> str:
        """
        카테고리 리스트 기반으로 관련 가이드 섹션 추출

        Args:
            guide_type: 'reference' 또는 'test_data'
            categories: 카테고리 이름 리스트 (예: ['user', 'auth', 'finger'])

        Returns:
            관련 섹션들을 결합한 문자열
        """
        guide_text = self.guides.get(guide_type, '')
        if not guide_text or not categories:
            return ""

        sections = []

        for category_name in categories:
            # REFERENCE_GUIDE 섹션 추출
            if guide_type == 'reference':
                # "### 3.X {category} 카테고리" 형식 검색
                section = self._extract_guide_section(
                    guide_text,
                    f"카테고리"
                )
                if section and category_name in section.lower():
                    sections.append(f"## {category_name.upper()} 카테고리\n\n{section}")

            # TEST_DATA_GUIDE 섹션 추출
            elif guide_type == 'test_data':
                # **Category**: `{category}` 형식 검색
                lines = guide_text.split('\n')
                in_section = False
                category_section = []

                for i, line in enumerate(lines):
                    if f'**Category**: `{category_name}`' in line:
                        in_section = True
                        category_section = [line]
                    elif in_section:
                        if line.startswith('**Category**:') and category_name not in line:
                            break
                        category_section.append(line)
                        if i >= len(lines) - 1:
                            break

                if category_section:
                    sections.append(f"## {category_name.upper()} 데이터 패턴\n\n" + '\n'.join(category_section))

        if not sections:
            # 섹션을 찾지 못한 경우 가이드 전체의 일부 반환
            return guide_text[:5000] + "\n... (생략)"

        return "\n\n---\n\n".join(sections)


    def _extract_category_patterns(self, test_data_guide: str, category_name: str) -> str:
        """
        TEST_DATA_GUIDE에서 특정 카테고리의 데이터 생성 패턴 추출

        Args:
            test_data_guide: TEST_DATA_GUIDE 전체 텍스트
            category_name: 카테고리 이름 (예: 'user', 'auth')

        Returns:
            해당 카테고리 관련 패턴 섹션
        """
        if not test_data_guide:
            return ""

        # "**Category**: `{category}`" 또는 섹션 제목으로 검색
        lines = test_data_guide.split('\n')
        patterns = []
        in_relevant_section = False
        section_lines = []

        for i, line in enumerate(lines):
            # 카테고리 태그 발견
            if f'**Category**: `{category_name}`' in line or f'`{category_name}`' in line.lower():
                in_relevant_section = True
                section_lines = [line]
            elif in_relevant_section:
                # 다음 섹션 시작 (##로 시작) 또는 다른 카테고리 발견
                if line.startswith('## ') or (line.startswith('**Category**:') and category_name not in line):
                    patterns.append('\n'.join(section_lines))
                    section_lines = []
                    in_relevant_section = False
                else:
                    section_lines.append(line)

        # 마지막 섹션 추가
        if section_lines:
            patterns.append('\n'.join(section_lines))

        if patterns:
            return "\n\n".join(patterns)

        return f"(카테고리 '{category_name}'에 대한 데이터 패턴을 찾을 수 없습니다.)"



    async def testcase_rag_node(self, state: GraphState) -> Dict[str, Any]:
        """테스트 케이스 검색 노드"""
        await cl.Message(content=" **1. 🔍 테스트케이스 검색 시작...**").send()
        query = state['original_query']
        # 상속받은 retrieve_test_case 메서드 호출
        results = await self.retrieve_test_case(query)
        #chainlit에 실시간 결과값 표시
        await cl.Message(content=f"✅ **테스트케이스 검색 완료** \n```json\n{json.dumps(results, ensure_ascii=False, indent=2, default=str)}\n```").send()
        return {"test_case_info": results}


    async def base_structure_node(self, state: GraphState) -> Dict[str, Any]:
        """
        Phase 2: 핵심 3파일(manager.py, testCOMMONR.py, util.py)을 통째로 넣고
        테스트 클래스의 기본 구조를 생성
        """
        print("\n" + "="*80)
        print("🏗️ Phase 2: 기본 구조 생성 (핵심 3파일 통째로)")
        print("="*80)

        test_case_info = state.get("test_case_info", [])
        resource_plan = state.get("resource_plan", {})

        if not test_case_info:
            error_msg = "⚠️ 테스트케이스가 없어 기본 구조를 생성할 수 없습니다."
            await cl.Message(content=error_msg).send()
            return {"base_structure": "", "core_files_loaded": False, "error": error_msg}

        await cl.Message(content="🏗️ **Phase 2: 기본 구조 생성 중...**\n- manager.py, testCOMMONR.py, util.py 로딩\n- 테스트 클래스 골격 생성").send()

        # 핵심 3파일 통째로 로드
        print("\n📚 핵심 3파일 로딩 중...")
        manager_full = self._read_full_file("demo/demo/manager.py")
        testCOMMONR_full = self._read_full_file("demo/demo/test/testCOMMONR.py")
        util_full = self._read_full_file("demo/demo/test/util.py")

        # 가이드 문서
        workflow_guide = self.guides.get('workflow', '')

        # 🆕 카테고리 기반 관련 가이드 섹션 추출
        categories = resource_plan.get('categories', [])
        reference_sections = self._get_relevant_guide_sections('reference', categories)
        test_data_sections = self._get_relevant_guide_sections('test_data', categories)

        # 🆕 Manager API 인덱스 (함수 검증용)
        manager_api_index = json.dumps(
            self.resources.get('manager_api', {}),
            ensure_ascii=False,
            indent=2
        )

        # 테스트케이스 내용 구성
        test_case_bundle = "\n\n".join([
            f"### 테스트케이스 #{i+1}\n"
            f"내용:\n{tc.get('content', '')}\n\n"
            f"메타데이터:\n```json\n{json.dumps(tc.get('metadata', {}), ensure_ascii=False, indent=2)}\n```"
            for i, tc in enumerate(test_case_info)
        ])

        # 프롬프트 구성
        prompt = f"""# G-SDK 테스트 자동화 코드 생성 - Phase 2: 기본 구조

당신은 30년 경력의 GSDK Python 테스트 전문가입니다.
아래 테스트케이스를 바탕으로 **테스트 클래스의 기본 구조**를 생성하세요.

---

## 📋 테스트케이스

{test_case_bundle}

---

## 🎯 리소스 계획

```json
{json.dumps(resource_plan, ensure_ascii=False, indent=2)}
```

---

## 📚 참조 코드 (통째로 제공 - 실제 메서드만 사용할 것)

### manager.py (전체)
```python
{manager_full}
```

### testCOMMONR.py (전체)
```python
{testCOMMONR_full}
```

### util.py (전체)
```python
{util_full}
```

---

## 📖 WORKFLOW 가이드 (작업 흐름)

{workflow_guide}

---

## 📖 REFERENCE 가이드 (API 레퍼런스 - 관련 카테고리)

{reference_sections}

---

## 📖 TEST_DATA 가이드 (데이터 생성 패턴 - 관련 카테고리)

{test_data_sections}

---

## 📋 Manager API 인덱스 (함수 검증용)

```json
{manager_api_index}
```

---

## 🎯 생성할 것

1. **Import 문**
   - 필요한 pb2 모듈 (resource_plan의 카테고리 기반)
   - manager, util, testCOMMONR
   - unittest, time, random, os, json 등

2. **클래스 정의**
   - TestCOMMONR 상속
   - Docstring (테스트 시나리오 설명)

3. **setUp/tearDown**
   - super().setUp(), super().tearDown() 호출
   - 추가 백업/복원이 필요한 경우만 작성

4. **테스트 메서드 골격**
   - 각 테스트 스텝별 TODO 주석
   - 메서드 이름: testCommonr_{{번호}}_{{서브번호}}_{{기능명}}

5. **기본 코드 뼈대**
   - 사용자 데이터 로드 패턴 (JSON → UserInfo)
   - 디바이스 능력 검증 (skipTest 사용)

## ⚠️ 중요 제약사항

1. **실제 존재하는 메서드만 사용**:
   - manager.py, testCOMMONR.py, util.py에 실제로 정의된 함수만 사용
   - 존재하지 않는 헬퍼 메서드는 절대 만들지 말 것

2. **정확한 시그니처 사용**:
   - EventMonitor(svcManager, masterID, eventCode=0x..., userID=...)
   - randomNumericUserID(), generateRandomPIN()
   - self.svcManager.enrollUsers(), self.svcManager.getAuthConfig() 등

3. **Phase 2에서는 기본 구조만**:
   - 상세 구현은 Phase 3(카테고리별 처리)에서 진행
   - 지금은 클래스 뼈대 + TODO 주석만

## 출력 형식

순수 Python 코드만 출력 (마크다운 블록 ```python 없이)
"""

        print("\n⚙️ LLM 호출 중... (기본 구조 생성)")
        base_structure = await self.llm.ainvoke(prompt)

        # 마크다운 코드 블록 제거
        base_structure = self._clean_generated_code(base_structure)

        print(f"\n✅ 기본 구조 생성 완료 ({len(base_structure)} chars)")
        await cl.Message(content="✅ **기본 구조 생성 완료**\n- Import 문, 클래스 정의, setUp/tearDown, 테스트 메서드 골격 생성됨").send()

        return {
            "base_structure": base_structure,
            "core_files_loaded": True
        }


    async def category_processor_node(self, state: GraphState) -> Dict[str, Any]:
        """
        Phase 3: 카테고리별로 example, pb2, proto 파일을 통째로 넣고
        상세 코드를 순차적으로 생성
        """
        print("\n" + "="*80)
        print("🔧 Phase 3: 카테고리별 상세 코드 생성")
        print("="*80)

        resource_plan = state.get("resource_plan", {})
        base_structure = state.get("base_structure", "")
        test_case_info = state.get("test_case_info", [])

        categories = resource_plan.get("categories", [])

        if not categories:
            print("   ⚠️ 카테고리가 없어 상세 코드 생성을 건너뜁니다.")
            return {"category_codes": {}}

        await cl.Message(content=f"🔧 **Phase 3: 카테고리별 상세 코드 생성 중...**\n- 총 {len(categories)}개 카테고리 처리 예정").send()

        category_codes = {}

        for idx, category_name in enumerate(categories, 1):
            print(f"\n📦 [{idx}/{len(categories)}] 카테고리 '{category_name}' 처리 중...")
            await cl.Message(content=f"📦 **[{idx}/{len(categories)}]** 카테고리 '{category_name}' 분석 중...").send()

            # 카테고리별 파일 통째로 로드
            category_files = self._load_category_files_full(category_name)

            if not category_files:
                print(f"   ⚠️ 카테고리 '{category_name}' 파일 로드 실패, 건너뜀")
                continue

            # LLM 호출하여 카테고리별 코드 생성
            category_code = await self._generate_category_code(
                category_name=category_name,
                category_files=category_files,
                base_structure=base_structure,
                test_case_info=test_case_info,
                resource_plan=resource_plan
            )

            category_codes[category_name] = category_code
            await cl.Message(content=f"✅ 카테고리 '{category_name}' 처리 완료").send()

        print(f"\n✅ 전체 {len(category_codes)}개 카테고리 처리 완료")
        return {"category_codes": category_codes}


    async def _generate_category_code(
        self,
        category_name: str,
        category_files: Dict[str, str],
        base_structure: str,
        test_case_info: List[Dict],
        resource_plan: Dict
    ) -> Dict[str, Any]:
        """
        특정 카테고리에 대한 상세 코드 생성
        """
        test_case_bundle = "\n\n".join([
            f"### 테스트케이스 #{i+1}\n{tc.get('content', '')}"
            for i, tc in enumerate(test_case_info)
        ])

        # 🆕 category_map.json에서 메타데이터 추출
        category_info = self._get_category_by_name(category_name)
        keywords = category_info.get('keywords', []) if category_info else []
        description = category_info.get('description', '') if category_info else ''
        manager_methods = category_info.get('manager_methods', []) if category_info else []

        # 🆕 REFERENCE 가이드에서 해당 카테고리 섹션 추출
        reference_guide = self.guides.get('reference', '')
        reference_section = self._extract_category_patterns(reference_guide, category_name)

        # 🆕 TEST_DATA 가이드에서 해당 카테고리 패턴 추출
        test_data_guide = self.guides.get('test_data', '')
        test_data_patterns = self._extract_category_patterns(test_data_guide, category_name)

        prompt = f"""# G-SDK 테스트 자동화 - Phase 3: {category_name.upper()} 카테고리 상세 코드

당신은 GSDK {category_name} 카테고리 전문가입니다.
아래 기본 구조에 **{category_name} 관련 상세 코드**를 추가하세요.

---

## 📋 테스트케이스 ({category_name} 관련 부분)

{test_case_bundle}

---

## 🏗️ 기본 구조 (Phase 2에서 생성됨)

```python
{base_structure}
... (생략)
```

---

## 📋 {category_name.upper()} 카테고리 메타데이터

**키워드**: {', '.join(keywords) if keywords else '없음'}
**설명**: {description if description else '설명 없음'}
**Manager 메서드**: {', '.join(manager_methods) if manager_methods else '없음'}

---

## 📖 REFERENCE 가이드 ({category_name} 카테고리 API 사용법)

{reference_section if reference_section else '# 관련 섹션 없음'}

---

## 📖 TEST_DATA 가이드 ({category_name} 데이터 생성 패턴)

{test_data_patterns if test_data_patterns else '# 관련 패턴 없음'}

---

## 📚 {category_name.upper()} 카테고리 참조 파일 (통째로)

### example/{category_name}/{category_name}.py
```python
{category_files.get('example', '# 파일 없음')}
... (너무 길면 생략)
```

### {category_name}_pb2.py
```python
{category_files.get('pb2', '# 파일 없음')}
... (너무 길면 생략)
```

### {category_name}.proto
```protobuf
{category_files.get('proto', '# 파일 없음')}
---

## 🎯 생성할 것

1. **Import 추가 여부**:
   - {category_name}_pb2 import가 필요한지 판단
   - 필요하면 추가할 import 문 제시

2. **{category_name} 관련 설정 코드**:
   - 예: AuthConfig 설정 (auth), FingerprintConfig 설정 (finger)

3. **{category_name} 관련 데이터 생성**:
   - 예: UserInfo 생성 (user), CardData 생성 (card)

4. **{category_name} 관련 API 호출**:
   - manager.py의 메서드 사용 (예: enrollUsers, setAuthConfig)

5. **{category_name} 관련 검증**:
   - assertEqual, assertTrue 등

## 출력 형식

JSON 형식으로 답변 (마크다운 블록 없이):
{{
  "imports": ["import {category_name}_pb2"],
  "setup_code": "# {category_name} 설정 코드\\n...",
  "test_code": "# {category_name} 테스트 코드\\n...",
  "assertions": "# {category_name} 검증 코드\\n..."
}}
"""

        print(f"   ⚙️ LLM 호출 중... (카테고리: {category_name})")
        result = await self.llm.ainvoke(prompt)

        # JSON 파싱
        parsed = self._safe_parse_json(result, {
            "imports": [],
            "setup_code": "",
            "test_code": "",
            "assertions": ""
        })

        print(f"   ✓ 카테고리 '{category_name}' 코드 생성 완료")
        return parsed


    async def merge_validate_node(self, state: GraphState) -> Dict[str, Any]:
        """
        Phase 4: Phase 2 기본 구조 + Phase 3 카테고리별 코드 → 최종 통합
        테스트케이스 100% 커버리지 검증
        """
        print("\n" + "="*80)
        print("🔍 Phase 4: 코드 통합 및 검증")
        print("="*80)

        base_structure = state.get("base_structure", "")
        category_codes = state.get("category_codes", {})
        test_case_info = state.get("test_case_info", [])

        await cl.Message(content="🔍 **Phase 4: 코드 통합 및 검증 중...**\n- 기본 구조 + 카테고리별 코드 병합\n- 커버리지 분석").send()

        # 테스트케이스 내용 구성
        test_case_bundle = "\n\n".join([
            f"### 테스트케이스 #{i+1}\n{tc.get('content', '')}"
            for i, tc in enumerate(test_case_info)
        ])

        # 카테고리별 코드 요약
        category_summary = json.dumps(category_codes, ensure_ascii=False, indent=2)

        prompt = f"""# G-SDK 테스트 자동화 - Phase 4: 최종 코드 통합

당신은 코드 통합 및 검증 전문가입니다.
Phase 2 기본 구조와 Phase 3 카테고리별 코드를 **완벽하게 병합**하세요.

---

## 🏗️ 기본 구조 (Phase 2)

```python
{base_structure}
```

---

## 🔧 카테고리별 상세 코드 (Phase 3)

```json
{category_summary}
```

---

## 📋 테스트케이스 (커버리지 검증용)

{test_case_bundle}

---

## 📋 Manager API 인덱스 (함수 검증용)

```json
{json.dumps(self.resources.get('manager_api', {{}}), ensure_ascii=False, indent=2)[:5000]}
```

**사용법**: 코드에서 `self.svcManager.XXX()` 호출 시 위 인덱스에 해당 메서드가 존재하는지 확인하세요.

---

## 📋 Event Codes (이벤트 검증용)

```json
{json.dumps(self.resources.get('event_codes', {{}}), ensure_ascii=False, indent=2)[:3000]}
```

**사용법**: EventMonitor에서 사용할 이벤트 코드를 위 목록에서 선택하세요. (예: BS2_EVENT_VERIFY_SUCCESS = 0x1000)

---

## 🎯 할 일

1. **Import 문 통합**:
   - 기본 구조의 import + 각 카테고리의 imports
   - 중복 제거

2. **코드 병합**:
   - setUp 메서드: 기본 구조 + 각 카테고리 setup_code
   - 테스트 메서드: TODO 주석 → 실제 구현 (category test_code)
   - 검증 코드: assertions 추가

3. **커버리지 검증**:
   - 모든 테스트 스텝이 구현되었는가?
   - 각 스텝이 올바른 API를 호출하는가?
   - EventMonitor 등 검증 로직이 있는가?

4. **함수 존재 확인 (CRITICAL)**:
   - self.svcManager.XXX() → 위 Manager API 인덱스에 존재하는 메서드만 사용
   - self.setXXXAuthMode() → testCOMMONR.py에 존재하는 헬퍼만 사용
   - util.XXX() → util.py에 존재하는 함수만 사용
   - **존재하지 않는 함수를 사용하면 invalid_functions 배열에 추가하고 needs_refinement=true로 설정**

5. **이벤트 검증 확인**:
   - EventMonitor를 사용하는 경우, eventCode가 위 Event Codes 목록에 존재하는지 확인
   - 존재하지 않는 이벤트 코드 사용 시 invalid_functions에 추가

## 출력 형식

JSON 형식으로 답변:
{{
  "final_code": "완성된 Python 코드 전체",
  "coverage_percentage": 95,
  "missing_steps": ["스텝 3-2: 얼굴 인증 검증 누락"],
  "invalid_functions": ["self.setCardAuthMode (존재하지 않음)"],
  "needs_refinement": false,
  "notes": "추가 설명..."
}}
"""

        print("\n⚙️ LLM 호출 중... (코드 통합 및 검증)")
        result = await self.llm.ainvoke(prompt)

        # JSON 파싱
        parsed = self._safe_parse_json(result, {
            "final_code": base_structure,
            "coverage_percentage": 0,
            "missing_steps": [],
            "invalid_functions": [],
            "needs_refinement": True,
            "notes": ""
        })

        final_code = parsed.get("final_code", base_structure)
        coverage = parsed.get("coverage_percentage", 0)
        needs_refinement = parsed.get("needs_refinement", False)

        print(f"\n✅ 코드 통합 완료 (커버리지: {coverage}%)")

        coverage_emoji = "✅" if coverage >= 90 else "⚠️" if coverage >= 70 else "❌"
        await cl.Message(content=f"{coverage_emoji} **코드 통합 완료**\n- 커버리지: {coverage}%\n- 재생성 필요: {'예' if needs_refinement else '아니오'}").send()

        return {
            "final_code": final_code,
            "generated_code": final_code,  # 기존 호환성
            "coverage": coverage,
            "validation_result": parsed,
            "needs_refinement": needs_refinement
        }


    async def refine_node(self, state: GraphState) -> Dict[str, Any]:
        """
        Phase 5: 검증 실패 시 부족한 부분 재생성
        """
        print("\n" + "="*80)
        print("🔄 Phase 5: 코드 재생성 (검증 실패 항목 수정)")
        print("="*80)

        validation_result = state.get("validation_result", {})
        final_code = state.get("final_code", "")
        test_case_info = state.get("test_case_info", [])

        await cl.Message(content="🔄 **Phase 5: 코드 재생성 중...**\n- 검증 실패 항목 수정").send()

        missing_steps = validation_result.get("missing_steps", [])
        invalid_functions = validation_result.get("invalid_functions", [])

        prompt = f"""# G-SDK 테스트 자동화 - Phase 5: 코드 재생성

이전 코드에 문제가 발견되었습니다. 수정하세요.

---

## 🔍 검증 결과

```json
{json.dumps(validation_result, ensure_ascii=False, indent=2)}
```

---

## 📄 현재 코드

```python
{final_code}
```

---

## 🎯 수정 사항

1. **누락된 스텝 추가**:
{chr(10).join(f'   - {step}' for step in missing_steps) if missing_steps else '   (없음)'}

2. **존재하지 않는 함수 교체**:
{chr(10).join(f'   - {func}' for func in invalid_functions) if invalid_functions else '   (없음)'}

3. **대체 방법 찾기**:
   - manager.py, testCOMMONR.py, util.py에서 유사한 함수 찾기
   - 직접 구현 가능한 경우 간단한 코드로 대체

## 출력 형식

JSON 형식으로 답변:
{{
  "final_code": "수정된 완전한 코드",
  "coverage_percentage": 100,
  "needs_refinement": false
}}
"""

        print("\n⚙️ LLM 호출 중... (코드 재생성)")
        result = await self.llm.ainvoke(prompt)

        parsed = self._safe_parse_json(result, {
            "final_code": final_code,
            "coverage_percentage": state.get("coverage", 0),
            "needs_refinement": False
        })

        refined_code = parsed.get("final_code", final_code)
        coverage = parsed.get("coverage_percentage", 0)

        print(f"\n✅ 코드 재생성 완료 (커버리지: {coverage}%)")
        await cl.Message(content=f"✅ **코드 재생성 완료**\n- 최종 커버리지: {coverage}%").send()

        return {
            "final_code": refined_code,
            "generated_code": refined_code,
            "coverage": coverage,
            "needs_refinement": False
        }


class RAG_Graph(RAG_Function):
    def __init__(self, **kwargs):
        """
        RAG_Graph 초기화
        부모 클래스(RAG_Function) 초기화 후 LangGraph 빌드
        """
        # 부모 클래스 초기화 (VectorDB, LLM 등)
        super().__init__(**kwargs)

        # LangGraph 빌드 및 초기화
        self.graph = self._build_graph()

        print("✅ RAG_Graph 초기화 완료 (LangGraph 빌드 완료)")

    def _derive_artifact_info(self, query: str, state: GraphState) -> Dict[str, str]:
        """파일 저장을 위한 메타 정보 구성"""
        issue_key = "UNKNOWN"
        step_hint = "all"

        metadata_source = None
        test_case_info = state.get("test_case_info") or []
        if test_case_info:
            metadata_source = test_case_info[0].get("metadata", {})
        else:
            metadata_source = {}

        if metadata_source:
            issue_key = metadata_source.get("issue_key", issue_key)
            step_hint = metadata_source.get("step_index", step_hint)

        if issue_key == "UNKNOWN":
            import re
            match = re.search(r'(COMMONR-\d+)', query)
            if match:
                issue_key = match.group(1)
        if step_hint == "all" and issue_key != "UNKNOWN":
            import re
            match = re.search(r'스텝\s*(\d+)', query)
            if match:
                step_hint = match.group(1)

        return {
            "issue_key": issue_key,
            "step_hint": str(step_hint),
        }

    def _clean_generated_code(self, code: str) -> str:
        """Markdown 코드 블록을 제거하고 양끝 공백 정리"""
        import re

        cleaned = re.sub(r'^```python\s*\n', '', code.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r'```$', '', cleaned.strip())
        return cleaned.strip()

    def _persist_generated_code(self, code: str, artifact: Dict[str, str]) -> str:
        """생성된 코드를 파일로 저장하고 경로 반환"""
        output_dir = Path(__file__).parent.parent / "generated_codes"
        output_dir.mkdir(exist_ok=True)

        issue_key = artifact.get("issue_key", "UNKNOWN")
        issue_number = issue_key.split('-')[-1] if '-' in issue_key else issue_key
        step_hint = artifact.get("step_hint", "all")
        filename = f"testCOMMONR_{issue_number}_{step_hint}.py"
        file_path = output_dir / filename

        cleaned_code = self._clean_generated_code(code)
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(cleaned_code)

        print(f"✅ 코드 파일 저장: {file_path}")
        return str(file_path)

    def _build_graph(self):
        """
        새로운 Phase 구조로 Graph 구성:
        Phase 0: retrieve_test_case
        Phase 1: plan_resources
        Phase 2: generate_base_structure (핵심 3파일 통째로)
        Phase 3: process_categories (카테고리별 순차 처리)
        Phase 4: merge_and_validate (통합 + 검증)
        Phase 5: refine_final (필요시)
        """
        workflow = StateGraph(GraphState)

        # 모든 노드들 추가
        workflow.add_node("retrieve_test_case", self.testcase_rag_node)
        workflow.add_node("plan_resources", self.resource_planner_node)

        # 새로운 Phase 2-5 노드
        workflow.add_node("generate_base_structure", self.base_structure_node)
        workflow.add_node("process_categories", self.category_processor_node)
        workflow.add_node("merge_and_validate", self.merge_validate_node)
        workflow.add_node("refine_final", self.refine_node)

        # 진입 노드 설정
        workflow.set_entry_point("retrieve_test_case")

        # 그래프 플로우 (순차)
        workflow.add_edge("retrieve_test_case", "plan_resources")
        workflow.add_edge("plan_resources", "generate_base_structure")
        workflow.add_edge("generate_base_structure", "process_categories")
        workflow.add_edge("process_categories", "merge_and_validate")

        # 조건부 분기: needs_refinement에 따라
        workflow.add_conditional_edges(
            "merge_and_validate",
            lambda state: "refine" if state.get("needs_refinement", False) else "end",
            {
                "refine": "refine_final",
                "end": END
            }
        )

        workflow.add_edge("refine_final", END)

        return workflow.compile()

    async def run_graph(self, query: str) -> GraphState:
        """사용자 쿼리를 LangGraph에 전달하고 산출물을 정리"""
        print("🚀 LangGraph 실행 시작")

        initial_state: GraphState = {
            "original_query": query
        }

        final_state: GraphState = await self.graph.ainvoke(initial_state)

        generated_code = final_state.get("generated_code")
        if generated_code:
            artifact_info = final_state.get("artifact_info") or self._derive_artifact_info(query, final_state)
            final_state["artifact_info"] = artifact_info
            file_path = self._persist_generated_code(generated_code, artifact_info)
            final_state["file_path"] = file_path
        else:
            print("⚠️ 생성된 코드가 없습니다.")

        print("✅ LangGraph 실행 완료")
        return final_state


async def process_query(user_query):
    """
    사용자의 쿼리를 받아 RAG_Graph를 실행하고 결과를 반환하는 함수
    """
    graph_run = RAG_Graph(
        testcase_db_path="/Users/admin/Documents/2025_project/QE_RAG_COMPANY/QE_RAG_2025/chroma_db",
        testcase_collection_name="jira_test_cases",
        testcase_embedding_model="intfloat/multilingual-e5-large",
        lm_studio_url="http://127.0.0.1:1234/v1",
        lm_studio_model="qwen/qwen3-8b"
    )

    final_state = await graph_run.run_graph(user_query)
    
    return final_state
    
