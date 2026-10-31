from datetime import date

import requests
import streamlit as st
from langchain.tools import tool
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from api import API_URL, get_session

HISTORY_START = date(1999, 1, 4)  # Frankfurter(ECB) 데이터가 시작되는 날


@tool
def get_exchange_rate(from_currency: str, to_currency: str, amount: float = 1.0) -> str:
    """
    두 통화 사이의 최신 환율을 조회하고 금액을 변환한다.
    통화 코드는 ISO 3자리 코드(USD, KRW, EUR, JPY 등)를 사용한다.
    """

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return f"{amount} {from_currency} = {amount} {to_currency} (같은 통화)"

    try:
        res = get_session().get(
            f"{API_URL}/latest",
            params={"from": from_currency, "to": to_currency, "amount": amount},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
    except requests.RequestException as e:
        return f"환율 조회 실패: {e}"

    converted = data["rates"][to_currency]
    date = data["date"]

    return f"{amount} {from_currency} = {converted:,.2f} {to_currency} (기준일: {date}, 출처: ECB/Frankfurter)"


@tool
def get_historical_exchange_rate(
    from_currency: str,
    to_currency: str,
    start_date: str,
    end_date: str | None = None,
) -> str:
    """
    과거 환율을 조회한다. 날짜는 YYYY-MM-DD 형식이고, 1999-01-04 이후 데이터만 있다.
    - start_date만 주면: 그 날짜의 환율 (주말·공휴일이면 직전 영업일 값)
    - start_date와 end_date를 모두 주면: 그 기간의 환율 추이 요약
      (시작·끝 값, 변동률, 최고·최저, 중간 지점 값들)
    "작년 이맘때 환율", "지난달보다 올랐어?", "최근 한 달 추이" 같은 질문에 사용한다.
    통화 코드는 ISO 3자리 코드(USD, KRW, EUR, JPY 등)를 사용한다.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return "같은 통화끼리는 환율이 항상 1이에요."

    # 날짜 형식 검사
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date) if end_date else None
    except ValueError:
        return "날짜 형식이 잘못됐어요. YYYY-MM-DD 형식으로 다시 시도하세요."

    if start < HISTORY_START:
        return f"{HISTORY_START} 이전 데이터는 없어요."
    if start > date.today() or (end and end > date.today()):
        return "미래 날짜의 환율은 조회할 수 없어요."
    if end and end < start:
        start, end = end, start  # 순서가 바뀌어 들어오면 바로잡기

    # API 호출: 날짜 하나면 /2025-01-02, 기간이면 /2025-01-01..2025-01-31
    path = f"{start}..{end}" if end else f"{start}"
    try:
        res = get_session().get(
            f"{API_URL}/{path}",
            params={"from": from_currency, "to": to_currency},
            timeout=30,
        )
        res.raise_for_status()
        data = res.json()
    except requests.RequestException as e:
        return f"환율 조회 실패: {e}"

    # ① 특정 날짜 하나
    if not end:
        rate = data["rates"][to_currency]
        note = "" if data["date"] == str(start) else " (요청한 날짜가 휴일이라 직전 영업일 값)"
        return f"1 {from_currency} = {rate:,.2f} {to_currency} (기준일: {data['date']}{note}, 출처: ECB/Frankfurter)"

    # ② 기간 추이 요약
    series = sorted((d, r[to_currency]) for d, r in data["rates"].items())  # [(날짜, 값), ...]
    if not series:
        return "해당 기간에 환율 데이터가 없어요."

    first_date, first = series[0]
    last_date, last = series[-1]
    high_date, high = max(series, key=lambda x: x[1])
    low_date, low = min(series, key=lambda x: x[1])
    change = last - first

    # 추이를 파악할 수 있게 중간 지점 값을 최대 10개 정도 골라서 함께 전달
    step = max(1, len(series) // 10)
    samples = ", ".join(f"{d}: {r:,.2f}" for d, r in series[::step])

    return (
        f"[{from_currency} → {to_currency} 기간 추이 {first_date} ~ {last_date}, 영업일 {len(series)}일, 출처: ECB/Frankfurter]\n"
        f"- 시작: {first:,.2f} → 끝: {last:,.2f} (변동 {change:+,.2f}, {change / first * 100:+.2f}%)\n"
        f"- 최고: {high:,.2f} ({high_date}) / 최저: {low:,.2f} ({low_date})\n"
        f"- 중간 값: {samples}"
    )


SYSTEM_PROMPT = """너는 환율 안내 챗봇이야. 오늘 날짜는 {today}이다. 답변은 한국어로 해.

[도구 사용 규칙]
- 현재 환율, 환전 금액 계산 → get_exchange_rate
- 과거 특정 날짜의 환율, 기간별 추이·비교 → get_historical_exchange_rate
  "작년 이맘때", "지난달", "최근 3개월" 같은 표현은 오늘 날짜를 기준으로 YYYY-MM-DD로 바꿔서 사용해.
- 환율 수치는 반드시 도구 결과만 사용하고, 추측하거나 기억에 의존하지 마.

[환율 변동 원인을 묻는 질문]
"왜 올랐어/떨어졌어?", "요즘 원화가 왜 약해?", "앞으로 어떻게 될까?" 같은 질문에는 다음 순서를 따라:
1. get_historical_exchange_rate로 실제 추이를 확인해. 질문에 기간이 없으면 최근 1개월.
2. tavily_search로 관련 뉴스를 검색해. topic은 "news"로, time_range는 확인한 기간에 맞게 지정해.
3. 아래 형식으로 답해:
   ### 📊 환율 데이터
   기간, 시작 → 끝 값, 변동률, 최고·최저
   ### 📰 주요 원인
   뉴스에서 찾은 원인 2~4개. 항목마다 [기사 제목](링크) 형식으로 출처를 달아.
   ### 💡 요약
   한두 문장으로 정리
4. 뉴스 내용과 실제 데이터 방향이 맞지 않으면 그 점을 솔직하게 밝혀.
5. 마지막 줄에 "※ 참고용 정보이며 투자 판단의 근거로 사용하지 마세요."를 붙여.
"""


# 날짜가 바뀌면 오늘 날짜가 들어간 프롬프트로 에이전트를 새로 만든다 (today가 캐시 키 역할)
@st.cache_resource
def get_agent(today: str):
    model = init_chat_model("gpt-5.4-mini")
    # topic을 여기서 지정하면 모델이 "news"로 바꿀 수 없어서 지정하지 않음 (기본값 general)
    tavily_tool = TavilySearch(max_results=5)
    return create_agent(
        model,
        tools=[tavily_tool, get_exchange_rate, get_historical_exchange_rate],
        system_prompt=SYSTEM_PROMPT.format(today=today),
    )

agent = get_agent(str(date.today()))

st.title("환율 안내 챗봇")

# 세션에 messages 저장공간 만들기 (처음 실행 시 1회만 생성)
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("무엇을 도와드릴까요?")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 답변 말풍선 안에서 로딩 표시
    with st.chat_message("assistant"):
        with st.spinner("답변을 생성하는 중..."):
            response = agent.invoke({"messages": st.session_state.messages})
        answer = response["messages"][-1].content
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
