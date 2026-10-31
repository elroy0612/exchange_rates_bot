from datetime import date, timedelta

import altair as alt
import pandas as pd
import requests
import streamlit as st

from api import API_URL, get_session

HISTORY_START = date(1999, 1, 4)  # Frankfurter(ECB) 데이터가 시작되는 날


@st.cache_data(ttl=60 * 60 * 24)  # 통화 목록은 거의 바뀌지 않으므로 하루 동안 재사용
def get_currencies():
    res = get_session().get(f"{API_URL}/currencies", timeout=10)
    res.raise_for_status()
    return res.json()  # {"USD": "United States Dollar", "KRW": "South Korean Won", ...}


# 환율은 하루 한 번(유럽 기준 오후 4시쯤) 갱신되므로 3시간 동안 재사용
# (end에 오늘 날짜가 들어가서 날짜가 바뀌면 자동으로 새로 불러옴)
@st.cache_data(ttl=60 * 60 * 3)
def get_timeseries(base, target, start, end):
    res = get_session().get(
        f"{API_URL}/{start}..{end}",
        params={"from": base, "to": target},
        timeout=30,  # 전체 기간 조회는 몇 초 걸릴 수 있음
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
# 차트를 축소했을 때도 그래프가 꽉 차도록, 선택한 기간과 상관없이
# Frankfurter가 제공하는 전체 기간(1999년~)을 한 번에 불러온다. (통화쌍별로 캐시됨)
try:
    df_all = get_timeseries(base, target, HISTORY_START, end)
except requests.RequestException as e:
    st.error(f"환율 데이터를 불러오지 못했어요: {e}")
    st.stop()

df = df_all[df_all.index >= pd.Timestamp(start)]  # 선택한 기간만 (요약 지표용)
if df.empty:
    st.warning("선택한 기간에 환율 데이터가 없어요.")
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
chart_df = df_all.reset_index()
chart_df.columns = ["날짜", "환율"]

# 마우스 휠 확대/축소, 드래그 이동을 x축(날짜)에만 적용.
# 처음 보이는 범위는 선택한 기간(start ~ 마지막 데이터 날짜)
view_start = df.index[0]
view_end = df.index[-1]
zoom = alt.selection_interval(
    bind="scales",
    encodings=["x"],
    clear=False,  # 더블클릭으로 초기화되는 기능 끄기
    value={"x": [
        alt.DateTime(year=view_start.year, month=view_start.month, date=view_start.day),
        alt.DateTime(year=view_end.year, month=view_end.month, date=view_end.day),
    ]},
)

# 마우스를 올린 위치와 가장 가까운 날짜 선택 (툴팁·세로선 표시용)
hover = alt.selection_point(fields=["날짜"], nearest=True, on="pointerover", empty=False)

# ① 확대/축소를 담당하는 투명 레이어
#    전체 데이터를 갖고 있고 y축을 쓰지 않아서 y축 범위에 영향을 주지 않는다.
zoom_layer = (
    alt.Chart(chart_df)
    .mark_rule(opacity=0)
    .encode(x=alt.X("날짜:T", title=None, axis=alt.Axis(format="%y.%m.%d")))
    .add_params(zoom)
)

# ② 실제로 보이는 레이어들
#    zoom 범위 안의 데이터만 남기기 때문에, y축이 화면에 보이는 데이터에 맞춰 자동으로 바뀐다.
visible = alt.Chart(chart_df).transform_filter(zoom).encode(
    x="날짜:T",
    y=alt.Y(
        "환율:Q",
        title=f"1 {base} → {target}",
        scale=alt.Scale(zero=False, padding=15),  # 0부터 시작하지 않고 위아래 15px 여백
    ),
)

line = visible.mark_line(clip=True)

points = visible.mark_circle(size=60, clip=True).encode(
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

# 확대/축소한 뒤 선택한 기간으로 되돌리기
# 버튼을 누를 때마다 숫자를 올려서 차트를 새로 그리게 만든다.
# (같은 차트를 다시 그리면 Streamlit이 이전 확대 상태를 그대로 유지하기 때문)
if "chart_reset" not in st.session_state:
    st.session_state.chart_reset = 0

caption_col, button_col = st.columns([4, 1], vertical_alignment="center")
with caption_col:
    st.caption("🖱️ 마우스 휠로 확대/축소, 드래그로 이동할 수 있어요.")
with button_col:
    if st.button(f"↺ {period} 보기", width="stretch"):
        st.session_state.chart_reset += 1

chart = (zoom_layer + line + points + rule).properties(
    usermeta={"reset": st.session_state.chart_reset}  # 화면에는 안 보이고, 차트를 새로 그리게 하는 용도
)
st.altair_chart(chart, width="stretch", key=f"chart_{st.session_state.chart_reset}")
