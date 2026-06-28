import requests
from config import API_URL


def upload_pdfs_api(files):
    files_payload=[ ("files",(f.name,f.read(),"application/pdf")) for f in files]
    return requests.post(f"{API_URL}/upload_pdfs/",files=files_payload)

def ask_question(question):
    return requests.post(f"{API_URL}/ask/",data={"question":question})

def upload_csv_api(file, participant_code="P001"):
    return requests.post(
        f"{API_URL}/upload_csv/",
        files={"file": (file.name, file.read(), "text/csv")},
        data={"participant_code": participant_code},
    )