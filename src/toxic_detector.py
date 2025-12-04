# src/toxic_detector.py
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from .llm_service import get_genai_client
from deepeval.models.base_model import DeepEvalBaseLLM

# [변경] 기존 rag_pipeline 대신 새로 만든 Context Manager 사용
from .legal_context import LawContextManager 
from .rag_pipeline import search_precedents # 판례는 기존대로 유지 (이미 DB가 있으므로)
from dotenv import load_dotenv
from deepeval.metrics.g_eval import Rubric
load_dotenv()

# --- 1. DeepEval용 Gemini Wrapper 설정 ---
class GeminiDeepEvalLLM(DeepEvalBaseLLM):
    def __init__(self, model_name="gemini-2.5-flash"):
        self.client = get_genai_client()
        self.model_name = model_name

    def load_model(self):
        return self.client

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"Error: {e}"

    async def a_generate(self, prompt: str) -> str:
        # 비동기 처리가 필요할 경우 구현 (여기선 동기 함수 호출)
        return self.generate(prompt)

    def get_model_name(self):
        return self.model_name

# --- 2. 독소조항 판별기 클래스 ---
class ToxicClauseDetector:
    def __init__(self):
        self.evaluator_llm = GeminiDeepEvalLLM()
        # [추가] 법령 매니저 초기화
        self.law_manager = LawContextManager()
        self.law_manager.initialize_database() # 객체 생성 시 1번만 실행됨 (약 3~5초 소요)
        # [핵심] G-Eval 평가 기준 (Rubric) 정의
        self.toxic_criteria = """
        당신은 한국의 근로기준법을 수호하는 엄격한 '근로계약서 감사관'입니다.
        입력된 '근로계약 조항'이 '관련 법령/판례(Context)'에 비추어 볼 때 근로자에게 불리하거나 불법적인지 평가하세요.
        
        [독소조항 판단 기준]
        1. 강행규정 위반: 최저임금 미달, 퇴직금 포기 각서, 위약금 예정 등 법으로 금지된 내용인가?
        2. 포괄임금 오남용: 근로시간 산정이 가능한데도 포괄임금제를 적용하여 수당을 미지급하려 하는가?
        3. 불공정성: '갑'에게 일방적으로 유리하거나, 모호한 표현으로 '을'의 권리를 제한하는가?
        4. 절차 무시: 해고, 징계 등의 절차를 법적 기준보다 간소화하거나 생략하는가?
        """
        self.rubric = [
        Rubric(score_range=(0,2), expected_outcome="완전히 불공정한 계약."),
        Rubric(score_range=(3,5), expected_outcome="대체로 불공정한 계약."),
        Rubric(score_range=(6,7), expected_outcome="공정한 계약이지만 잠재적으로 불공정할 수 있는 조항 존재."),
        Rubric(score_range=(8,10), expected_outcome="불공정한 조항 없이 완전히 공정한 계약"),
    ]
        self.evaluation_steps = [
            "입력된 '계약 조항'의 핵심 주제(임금, 근로시간, 해고 등)를 파악한다.",
            "제공된 'Context(법령/판례)'와 조항을 비교하여 법적 기준(Minimum Standard)보다 낮은지 확인한다.",
            "조항에 '위약금', '손해배상액 예정', '민형사상 이의 제기 금지' 등의 불법 키워드가 있는지 확인한다.",
            "위반 사항이 발견되면 '독소조항(Toxic)'으로 간주하고 높은 위험 점수를 부여한다.",
            "법적 문제가 없다면 낮은 점수를 부여한다."
        ]

    def _retrieve_context(self, clause_text):
        """
        Context 검색 로직 변경 (API 호출 -> 로컬 DB 검색)
        """
        # 1. 법령 검색 (이제 엄청 빠름!)
        laws = self.law_manager.search_relevant_laws(clause_text, k=2)
        law_text = "\n".join(laws) if laws else "관련 법령 없음"

        # 2. 판례 검색
        precedents = search_precedents(clause_text, k=1)
        precedent_text = precedents[0] if precedents else "관련 판례 없음"

        return f"[관련 법령]\n{law_text}\n\n[관련 판례]\n{precedent_text}"

    def detect(self, clause_text):
        """
        단일 조항을 분석하여 독소조항 여부, 점수, 근거를 반환합니다.
        """
        print(f"🕵️ 조항 분석 중: {clause_text[:30]}...")
        
        # 1. Retrieval
        retrieved_context = self._retrieve_context(clause_text)
        
        # 2. G-Eval Metric 설정
        toxic_metric = GEval(
            name="Toxic Clause Score",
            criteria=self.toxic_criteria,
            rubric=self.rubric,
            # evaluation_steps=self.evaluation_steps,
            model=self.evaluator_llm,
            threshold=0.5, # 0.5 이상이면 독소조항으로 간주 (설정에 따라 다름)
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.RETRIEVAL_CONTEXT]
        )

        # 3. Test Case 생성
        test_case = LLMTestCase(
            input=clause_text,
            actual_output="이 조항은 평가 대상입니다.", # G-Eval은 Output이 없어도 Input-Context 관계 평가 가능
            retrieval_context=[retrieved_context]
        )

        # 4. 평가 실행
        toxic_metric.measure(test_case)
        
        # 5. 결과 포맷팅
        # G-Eval 점수는 0~1 사이로 나옵니다. (0: 안전, 1: 매우 위험으로 프롬프트 조정 필요)
        # DeepEval 기본은 '높을수록 좋은 것'일 수 있으므로, 
        # 점수가 높게 나왔다면 "법적으로 완벽함", 낮다면 "위반됨"일 수 있습니다.
        # **주의**: 프롬프트에서 "위반되면 높은 점수"라고 명시하거나, 해석을 반대로 해야 합니다.
        # 여기서는 score를 "안전도(Safety Score)"로 해석하겠습니다. (점수가 낮으면 위험)
        
        safety_score = toxic_metric.score # 0.0 ~ 1.0
        risk_score = 1.0 - safety_score # 위험도로 변환 (0: 안전, 1: 위험)
        
        is_toxic = risk_score > 0.4 # 위험도 0.4 초과시 독소조항 판단
        
        return {
            "clause": clause_text,
            "is_toxic": is_toxic,
            "risk_score": round(risk_score * 10, 1), # 10점 만점 환산
            "reason": toxic_metric.reason,
            "context_used": retrieved_context
        }

    def generate_easy_suggestion(self, detection_result):
        """
        판별 결과를 바탕으로 '쉬운 해석'과 '수정 제안'을 생성합니다. (Generator)
        """
        if not detection_result['is_toxic']:
            return "✅ 법적으로 문제없는 안전한 조항입니다."

        prompt = f"""
        당신은 근로자 편인 법률 전문가입니다.
        아래 조항이 '독소조항'으로 판별되었습니다.
        
        [원문 조항]: {detection_result['clause']}
        [위험 판단 근거]: {detection_result['reason']}
        [참고 법령/판례]: {detection_result['context_used']}

        다음 두 가지를 마크다운 형식으로 작성해주세요:
        1. **쉬운 해석**: 이 조항이 왜 위험한지 초등학생도 알기 쉽게 설명 (2문장 이내)
        2. **수정 제안**: 근로자에게 유리하거나 법에 맞게 수정한 조항 예시
        """
        
        return self.evaluator_llm.generate(prompt)

# --- 실행 테스트 ---
if __name__ == "__main__":
    detector = ToxicClauseDetector()
    
    # 테스트용 독소조항 예시
    toxic_clause = "제10조 (퇴직금) 근로자가 입사 후 1년 이내에 퇴사하는 경우, 회사는 교육비 명목으로 퇴직금을 지급하지 아니하며, 근로자는 이에 대해 민형사상 이의를 제기할 수 없다."
    
    print("\n🚀 [독소조항 판별 시작]")
    result = detector.detect(toxic_clause)
    
    print(f"\n📊 위험도: {result['risk_score']} / 10")
    print(f"🚨 독소조항 여부: {'네, 위험합니다!' if result['is_toxic'] else '아니오, 안전합니다.'}")
    print(f"📝 판단 근거: {result['reason']}")
    
    print("\n💡 [AI 솔루션]")
    suggestion = detector.generate_easy_suggestion(result)
    print(suggestion)