"""Frankfurter API 공통 설정 (home.py, page1.py, page2.py에서 함께 사용)"""
import requests
import streamlit as st

# 옛 주소(api.frankfurter.app)는 매번 이 주소로 리다이렉트되어 요청이 두 번 일어남
API_URL = "https://api.frankfurter.dev/v1"


@st.cache_resource
def get_session():
    """연결을 재사용하는 Session을 앱 전체에서 하나만 만들어 공유한다.
    처음 요청 이후에는 서버와 다시 연결하는 시간이 들지 않아 훨씬 빨라진다."""
    return requests.Session()


# 통화 코드 → 한국어 나라(지역) 이름 (Frankfurter가 지원하는 30개 통화)
COUNTRY_NAMES = {
    "AUD": "호주", "BRL": "브라질", "CAD": "캐나다", "CHF": "스위스",
    "CNY": "중국", "CZK": "체코", "DKK": "덴마크", "EUR": "유럽",
    "GBP": "영국", "HKD": "홍콩", "HUF": "헝가리", "IDR": "인도네시아",
    "ILS": "이스라엘", "INR": "인도", "ISK": "아이슬란드", "JPY": "일본",
    "KRW": "한국", "MXN": "멕시코", "MYR": "말레이시아", "NOK": "노르웨이",
    "NZD": "뉴질랜드", "PHP": "필리핀", "PLN": "폴란드", "RON": "루마니아",
    "SEK": "스웨덴", "SGD": "싱가포르", "THB": "태국", "TRY": "튀르키예",
    "USD": "미국", "ZAR": "남아프리카공화국",
}


def currency_label(code):
    """selectbox에 보여 줄 이름. 예: "USD - 미국" (목록에 없는 새 통화는 코드만)"""
    return f"{code} - {COUNTRY_NAMES[code]}" if code in COUNTRY_NAMES else code


@st.cache_data(ttl=60 * 60 * 24)  # 통화 목록은 거의 바뀌지 않으므로 하루 동안 재사용
def get_currencies():
    res = get_session().get(f"{API_URL}/currencies", timeout=10)
    res.raise_for_status()
    return res.json()  # {"USD": "United States Dollar", "KRW": "South Korean Won", ...}
