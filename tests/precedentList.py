import requests

# 요청 URL
url = 'http://www.law.go.kr/DRF/lawSearch.do?OC=junhajs&target=prec&type=JSON&query=부당해고'

# params = {
#     "OC": "junhajs",                # 사용자 이메일 ID (예: g4c@korea.kr → OC=g4c)
#     "target": "eflaw",     # 법령 검색
#     "type": "JSON",              # 출력 형태 (XML, HTML, JSON 중 선택)
#     "org": "1490000",           # 소관부처:고용노동부
# }

# GET 요청 보내기
response = requests.get(url)

# 응답 상태 확인
if response.status_code == 200:
    print(response.text)
    # data = response.json()  # JSON 파싱
    # print(data)             # 전체 데이터 출력
else:
    print("Error:", response.status_code)