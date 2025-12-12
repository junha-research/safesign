import requests

# 요청 URL
url = 'http://www.law.go.kr/DRF/lawService.do?OC=junhajs&target=prec&ID=236371&type=XML'

# GET 요청 보내기
response = requests.get(url)

# 응답 상태 확인
if response.status_code == 200:
    print(response.text)
    # data = response.json()  # JSON 파싱
    # print(data)             # 전체 데이터 출력
else:
    print("Error:", response.status_code)