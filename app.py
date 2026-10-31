import streamlit as st
from dotenv import load_dotenv

load_dotenv()

home = st.Page("home.py", title="홈", icon="🏠", default=True)
page_1 = st.Page("page1.py", title="환율 챗봇", icon="💬")
page_2 = st.Page("page2.py", title="환율 차트", icon="📈")

pages = st.navigation({
    "메인": [home],
    "기능": [page_1, page_2],
})

pages.run()
