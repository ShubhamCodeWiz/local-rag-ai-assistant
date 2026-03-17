from fastapi import FastAPI, UploadFile, File
from pypdf import PdfReader
import io
import chromadb
import ollama # Import the interface to the AI Brain

app = FastAPI()

chroma_client = chromadb.PersistentClient(path="./chroma_db") 
collection = chroma_client.get_or_create_collection(name="pdf_chat")

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    content = await file.read()
    stream = io.BytesIO(content)
    pdf = PdfReader(stream)
    text_content = ""
    for page in pdf.pages:
        text_content += page.extract_text()

    chunk_size = 1000
    chunks = []
    for i in range(0, len(text_content), chunk_size):
        chunks.append(text_content[i:i+chunk_size])
        
    chunk_ids = [f"chunk_{i}" for i in range(len(chunks))]
    
    collection.add(
        documents=chunks,
        ids=chunk_ids,
        metadatas=[{"source": file.filename} for _ in chunks]
    )
    return {"filename": file.filename, "chunks_added": len(chunks)}

@app.get("/query")
def query_documents(question: str):
    # 1. Search DB for relevant chunks
    results = collection.query(
        query_texts=[question],
        n_results=1 # Let's just get the #1 best chunk for now
    )

    context = "No relevant context found."
    if results and "documents" in results and results['documents']:
        context = results['documents'][0][0] # The text of the best chunk
    
    # 2. Construct the Prompt for the AI
    # We tell the AI: "Here is some context. Use it to answer the question."
    prompt = f"""
    You are a helpful assistant. Answer the question based ONLY on the following context:
    
    CONTEXT:
    {context}
    
    QUESTION:
    {question}
    """
    
    # 3. Send to Ollama (The Brain)
    # 'model' must match what you installed (llama3.2, mistral, etc.)
    response = ollama.chat(model='tinyllama', messages=[
        {'role': 'user', 'content': prompt},
    ])
    
    # 4. Extract the answer
    ai_answer = response['message']['content']
    
    return {"question": question, "answer": ai_answer, "context_used": context}