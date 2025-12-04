# build_db.py
import os
import time
from datasets import load_dataset
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# --- 설정 ---
EMBEDDING_MODEL = "jhgan/ko-sbert-nli"
DB_PATH = "precedent_faiss_db"
# HuggingFace에 공개된 판례 데이터셋 (예시)
DATASET_ID = "joonhok-exo-ai/korean_law_open_data_precedents" 
SAMPLE_SIZE = 1000  # 테스트용으로 1000개만 (전체 사용 시 None으로 변경)

def build_vector_db():
    print(f"📥 1. 판례 데이터셋 다운로드 중... ({DATASET_ID})")
    try:
        # split="train"은 데이터셋 구조에 따라 다를 수 있음
        dataset = load_dataset(DATASET_ID, split="train")
        print(f"   - 전체 데이터 개수: {len(dataset)}개")
        
        if SAMPLE_SIZE and len(dataset) > SAMPLE_SIZE:
            dataset = dataset.select(range(SAMPLE_SIZE))
            print(f"   - (설정) 상위 {SAMPLE_SIZE}개만 벡터화합니다.")
            
    except Exception as e:
        print(f"❌ 데이터셋 로드 실패: {e}")
        return

    print("\n🔄 2. 문서 객체(Document)로 변환 중...")
    documents = []
    
    for item in dataset:
        # 업로드된 파일 로직에 맞춘 컬럼 매핑
        content = item.get('전문', '')
        summary = item.get('판결요지', '')
        note = item.get('판시사항', '')
        case_name = item.get('사건명', '사건명 정보 없음')
        
        if not content or len(str(content)) < 10: 
            continue

        # 검색 최적화를 위해 중요 정보를 앞단에 배치
        page_content = f"""
[사건명] {case_name}
[판시사항] {note}
[판결요지] {summary}
[전문] {content[:2000]}...
"""
        metadata = {
            "case_name": case_name,
            "source": "Precedent_DB"
        }
        documents.append(Document(page_content=page_content, metadata=metadata))

    print(f"   - 변환된 문서: {len(documents)}개")

    print(f"\n🧮 3. 임베딩 및 벡터 DB 저장 중... (모델: {EMBEDDING_MODEL})")
    try:
        start_time = time.time()
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        
        # FAISS DB 생성
        vectorstore = FAISS.from_documents(documents, embeddings)
        vectorstore.save_local(DB_PATH)
        
        print(f"✅ DB 저장 완료! 경로: ./{DB_PATH} (소요시간: {time.time()-start_time:.1f}초)")
        
    except Exception as e:
        print(f"❌ 벡터 DB 생성 실패: {e}")

if __name__ == "__main__":
    build_vector_db()