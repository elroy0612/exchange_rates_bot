import requests
import streamlit as st

from api import API_URL, currency_label, get_currencies, get_session


@st.cache_data(ttl=60 * 60 * 3)  # 환율은 하루 한 번 갱신되므로 3시간 동안 재사용
def get_latest_rates(base):
    """기준 통화 1단위에 대한 모든 통화의 최신 환율을 한 번에 가져온다.
    대상 통화나 금액을 바꿔도 API를 다시 부르지 않고 이 결과로 계산한다."""
    res = get_session().get(f"{API_URL}/latest", params={"from": base}, timeout=10)
    res.raise_for_status()
    return res.json()  # {"base": "USD", "date": "2026-10-30", "rates": {"KRW": 1335.27, ...}}


def fmt(x):
    """숫자를 보기 좋게: 133,527.00 → 133,527 / 294.40 → 294.4
    1보다 작은 값(예: 1원 = 0.000749달러)은 소수점을 더 많이 보여 준다."""
    text = f"{x:,.2f}" if abs(x) >= 1 else f"{x:,.6f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def parse_amount(text):
    """입력한 글자를 숫자로 바꾼다. 쉼표는 무시하고 소수점 둘째 자리에서 반올림. 숫자가 아니면 None."""
    try:
        return round(float(text.replace(",", "")), 2)
    except ValueError:
        return None


def normalize_amount():
    """금액을 입력하고 엔터를 누르면 입력칸의 글자를 보기 좋게 바꾼다.
    예: 1234.567 → 1,234.57 / 100.00 → 100"""
    value = parse_amount(st.session_state.calc_amount)
    if value is not None:
        st.session_state.calc_amount = f"{value:,.2f}".rstrip("0").rstrip(".")


def swap_currencies():
    """⇄ 버튼: 두 selectbox의 값을 서로 바꾼다.
    위젯 값은 위젯이 그려지기 전에만 바꿀 수 있어서, 버튼의 on_click 콜백에서 처리한다."""
    st.session_state.calc_from, st.session_state.calc_to = (
        st.session_state.calc_to,
        st.session_state.calc_from,
    )


st.title("🧮 환율 계산기")

try:
    codes = list(get_currencies().keys())
except requests.RequestException as e:
    st.error(f"통화 목록을 불러오지 못했어요: {e}")
    st.stop()

# 처음 들어왔을 때 기본값 (USD → KRW)
st.session_state.setdefault("calc_from", "USD")
st.session_state.setdefault("calc_to", "KRW")

# 첫째 줄: 기준 통화 | ⇄ | 대상 통화
col_from, col_swap, col_to = st.columns([4, 1, 4], vertical_alignment="bottom")
with col_from:
    base = st.selectbox("기준 통화", codes, key="calc_from", format_func=currency_label)
with col_swap:
    st.button("⇄", on_click=swap_currencies, width="stretch", help="두 통화 바꾸기")
with col_to:
    target = st.selectbox("대상 통화", codes, key="calc_to", format_func=currency_label)

# 둘째 줄: 금액
# number_input 대신 text_input을 써서 +/- 버튼과 강제 소수점(.00) 표시를 없앰
st.session_state.setdefault("calc_amount", "100")
st.text_input(
    f"금액 ({base})",
    key="calc_amount",
    icon="💰",
    placeholder="금액을 입력하세요",
    on_change=normalize_amount,
    validate=(r"^\s*[0-9][0-9,]*(\.[0-9]*)?\s*$", "숫자만 입력할 수 있어요. 예: 1,000 또는 12.5"),
)
amount = parse_amount(st.session_state.calc_amount)

# 금액 칸에서 엔터를 누르면 입력칸에서 커서를 빼서(blur) 깜빡이는 커서가 사라지게 한다.
# Streamlit에 없는 기능이라 JavaScript로 처리 (window 플래그로 한 번만 등록)
# (스크립트가 든 빈 칸이 화면에 공간을 차지하지 않도록 style로 숨김)
st.html(
    """
    <style>[data-testid='stElementContainer']:has(script) { display: none; }</style>
    <script>
    if (!window.__calcAmountBlur) {
        window.__calcAmountBlur = true;
        document.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && e.target.closest(".st-key-calc_amount")) {
                setTimeout(() => e.target.blur(), 0);
            }
        });
    }
    </script>
    """,
    unsafe_allow_javascript=True,
)

if amount is None:
    st.info("금액을 입력하세요.")
    st.stop()

if base == target:
    st.warning("서로 다른 통화를 선택하세요.")
    st.stop()

try:
    data = get_latest_rates(base)
except requests.RequestException as e:
    st.error(f"환율을 불러오지 못했어요: {e}")
    st.stop()

rate = data["rates"][target]  # 1 base = rate target
result = amount * rate

# 결과
st.divider()
st.markdown(f"### {fmt(amount)} {base} = **{fmt(result)} {target}**")
st.caption(
    f"1 {base} = {fmt(rate)} {target}  ·  1 {target} = {fmt(1 / rate)} {base}  ·  "
    f"기준일: {data['date']} (ECB / Frankfurter)"
)
