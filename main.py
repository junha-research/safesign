import streamlit as st
import re
import os
import time
from dotenv import load_dotenv

# [Import] 같은 폴더에 있는 toxic_detector.py를 불러옵니다.
from src.toxic_detector import ToxicClauseDetector

# --- 1. 페이지 설정 ---
st.set_page_config(
    page_title="근로계약서 독소조항 판별기 (Standard Ver.)",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 더미 데이터 및 파싱 함수 ---
def get_dummy_contract_text():
    """테스트용 가상 근로계약서 텍스트"""
    return """
제1조 (목적)
본 계약은 사용자 (주)악덕상사(이하 "갑")와 근로자 홍길동(이하 "을")의 근로조건을 정함을 목적으로 한다.

제2조 (근로장소 및 업무)
"을"은 "갑"의 본사 및 "갑"이 지정하는 장소에서 소프트웨어 개발 업무를 수행한다.

제3조 (근로시간)
1. 근로시간은 09:00부터 18:00까지로 한다 (휴게시간 1시간 포함).
2. "갑"은 업무상 필요한 경우 "을"에게 연장, 야간 및 휴일근로를 명할 수 있으며 "을"은 이에 동의한 것으로 간주한다.

제4조 (임금)
1. 월 급여는 2,500,000원으로 한다.
2. 위 급여에는 식대, 교통비 및 법정 제수당(연장, 야간, 휴일근로수당 등)이 모두 포함된 포괄임금으로 산정하며, "을"은 추가적인 수당을 청구하지 않는다.

제5조 (퇴직금)
"을"이 입사 후 1년 미만에 퇴사하는 경우, 수습기간 동안의 교육비 및 손해배상 명목으로 퇴직금은 지급하지 아니한다.

제6조 (계약해지)
"을"이 무단결근 3일 이상 지속하거나 업무 능력이 현저히 부족하다고 판단될 경우 "갑"은 즉시 계약을 해지할 수 있다.

제7조 (손해배상)
"을"이 계약기간 중 퇴사하여 "갑"에게 손해를 입힌 경우, "을"은 "갑"에게 일금 1,000만원을 배상하여야 한다.
"""

def parse_text_to_chunks(text):
    """텍스트를 '제N조' 기준으로 자르는 파서"""
    split_pattern = r'(?=\n\s*제\s*\d+\s*조)'
    chunks = re.split(split_pattern, text)
    # 공백 제거 및 유효한 조항만 필터링
    clean_chunks = [c.strip() for c in chunks if len(c.strip()) > 10]
    return clean_chunks

# --- 3. 단위 작업 함수 (Helper) ---
def process_single_clause(detector, clause, index):
    """하나의 조항을 분석하고 결과를 반환하는 함수"""
    try:
        # 1. 독소조항 탐지
        detection = detector.detect(clause)
        
        # 2. 수정 제안 생성 (독소조항일 때만)
        suggestion = ""
        if detection['is_toxic']:
            suggestion = detector.generate_easy_suggestion(detection)
            
        return {
            "id": index + 1,
            "clause": clause,
            "is_toxic": detection['is_toxic'],
            "score": detection['risk_score'],
            "reason": detection['reason'],
            "context": detection['context_used'],
            "suggestion": suggestion,
            "status": "success"
        }
    except Exception as e:
        return {
            "id": index + 1,
            "clause": clause,
            "error": str(e),
            "status": "error"
        }

# --- 4. 메인 어플리케이션 ---
def main():
    # 사이드바 설정
    with st.sidebar:
        st.title("⚖️ Contract Guardian")
        st.markdown("---")
        
        load_dotenv()
        env_key = os.getenv("GEMINI_API_KEY")
        
        api_key_input = st.text_input(
            "Gemini API Key", 
            value=env_key if env_key else "", 
            type="password"
        )
        if api_key_input:
            os.environ["GEMINI_API_KEY"] = api_key_input

        st.info("💡 순차 처리(Sequential Processing) 방식의 안정적인 데모 버전입니다.")

    # 메인 화면
    st.title("📄 근로계약서 독소조항 판별기")
    st.markdown("계약서 내용을 입력하면 AI가 **한 조항씩 꼼꼼하게** 분석합니다.")

    # [입력 영역] 텍스트 에디터 사용
    default_text = get_dummy_contract_text()
    contract_text = st.text_area("계약서 내용 (수정 가능)", value=default_text, height=300)

    # API 키 체크
    if not os.environ.get("GEMINI_API_KEY"):
        st.warning("⚠️ 왼쪽 사이드바에 API Key를 입력해주세요.")
        return

    # [분석 버튼]
    if st.button("🚀 독소조항 분석 시작", use_container_width=True):
        
        # 1. Parsing
        chunks = parse_text_to_chunks(contract_text)
        
        if not chunks:
            st.error("분석할 조항을 찾지 못했습니다. '제N조' 형식이 포함되어 있는지 확인해주세요.")
            st.stop()

        # 2. Detector 초기화 (캐싱)
        @st.cache_resource
        def get_detector():
            # [중요] 객체 생성 시 괄호 () 필수
            return ToxicClauseDetector()
        
        with st.spinner("⚙️ 법령 DB 및 AI 엔진 초기화 중... (최초 1회만 소요)"):
            detector = get_detector()

        st.info(f"총 {len(chunks)}개의 조항을 순서대로 분석합니다.")

        # 3. 순차 실행 루프 (Sequential Loop)
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, clause in enumerate(chunks):
            # 실시간 상태 표시
            status_text.markdown(f"**🕵️ 분석 중 ({i+1}/{len(chunks)}):** 제{i+1}조 심사 중...")
            
            # --- 분석 실행 (동기 방식) ---
            res = process_single_clause(detector, clause, i)
            results.append(res)
            
            # 진행률 업데이트
            progress_bar.progress((i + 1) / len(chunks))
            
            # 짧은 대기 (UX용, 너무 빠르면 눈에 안 보일 수 있음)
            # time.sleep(0.1) 

        status_text.success("✅ 모든 분석이 완료되었습니다!")
        st.session_state.analysis_results = results # 결과 저장
        
        # 4. 결과 리포트 출력
        st.divider()
        
        # 요약 지표
        toxic_count = sum(1 for r in results if r.get('is_toxic'))
        col1, col2 = st.columns(2)
        col1.metric("분석된 조항", f"{len(results)}건")
        col2.metric("발견된 위험 조항", f"{toxic_count}건", delta="-주의" if toxic_count > 0 else "안전")

        # 상세 결과 탭
        tab1, tab2 = st.tabs(["🚨 위험 조항 리포트", "📑 전체 조항 보기"])
        
        with tab1:
            if toxic_count == 0:
                st.success("독소조항이 발견되지 않았습니다.")
            else:
                for res in results:
                    if res.get('is_toxic'):
                        with st.expander(f"⚠️ [위험] 제{res['id']}조 (위험도: {res['score']})", expanded=True):
                            c1, c2 = st.columns(2)
                            with c1:
                                st.caption("원문")
                                st.error(res['clause'])
                                st.markdown(f"**판단 근거:** {res['reason']}")
                            with c2:
                                st.caption("AI 솔루션")
                                st.markdown(res['suggestion'])
                                with st.popover("참고 법령 확인"):
                                    st.text(res['context'])
        
        with tab2:
            for res in results:
                icon = "🔴" if res.get('is_toxic') else "🟢"
                with st.expander(f"{icon} 제{res['id']}조"):
                    st.write(res['clause'])
                    if 'error' in res:
                        st.error(f"에러: {res['error']}")
                    else:
                        st.caption(f"판단 결과: {res['reason']}")

if __name__ == "__main__":
    main()