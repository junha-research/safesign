import requests

# 요청 URL
url = 'http://www.law.go.kr/DRF/lawService.do?OC=junhajs&target=eflaw&ID=001872&type=JSON'

# GET 요청 보내기
response = requests.get(url)

# 응답 상태 확인
if response.status_code == 200:
    with open("lawService_resp.txt", "w", encoding="utf-8") as f:
        f.write(response.text)
    # data = response.json()  # JSON 파싱
    # print(data)             # 전체 데이터 출력
else:
    print("Error:", response.status_code)