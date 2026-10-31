import requests
import streamlit as st
from langchain.tools import tool
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

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
        res = requests.get(
            "https://api.frankfurter.app/latest",
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
    

@st.cache_resource
def get_agent():
    model = init_chat_model("gpt-5.4-mini")
    tavily_tool = TavilySearch(max_results=5, topic="general")
    return create_agent(
        model,
        tools=[tavily_tool, get_exchange_rate],   # 환율 도구도 여기에
        system_prompt="너는 환율 안내 챗봇이야. 환율·환전 질문에는 반드시 get_exchange_rate 도구를 사용해.",
    )

agent = get_agent()

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