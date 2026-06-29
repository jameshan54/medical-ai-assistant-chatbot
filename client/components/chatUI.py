import streamlit as st
from utils.api import ask_question


def render_chat():
    st.subheader("💬 Chat with your assistant")

    code = st.session_state.get("participant_code", "P001")
    st.caption(f"Query target: **{code}**")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            tools_used = msg.get("tools_used", [])
            if tools_used:
                st.caption(f"Tools: {', '.join(tools_used)}")

    user_input = st.chat_input("Type your question....")
    if user_input:
        st.chat_message("user").markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        response = ask_question(user_input, participant_code=code)

        if response.status_code == 200:
            data = response.json()
            answer = data["response"]
            tools_used = data.get("tools_used", [])
            with st.chat_message("assistant"):
                st.markdown(answer)
                if tools_used:
                    st.caption(f"Tools: {', '.join(tools_used)}")
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "tools_used": tools_used,
            })
        else:
            st.error(f"Error: {response.text}")