# safesign

폴더구조(수정가능)
```
Labor-Contract-Validator/
│
│
├── data/                      # 데이터 저장소 [cite: 312]
│   ├── vector_store/          # ChromaDB/FAISS (판례 임베딩 저장소)
│   └── raw_laws/              # 법제처 API 캐싱 데이터 (JSON)
│
├── src/                       # 핵심 소스 코드 (Backend & Logic)
│   ├── legal_context.py       # 법령 추출 및 벡터화
│   ├── legal_search.py        # 판례 추출 및 벡터화
│   ├── llm_service.py         # LLM 답변 생성
│   ├── rag_pipeline.py        # 
│   ├── toxic_detector.py      # DeepEval 기반 독소조항 판별
│
├── ui/                        # 프론트엔드 컴포넌트
│   ├── dashboard.py           # 결과 시각화 (차트, 게이지)
│   ├── uploader.py            # 파일 업로드 위젯
│   └── layout.py              # 전체 페이지 레이아웃 관리
│
├── tests/                     # 단위 테스트 및 평가 실행
│   ├── test_parser.py
│   └── eval_experiment.py     # DeepEval 실험 실행 스크립트
│
├── .env                       # API KEY 관리 (Git 업로드 금지)
├── .gitignore                 # Git 무시 설정
├── main.py                    # Streamlit 실행 진입점 (Entry Point)
├── README.md                  # 프로젝트 설명서
└── requirements.txt           # 의존성 라이브러리 목록
```
