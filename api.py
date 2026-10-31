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
