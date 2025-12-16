import os
import requests
import xml.etree.ElementTree as ET
import json  # JSON 처리를 위해 import 추가
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

# 1. 환경 설정
load_dotenv()
MOLEG_API_KEY = os.getenv("MOLEG_API_KEY")
SAVE_PATH = "../data/faiss_law_db"
TARGET_LAWS = ["근로기준법", "최저임금법", "근로자퇴직급여 보장법"]

# 2. 헬퍼 함수 정의
def search_law_id(law_name):
    """법령 이름으로 ID 검색 (JSON 응답 파싱)"""
    url = f"http://www.law.go.kr/DRF/lawSearch.do?OC={MOLEG_API_KEY}&target=eflaw&nw=3&query={law_name}&type=json"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        laws = data.get("LawSearch", {}).get("law", [])
        if isinstance(laws, dict):
            laws = [laws]

        target = None
        if laws:
            # 정확히 일치하는 법령 우선
            exact_match = next((law for law in laws if law.get("법령명한글") == law_name), None)
            if exact_match:
                target = exact_match
            else:
                # 이름이 가장 짧은 법령 선택 (시행령/시행규칙 배제 목적)
                laws.sort(key=lambda x: len(x.get("법령명한글", "")))
                target = laws[0]

        if target:
            raw_id = target.get("법령ID")
            real_name = target.get("법령명한글")
            return str(int(raw_id)) if raw_id and raw_id.isdigit() else raw_id, real_name
    except Exception as e:
        print(f"⚠️ ID 검색 실패 ({law_name}): {e}")
    return None, None


def get_parsed_articles(law_id, law_name):
    """법령 본문 XML을 가져와 조항별 텍스트로 파싱"""
    url = f"http://www.law.go.kr/DRF/lawService.do?OC={MOLEG_API_KEY}&target=eflaw&ID={law_id}&type=XML"
    parsed_docs = []
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)

        for unit in root.findall(".//조문단위"):
            if unit.find("조문여부").text != "조문":
                continue

            text_buffer = []
            for elem in unit.iter():
                if elem.text and elem.text.strip():
                    tag, text = elem.tag, elem.text.strip()
                    if tag == "조문내용":
                        text_buffer.append(text)
                    elif tag in ["항번호", "호번호", "목번호"]:
                        text_buffer.append(f"\n  {text}")

            full_text = "".join(text_buffer).strip()
            article_num = unit.find(".//조문번호")
            article_title = unit.find(".//조문명")

            metadata = {
                "source": law_name,
                "조문번호": article_num.text.strip() if article_num is not None and article_num.text else "N/A",
                "조문명": article_title.text.strip() if article_title is not None and article_title.text else "N/A",
            }

            if full_text:
                parsed_docs.append(Document(page_content=full_text, metadata=metadata))
    except Exception as e:
        print(f"⚠️ 본문 파싱 실패 ({law_name}): {e}")
    return parsed_docs


# 3. 메인 실행 로직
def build_vector_db():
    print(f"법령 데이터 구축을 시작합니다... (저장 경로: {SAVE_PATH})")
    all_documents = []

    # 3-1. 법령 데이터 수집
    for law_name in TARGET_LAWS:
        print(f"   🔍 '{law_name}' 검색 중...")
        law_id, real_name = search_law_id(law_name)

        if law_id:
            print(f"   📥 '{real_name}'(ID:{law_id}) 본문 다운로드 및 파싱...")
            docs = get_parsed_articles(law_id, real_name)
            all_documents.extend(docs)
            print(f"      👉 {len(docs)}개 조항 추출 완료")
        else:
            print(f"      ❌ 법령 ID를 찾을 수 없습니다. (검색어: {law_name})")

    if not all_documents:
        print("❌ 저장할 데이터가 없습니다.")
        return

    # 3-2. 벡터화 및 저장
    print(f"⚡ 총 {len(all_documents)}개 조항 벡터화 시작 (Model: jhgan/ko-sbert-nli)...")
    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sbert-nli", model_kwargs={'device': 'cpu'})
    vectorstore = FAISS.from_documents(all_documents, embeddings)

    os.makedirs(SAVE_PATH, exist_ok=True)
    vectorstore.save_local(SAVE_PATH)
    print(f"✅ 저장 완료! DB 경로: {os.path.abspath(SAVE_PATH)}")


if __name__ == "__main__":
    build_vector_db()
