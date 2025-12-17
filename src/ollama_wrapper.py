from langchain_community.llms import Ollama
from deepeval.models.base_model import DeepEvalBaseLLM

class OllamaDeepEvalWrapper(DeepEvalBaseLLM):
    """
    DeepEval에서 Ollama 모델을 사용하기 위한 래퍼 클래스
    """
    def __init__(self, model_name="llama3"):
        self.model_name = model_name
        self.model = Ollama(model=model_name)

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        try:
            return self.model.invoke(prompt)
        except Exception as e:
            return f"Ollama Generation Error: {e}"

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self):
        return self.model_name