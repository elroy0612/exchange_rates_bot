import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# 한글 줄바꿈을 글자 단위가 아니라 단어(띄어쓰기) 단위로 (모든 페이지에 적용)
# - Streamlit이 문단(<p>)마다 word-break를 따로 지정하므로, 안쪽 요소 전체(*)에 !important로 덮어씀
# - overflow-wrap: 긴 URL처럼 한 단어가 너무 길 때만 중간에서 줄바꿈
# (st.html에 <style>만 넣으면 화면에 빈 공간을 차지하지 않음)
st.html("""
<style>
[data-testid='stMarkdownContainer'] *,
[data-testid='stCaptionContainer'] * {  /* st.caption(작은 글씨)은 별도 컨테이너를 씀 */
    word-break: keep-all !important;
    overflow-wrap: break-word;
}
</style>
""")

home = st.Page("home.py", title="홈", icon="🏠", default=True)
page_1 = st.Page("page1.py", title="환율 챗봇", icon="💬")
page_2 = st.Page("page2.py", title="환율 차트", icon="📈")
page_3 = st.Page("page3.py", title="환율 계산기", icon="🧮")

pages = st.navigation({
    "메인": [home],
    "기능": [page_1, page_2, page_3],
})

pages.run()
