from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

from api import API_URL, get_session

# (통화 코드, 표시 단위) - 엔화는 보통 100엔 기준으로 표시
MAJOR_CURRENCIES = [("USD", 1), ("EUR", 1), ("JPY", 100)]


@st.cache_data(ttl=60 * 60 * 3)  # 환율은 하루 한 번 갱신되므로 3시간 동안 재사용
def get_major_rates():
    """최근 일주일치 KRW 기준 환율을 가져와서 '외화 1단위 = 몇 원' 형태로 바꾼다."""
    end = date.today()
    start = end - timedelta(days=7)  # 주말·공휴일이 있어도 최근 2영업일이 포함되도록
    codes = ",".join(code for code, _ in MAJOR_CURRENCIES)

    res = get_session().get(
        f"{API_URL}/{start}..{end}",
        params={"from": "KRW", "to": codes},
        timeout=10,
    )
    res.raise_for_status()

    df = pd.DataFrame(res.json()["rates"]).T
    df.index = pd.to_datetime(df.index)
    return 1 / df  # 1원 = 0.00074달러 → 1달러 = 1,350원


st.title("💱 환율 도우미")
st.write("실시간 환율 조회와 환율 추이 차트를 제공하는 웹앱입니다.")

# 오늘의 주요 환율
st.subheader("오늘의 주요 환율")

try:
    rates = get_major_rates()
except requests.RequestException as e:
    st.error(f"환율 정보를 불러오지 못했어요: {e}")
else:
    latest, previous = rates.iloc[-1], rates.iloc[-2]
    cols = st.columns(len(MAJOR_CURRENCIES))
    for col, (code, unit) in zip(cols, MAJOR_CURRENCIES):
        value = latest[code] * unit
        change = (latest[code] - previous[code]) * unit
        col.metric(
            label=f"{unit} {code} → KRW",
            value=f"{value:,.2f}원",
            delta=f"{change:+,.2f}원 (전일 대비)",
        )
    st.caption(f"기준일: {rates.index[-1]:%Y-%m-%d}")

st.divider()

# 기능 소개
st.subheader("기능 소개")
col1, col2 = st.columns(2)
with col1:
    st.markdown("### 💬 환율 챗봇")
    st.write("'100달러 원화로 얼마야?'처럼 자연어로 물어보세요.")
    st.page_link("page1.py", label="챗봇 바로가기", icon="💬")
with col2:
    st.markdown("### 📈 환율 차트")
    st.write("통화와 기간을 골라 환율 변화를 그래프로 확인하세요.")
    st.page_link("page2.py", label="차트 바로가기", icon="📈")

st.caption("환율 데이터 출처: 유럽중앙은행(ECB) / Frankfurter API")
