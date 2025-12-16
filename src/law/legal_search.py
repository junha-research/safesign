import os
import requests
import xml.etree.ElementTree as ET
import json 
from dotenv import load_dotenv

# 1. 환경 설정: API 키 로드
load_dotenv()
MOLEG_API_KEY = os.getenv("MOLEG_API_KEY") 

def search_law_id(law_name):
    """
    법령 이름으로 ID를 검색하고 법령명(real_name)과 ID를 반환합니다. (JSON 응답 파싱)
    사용 API: lawSearch (type=json)
    """
    url = f"http://www.law.go.kr/DRF/lawSearch.do?OC={MOLEG_API_KEY}&target=eflaw&nw=3&query={law_name}&type=json" 
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status() 
        data = response.json() 
        
        laws = data.get("LawSearch", {}).get("law", []) 
        target = None
        
        if laws:
            exact_match = next((law for law in laws if law.get("법령명한글") == law_name), None)
            
            if exact_match:
                target = exact_match
            else:
                laws.sort(key=lambda x: len(x.get("법령명한글", "")))
                target = laws[0]
                
        if target:
            raw_id = target.get("법령ID")
            real_name = target.get("법령명한글")
            return str(int(raw_id)) if raw_id and raw_id.isdigit() else raw_id, real_name
    except requests.exceptions.RequestException as e:
        print(f"⚠️ ID 검색 및 요청 실패 ({law_name}): {e}")
    except json.JSONDecodeError:
        print(f"⚠️ ID 검색 JSON 파싱 실패 ({law_name}).")
    except Exception as e:
        print(f"⚠️ ID 검색 중 일반 오류 ({law_name}): {e}")
    return None, None

def get_law_content_xml(law_id):
    """
    법령 본문 XML을 가져와 raw content (bytes)로 반환합니다.
    사용 API: lawService (type=XML 요청)
    """
    if not law_id: return None
    
    # 법령 본문은 XML 포맷으로 요청
    url = f"http://www.law.go.kr/DRF/lawService.do?OC={MOLEG_API_KEY}&target=eflaw&ID={law_id}&type=XML" 
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"⚠️ 본문 XML 다운로드 실패 (ID:{law_id}): {e}")
        return None
    except Exception as e:
        print(f"⚠️ 본문 XML 다운로드 중 일반 오류 (ID:{law_id}): {e}")
        return None

def parse_articles_from_xml(xml_content):
    """
    raw XML content를 받아 조항별 텍스트로 파싱하여 리스트로 반환합니다.
    """
    if xml_content is None:
        return []
    
    parsed_articles = []
    
    try:
        root = ET.fromstring(xml_content) 
        
        for unit in root.findall(".//조문단위"):
            if unit.find("조문여부") is not None and unit.find("조문여부").text != "조문":
                continue
                
            text_buffer = []
            for elem in unit.iter():
                if elem.text and elem.text.strip():
                    tag = elem.tag
                    text = elem.text.strip()
                    
                    if tag == "조문내용": text_buffer.append(text)
                    elif tag in ["항번호", "호번호", "목번호"]: text_buffer.append(f"\n  {text}") 
                    else: text_buffer.append(f" {text}")
            
            full_text = "".join(text_buffer).strip()
            
            if full_text:
                parsed_articles.append(full_text)
                
    except ET.ParseError:
        print("⚠️ XML 파싱 실패: 응답 내용이 유효한 XML이 아닙니다.")
    except Exception as e:
        print(f"⚠️ XML 파싱 중 일반 오류: {e}")
        
    return parsed_articles