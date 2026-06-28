import streamlit as st
from utils.api import upload_pdfs_api, upload_csv_api


def render_uploader():
    st.sidebar.header("Upload Medical documents (.PDFs)")
    uploaded_files = st.sidebar.file_uploader(
        "Upload multiple PDFs", type="pdf", accept_multiple_files=True
    )
    if st.sidebar.button("Upload DB") and uploaded_files:
        response = upload_pdfs_api(uploaded_files)
        if response.status_code == 200:
            st.sidebar.success("Uploaded successfully")
        else:
            st.sidebar.error(f"Error:{response.text}")

    st.sidebar.divider()
    st.sidebar.header("Upload HRV CSV")
    participant_code = st.sidebar.text_input(
        "Participant code",
        value=st.session_state.get("participant_code", "P001"),
        key="participant_code_input",
    )
    st.session_state["participant_code"] = participant_code

    csv_file = st.sidebar.file_uploader("Upload HRV CSV", type="csv")

    if st.sidebar.button("Upload CSV") and csv_file:
        response = upload_csv_api(csv_file, participant_code)
        if response.status_code == 200:
            data = response.json()
            st.session_state["participant_code"] = participant_code
            st.sidebar.success(
                f"Done: inserted={data.get('inserted')}, skipped={data.get('skipped')}"
            )
        else:
            st.sidebar.error(f"Error: {response.text}")