from datetime import date, timedelta

import altair as alt
import pandas as pd
import requests
import streamlit as st

API_URL = "https://api.frankfurter.app"


@st.cache_data(ttl=3600)  # 같은 조건이면 1시간 동안 API를 다시 부르지 않음
def get_currencies():
    res = requests.get(f"{API_URL}/currencies", timeout=10)
    res.raise_for_status()
    return res.json()  # {"USD": "United States Dollar", "KRW": "South Korean Won", ...}


@st.cache_data(ttl=3600)
def get_timeseries(base, target, start, end):
    res = requests.get(
        f"{API_URL}/{start}..{end}",
        params={"from": base, "to": target},
        timeout=10,
    )
    res.raise_for_status()
    data = res.json()

    df = pd.DataFrame(data["rates"]).T  # 날짜가 행이 되도록 행/열 뒤집기
    df.index = pd.to_datetime(df.index)  # 문자열 날짜 → 날짜 타입
    return df


st.title("📈 환율 차트")

# 통화 목록 불러오기
try:
    currencies = get_currencies()
except requests.RequestException as e:
    st.error(f"통화 목록을 불러오지 못했어요: {e}")
    st.stop()

codes = list(currencies.keys())

# 입력 위젯
col1, col2, col3 = st.columns(3)
with col1:
    base = st.selectbox("기준 통화", codes, index=codes.index("USD"))
with col2:
    target = st.selectbox("대상 통화", codes, index=codes.index("KRW"))
with col3:
    period = st.selectbox("기간", ["1개월", "3개월", "6개월", "1년"])

if base == target:
    st.warning("서로 다른 통화를 선택하세요.")
    st.stop()

# 기간 → 날짜 계산
days = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}[period]
end = date.today()
start = end - timedelta(days=days)

# 데이터 불러오기
try:
    df = get_timeseries(base, target, start, end)
except requests.RequestException as e:
    st.error(f"환율 데이터를 불러오지 못했어요: {e}")
    st.stop()

# 요약 지표
latest = df[target].iloc[-1]
first = df[target].iloc[0]
change = latest - first

st.metric(
    label=f"1 {base} → {target} (기준일: {df.index[-1]:%Y-%m-%d})",
    value=f"{latest:,.2f}",
    delta=f"{change:,.2f} ({change / first * 100:+.2f}%)",
)

# 차트
chart_df = df.reset_index()
chart_df.columns = ["날짜", "환율"]

# y축: 0부터가 아니라 데이터의 최솟값~최댓값에 여백 10%를 더한 범위로 고정
y_min, y_max = chart_df["환율"].min(), chart_df["환율"].max()
pad = (y_max - y_min) * 0.1 or y_max * 0.01  # 값이 전부 같을 때 대비
y_domain = [y_min - pad, y_max + pad]

# 마우스 휠 확대/축소, 드래그 이동을 x축(날짜)에만 적용 → y축은 항상 전체 그래프가 보이게 유지
zoom = alt.selection_interval(bind="scales", encodings=["x"])

# 마우스를 올린 위치와 가장 가까운 날짜 선택 (툴팁·세로선 표시용)
hover = alt.selection_point(fields=["날짜"], nearest=True, on="pointerover", empty=False)

base_chart = alt.Chart(chart_df).encode(
    x=alt.X("날짜:T", title=None, axis=alt.Axis(format="%y.%m.%d")),
    y=alt.Y("환율:Q", title=f"1 {base} → {target}", scale=alt.Scale(domain=y_domain)),
)

# clip=True: 확대했을 때 선이 차트 영역 밖으로 삐져나가지 않게 자름
line = base_chart.mark_line(clip=True).add_params(zoom)

points = base_chart.mark_circle(size=60, clip=True).encode(
    opacity=alt.condition(hover, alt.value(1), alt.value(0)),
    tooltip=[
        alt.Tooltip("날짜:T", title="날짜", format="%Y-%m-%d"),
        alt.Tooltip("환율:Q", title=target, format=",.2f"),
    ],
).add_params(hover)

rule = (
    alt.Chart(chart_df)
    .mark_rule(color="gray", clip=True)
    .encode(x="날짜:T")
    .transform_filter(hover)
)

st.altair_chart(line + points + rule, width="stretch")
st.caption("🖱️ 마우스 휠로 확대/축소, 드래그로 이동, 더블클릭으로 원래대로 돌아갑니다.")
