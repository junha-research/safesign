# src/legal_context.py
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from .legal_search import get_law_content_xml, parse_articles_from_xml, search_law_id

class LawContextManager:
    def __init__(self):
        self.vectorstore = None
        # 근로계약서 분석에 필수적인 '3대장 법령'을 미리 정의
        self.target_laws = ["근로기준법", "최저임금법", "근로자퇴직급여 보장법"]
        self.embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sbert-nli")

    def initialize_database(self):
        """
        필수 법령들을 모두 가져와서 하나의 벡터 DB로 통합합니다. (최초 1회 실행)
        """
        print("📚 [초기화] 필수 법령 데이터를 구축하고 있습니다...")
        all_docs = []

        for law_name in self.target_laws:
            # 1. 법령 ID 찾기
            law_id, real_name = search_law_id(law_name)
            if not law_id:
                continue
            
            # 2. 전문 가져오기
            xml_content = get_law_content_xml(law_id)
            articles = parse_articles_from_xml(xml_content)
            
            # 3. 문서 객체로 변환
            for article in articles:
                doc = Document(
                    page_content=article,
                    metadata={"source": real_name}
                )
                all_docs.append(doc)
        
        if not all_docs:
            print("⚠️ 법령 데이터를 가져오지 못했습니다.")
            return

        # 4. 메모리 내 벡터 DB 생성 (빠름)
        self.vectorstore = FAISS.from_documents(all_docs, self.embeddings)
        print(f"✅ 법령 DB 구축 완료! (총 {len(all_docs)}개 조항)")

    def search_relevant_laws(self, query, k=2):
        """
        메모리 DB에서 관련 조항을 즉시 찾습니다. (API 호출 X)
        """
        if not self.vectorstore:
            return []
        
        # 유사도 검색
        docs = self.vectorstore.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]