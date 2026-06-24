import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from tqdm.auto import tqdm
from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "medicalindex")

if GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

UPLOAD_DIR = "./uploaded_docs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize Pinecone instance
pc = Pinecone(api_key=PINECONE_API_KEY)
spec = ServerlessSpec(cloud="aws", region=PINECONE_ENV)
existing_indexes = [i["name"] for i in pc.list_indexes()]

if PINECONE_INDEX_NAME not in existing_indexes:
    pc.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=3072,
        metric="dotproduct",
        spec=spec,
    )
    while not pc.describe_index(PINECONE_INDEX_NAME).status["ready"]:
        time.sleep(1)

index = pc.Index(PINECONE_INDEX_NAME)


def load_vectorstore(uploaded_files):
    """Save uploaded PDFs, split them into chunks, embed chunks, and upsert to Pinecone.

    Important evaluation metadata stored per chunk:
    - source: clean PDF filename
    - page: original 0-based page index from PyPDFLoader
    - page_number: human-friendly 1-based page number
    - chunk_id: chunk number within that PDF
    - vector_id: Pinecone vector ID
    - text: exact chunk text used for retrieval/generation
    """
    embed_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    file_paths = []

    # 1. Upload files to server
    for file in uploaded_files:
        save_path = Path(UPLOAD_DIR) / file.filename
        with open(save_path, "wb") as f:
            f.write(file.file.read())
        file_paths.append(str(save_path))

    # 2. Load, split, embed, and upsert each PDF
    for file_path in file_paths:
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
        )
        chunks = splitter.split_documents(documents)

        texts = [chunk.page_content for chunk in chunks]
        clean_source = Path(file_path).name
        safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(file_path).stem)[:50]

        ids = [f"{safe_stem}-{i}" for i in range(len(chunks))]

        metadatas = []
        for i, chunk in enumerate(chunks):
            raw_page = chunk.metadata.get("page")
            page_number = raw_page + 1 if isinstance(raw_page, int) else raw_page

            metadatas.append({
                **chunk.metadata,
                "source": clean_source,
                "page_number": page_number,
                "chunk_id": i,
                "vector_id": ids[i],
                "text": chunk.page_content,
            })

        # 3. Embedding
        print(f"🔍 Embedding {len(texts)} chunks from {clean_source}...")
        embeddings = []
        batch_size = 80
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = embed_model.embed_documents(batch)
            embeddings.extend(batch_embeddings)
            if i + batch_size < len(texts):
                time.sleep(30)

        # 4. Upsert to Pinecone
        print("📤 Uploading to Pinecone...")
        vectors = list(zip(ids, embeddings, metadatas))
        with tqdm(total=len(vectors), desc="Upserting to Pinecone") as progress:
            index.upsert(vectors=vectors)
            progress.update(len(vectors))

        print(f"✅ Upload complete for {file_path}")
