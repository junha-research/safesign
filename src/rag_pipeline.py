# main.py
import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# [사용자 모듈 import]
# legal_search.py: 법령 API 검색 및 실시간 벡터화
from .legal_search import search_law_articles_semantically
# llm_service.py: Gemini API 호출 및 법령명 추출
from .llm_service import extract_search_law_name, get_genai_client

# --- 설정 ---
load_dotenv()
DB_PATH = "precedent_faiss_db"
EMBEDDING_MODEL = "jhgan/ko-sbert-nli"

# 전역 변수로 DB 로드 (매번 로딩하지 않도록)
_vectorstore = None
_embeddings = None

def load_precedent_db():
    """판례 벡터 DB를 로드합니다."""
    global _vectorstore, _embeddings
    if _vectorstore is None:
        print("📂 판례 DB 로딩 중...")
        try:
            _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
            if os.path.exists(DB_PATH):
                _vectorstore = FAISS.load_local(
                    DB_PATH, 
                    _embeddings, 
                    allow_dangerous_deserialization=True # 로컬 파일 신뢰 시 True
                )
                print("✅ 판례 DB 로드 완료")
            else:
                print("⚠️ 판례 DB 파일이 없습니다. build_db.py를 먼저 실행하세요.")
        except Exception as e:
            print(f"❌ 판례 DB 로드 오류: {e}")
    return _vectorstore

def search_precedents(query, k=2):
    """로드된 DB에서 유사 판례 검색"""
    db = load_precedent_db()
    if not db: return []
    
    docs = db.similarity_search(query, k=k)
    return [d.page_content for d in docs]

def generate_answer_pipeline(user_question):
    """
    [핵심 파이프라인]
    1. 질문 분석 -> 법령명 추출
    2. 법령 검색 (API -> 실시간 벡터 검색)
    3. 판례 검색 (저장된 FAISS DB)
    4. LLM 답변 생성
    """
    client = get_genai_client()
    if not client:
        return "❌ API Key 오류: .env 파일을 확인하세요."

    print(f"\n🚀 질문 처리 시작: {user_question}")
    
    # ---------------------------------------------------------
    # Step 1: 법령명 추출 (LLM)
    # ---------------------------------------------------------
    print("🔍 [1/4] 관련 법령명 추론 중...")
    search_params = extract_search_law_name(user_question)
    target_law = search_params.get("law_name", "근로기준법")
    print(f"   -> 타겟 법령: {target_law}")

    # ---------------------------------------------------------
    # Step 2: 법령 조항 검색 (API + Real-time FAISS)
    # ---------------------------------------------------------
    print(f"📜 [2/4] 법령 조항 검색 중...")
    # legal_search.py의 함수 사용
    real_law_name, articles = search_law_articles_semantically(target_law, user_question, k=2)
    
    statute_context = ""
    if articles:
        statute_context = "\n\n".join(articles)
        print(f"   -> '{real_law_name}' 관련 조항 {len(articles)}개 확보")
    else:
        statute_context = "(관련 법 조항을 찾지 못했습니다.)"
        print("   -> 관련 조항 없음")

    # ---------------------------------------------------------
    # Step 3: 유사 판례 검색 (Saved FAISS)
    # ---------------------------------------------------------
    print("⚖️ [3/4] 유사 판례 검색 중...")
    precedents = search_precedents(user_question, k=1)
    
    precedent_context = ""
    if precedents:
        precedent_context = precedents[0] # 가장 유사한 1개만 사용
        print("   -> 유사 판례 1건 확보")
    else:
        precedent_context = "(유사 판례를 찾지 못했습니다.)"
        print("   -> 판례 없음")

    # ---------------------------------------------------------
    # Step 4: 최종 답변 생성 (LLM)
    # ---------------------------------------------------------
    print("🤖 [4/4] 최종 답변 생성 중...")
    
    prompt = f"""
    당신은 전문 법률 상담 AI입니다.
    사용자의 질문에 대해 아래 [법령]과 [판례]를 근거로 답변해주세요.

    [사용자 질문]: 
    {user_question}

    [참고 1: 관련 법령 ({real_law_name})]:
    {statute_context}

    [참고 2: 유사 판례]:
    {precedent_context}

    [작성 가이드]:
    1. 결론(가능/불가능 여부)을 먼저 명확히 말해주세요.
    2. [참고 1] 법령 내용을 인용하여 법적 근거를 설명하세요.
    3. [참고 2] 판례 내용을 인용하여 실제 적용 사례를 덧붙이세요.
    4. 어려운 법률 용어는 쉽게 풀어서 설명해주세요.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"❌ 답변 생성 중 오류 발생: {e}"

# --- 실행부 ---
if __name__ == "__main__":
    # 테스트 질문
    q = "아르바이트생도 주휴수당을 받을 수 있나요? 조건이 뭔가요?"
    
    final_answer = generate_answer_pipeline(q)
    
    print("\n" + "="*50)
    print("📝 [최종 답변]")
    print("="*50)
    print(final_answer)