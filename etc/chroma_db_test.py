import chromadb
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
from typing import List, Dict, Any, Optional
import json
import requests
import warnings
import datetime

# FutureWarning 무시
warnings.filterwarnings("ignore", category=FutureWarning)


class LMStudioLLM(LLM):
    """LM Studio와 연동하는 LangChain 호환 LLM 클래스"""
    
    base_url: str = "http://127.0.0.1:1234/v1"
    model_name: str = "qwen/qwen3-8b"
    temperature: float = 0.1
    max_tokens: int = 2048
    
    def __init__(self, 
                 base_url: str = "http://127.0.0.1:1234/v1",
                 model_name: str = "qwen/qwen3-8b",
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


class LangChainTestCaseSystem:
    def __init__(self, 
                 persist_directory: str = "./chroma_db",
                 collection_name: str = "jira_test_cases",
                 embedding_model_name: str = "intfloat/multilingual-e5-large",
                 lm_studio_url: str = "http://127.0.0.1:1234/v1",
                 lm_studio_model: str = "qwen/qwen3-8b"):
        
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        
        # 임베딩 모델 설정 (CPU 사용)
        model_kwargs = {'device': 'cpu', 'trust_remote_code': True}
        encode_kwargs = {'normalize_embeddings': True, 'batch_size': 4}
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
        
        # ChromaDB 연결
        self.vectorstore = self._connect_to_chroma()
        
        # LM Studio LLM 초기화
        self.llm = LMStudioLLM(
            base_url=lm_studio_url,
            model_name=lm_studio_model,
            temperature=0.1,
            max_tokens=2048
        )
        
        # 테스트케이스 찾기용 체인
        self.search_chain = self._setup_search_chain()
        
        # 테스트케이스 생성용 체인
        self.generation_chain = self._setup_generation_chain()
        
        # 결과 저장용
        self.test_results = []
    
    def _connect_to_chroma(self) -> Chroma:
        """기존 ChromaDB 컬렉션에 연결"""
        try:
            vectorstore = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            print(f"✅ 기존 ChromaDB 컬렉션 '{self.collection_name}' 연결 완료")
            return vectorstore
        except Exception as e:
            print(f"❌ ChromaDB 연결 실패: {e}")
            raise
    
    def _setup_search_chain(self) -> RetrievalQA:
        """테스트케이스 검색용 체인 설정"""
        search_prompt_template = PromptTemplate(
            template="""당신은 테스트케이스 검색 전문가입니다. 사용자의 요청에 맞는 테스트케이스를 찾아서 정리해주세요.

검색된 테스트케이스들:
{context}

사용자 요청: {question}

답변 가이드라인:
1. 요청과 관련된 테스트케이스들을 명확하게 정리해주세요
2. 각 테스트케이스의 이슈 키, 테스트 데이터, 테스트 스텝, 예상 결과를 포함해주세요
3. 이슈별로 그룹핑하여 체계적으로 보여주세요
4. 찾은 테스트케이스가 충분하지 않다면 추가 검색 키워드를 제안해주세요

답변:""",
            input_variables=["context", "question"]
        )
        
        return RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vectorstore.as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={"score_threshold": 0.6, "k": 10}
            ),
            chain_type_kwargs={"prompt": search_prompt_template},
            return_source_documents=True
        )
    
    def _setup_generation_chain(self) -> RetrievalQA:
        """테스트케이스 생성용 체인 설정"""
        generation_prompt_template = PromptTemplate(
            template="""당신은 테스트케이스 작성 전문가입니다. 기존 테스트케이스들을 참고하여 새로운 테스트케이스를 작성해주세요.

참고할 기존 테스트케이스들:
{context}

사용자 요청: {question}

새로운 테스트케이스 작성 가이드라인:
1. 사용자 요청에 맞는 구체적인 테스트케이스를 작성해주세요
2. 테스트 목적, 전제 조건, 테스트 스텝, 예상 결과를 명확히 구분해주세요
3. 기존 테스트케이스의 패턴과 형식을 참고하되, 새로운 시나리오를 제안해주세요
4. 테스트 데이터는 구체적이고 현실적으로 작성해주세요
5. Edge Case나 예외 상황도 고려해주세요
6. 가능하다면 여러 개의 테스트케이스 시나리오를 제안해주세요

테스트케이스 형식:
**테스트 케이스: [테스트 제목]**
- **테스트 목적**: [목적 설명]
- **전제 조건**: [사전 조건]
- **테스트 스텝**:
  1. [스텝 1]
  2. [스텝 2]
  ...
- **테스트 데이터**: [필요한 데이터]
- **예상 결과**: [기대하는 결과]

답변:""",
            input_variables=["context", "question"]
        )
        
        return RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 8}
            ),
            chain_type_kwargs={"prompt": generation_prompt_template},
            return_source_documents=True
        )
    
    def find_test_cases(self, query: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """테스트케이스 찾기 기능"""
        try:
            print(f"🔍 테스트케이스 검색 중: {query}")
            
            formatted_query = f"query: {query}"
            response = self.search_chain({"query": formatted_query})
            
            # 소스 문서 정리
            source_docs = []
            for doc in response.get("source_documents", []):
                source_docs.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "issue_key": doc.metadata.get("issue_key", ""),
                    "step_index": doc.metadata.get("step_index", "")
                })
            
            result = {
                "query": query,
                "answer": response["result"],
                "found_test_cases": source_docs,
                "total_found": len(source_docs)
            }
            
            # 결과 저장
            self._save_result("find_test_cases", query, result)
            
            return result
            
        except Exception as e:
            error_msg = f"테스트케이스 검색 중 오류: {str(e)}"
            print(f"❌ {error_msg}")
            error_result = {"query": query, "error": error_msg}
            self._save_result("find_test_cases", query, error_result)
            return error_result
    
    def generate_test_case(self, requirement: str) -> Dict[str, Any]:
        """테스트케이스 생성 기능"""
        try:
            print(f"🚀 테스트케이스 생성 중: {requirement}")
            
            formatted_requirement = f"query: {requirement}"
            response = self.generation_chain({"query": formatted_requirement})
            
            # 참고한 소스 문서들
            reference_docs = []
            for doc in response.get("source_documents", []):
                reference_docs.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "issue_key": doc.metadata.get("issue_key", ""),
                    "step_index": doc.metadata.get("step_index", "")
                })
            
            result = {
                "requirement": requirement,
                "generated_test_case": response["result"],
                "reference_test_cases": reference_docs,
                "reference_count": len(reference_docs)
            }
            
            # 결과 저장
            self._save_result("generate_test_case", requirement, result)
            
            return result
            
        except Exception as e:
            error_msg = f"테스트케이스 생성 중 오류: {str(e)}"
            print(f"❌ {error_msg}")
            error_result = {"requirement": requirement, "error": error_msg}
            self._save_result("generate_test_case", requirement, error_result)
            return error_result
    
    def _save_result(self, test_type: str, query: str, result: Any):
        """결과 저장"""
        self.test_results.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "framework": "langchain",
            "test_type": test_type,
            "query": query,
            "result": result
        })
    
    def save_results_to_file(self, filename: str = None):
        """결과를 파일에 저장"""
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"langchain_testcase_results_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, ensure_ascii=False, indent=2)
            print(f"✅ LangChain 결과가 {filename}에 저장되었습니다.")
        except Exception as e:
            print(f"❌ 파일 저장 오류: {e}")
    
    def print_find_result(self, result: Dict[str, Any]):
        """테스트케이스 찾기 결과 출력"""
        print(f"\n📋 검색 결과:")
        print("=" * 50)
        if "error" in result:
            print(f"❌ 오류: {result['error']}")
            return
        
        print(f"🔍 검색 쿼리: {result['query']}")
        print(f"📊 찾은 테스트케이스 수: {result['total_found']}개")
        print(f"\n💡 분석 결과:")
        print(result['answer'])
        
        if result['found_test_cases']:
            print(f"\n📚 찾은 테스트케이스들:")
            for i, doc in enumerate(result['found_test_cases'][:5], 1):
                issue_key = doc['issue_key']
                step_idx = doc['step_index']
                print(f"\n{i}. {issue_key}_step_{step_idx}")
                print(f"   {doc['content'][:150]}...")
    
    def print_generation_result(self, result: Dict[str, Any]):
        """테스트케이스 생성 결과 출력"""
        print(f"\n🚀 생성 결과:")
        print("=" * 50)
        if "error" in result:
            print(f"❌ 오류: {result['error']}")
            return
        
        print(f"📝 요구사항: {result['requirement']}")
        print(f"📊 참고한 테스트케이스 수: {result['reference_count']}개")
        print(f"\n🎯 생성된 테스트케이스:")
        print(result['generated_test_case'])
    
    def run_comprehensive_test(self):
        """종합 테스트 실행"""
        print("🚀 LangChain 테스트케이스 시스템 종합 테스트 시작")
        print("=" * 60)
        
        # 1. 테스트케이스 찾기 테스트들
        find_queries = [
            "Master Admin과 관련된 테스트케이스 중에서 master admin 설정 갯수에 대한 테스트케이스를 가져와줘"
        ]
        
        print("\n🔍 테스트케이스 찾기 테스트")
        print("-" * 40)
        for query in find_queries:
            result = self.find_test_cases(query)
            self.print_find_result(result)
            print("\n" + "="*30 + "\n")
        
        # 2. 테스트케이스 생성 테스트들
        generation_requirements = [
            "장치에 전체 관리자 설정을 강제할 수 있는 Master Admin 기능이 있는데 이 기능은 다음과 같이 동작을 해. 다만 이 기능이 동작을 하기 위해서는 조건이 있어. 버전이 V1.4.0 이상으로 생산된 제품이어야해. 조건에 부합되는 장치의 전원이 인가되면 화면에 Master Admin 설정화면이 표시가 돼. 하지만 버전이 V1.4.0 이하로 생산된 제품의 경우에는 장치 전원이 인가되면 메인화면이 표시가 돼. 버전은 BS3의 이전 버전들을 참고해서 테스트 케이스로 작성해줘."
        ]
        
        print("\n🚀 테스트케이스 생성 테스트")
        print("-" * 40)
        for requirement in generation_requirements:
            result = self.generate_test_case(requirement)
            self.print_generation_result(result)
            print("\n" + "="*30 + "\n")
        
        # 결과 저장
        self.save_results_to_file()
        
        print(f"\n🎉 LangChain 종합 테스트 완료!")
        print(f"총 {len(self.test_results)}개의 결과가 저장되었습니다.")


# 사용 예시
if __name__ == "__main__":
    # LangChain 테스트케이스 시스템 초기화
    langchain_system = LangChainTestCaseSystem(
        lm_studio_url="http://127.0.0.1:1234/v1",
        lm_studio_model="qwen/qwen3-8b"
    )
    
    # 종합 테스트 실행
    langchain_system.run_comprehensive_test()