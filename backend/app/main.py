from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import json
from datetime import datetime

app = FastAPI(title="ChatDoc Pro API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (replace with database in production)
documents = []
conversations = {}
api_keys = {}

class Question(BaseModel):
    doc_id: str
    question: str
    api_key: Optional[str] = None
    model: Optional[str] = "gpt-3.5-turbo"

class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []

@app.get("/")
def root():
    return {"message": "ChatDoc Pro API", "version": "1.0.0"}

@app.get("/documents")
def list_documents():
    return documents

@app.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    # Save file
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Create document record
    doc = {
        "id": str(len(documents) + 1),
        "name": file.filename,
        "path": file_path,
        "size": len(content),
        "uploaded_at": datetime.now().isoformat()
    }
    documents.append(doc)
    
    return {"message": "Document uploaded", "document": doc}

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    global documents
    documents = [d for d in documents if d["id"] != doc_id]
    return {"message": "Document deleted"}

@app.post("/chat", response_model=ChatResponse)
def ask_question(question: Question):
    # Find document
    doc = next((d for d in documents if d["id"] == question.doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Mock AI response (replace with actual RAG implementation)
    answer = f"基于文档《{doc['name']}》的回答：\n\n这是对您问题「{question.question}」的回答。\n\n在实际实现中，这里会调用RAG系统检索文档相关内容并生成答案。"
    
    return ChatResponse(
        answer=answer,
        sources=[doc["name"]]
    )

@app.get("/conversations/{doc_id}")
def get_conversation(doc_id: str):
    return conversations.get(doc_id, [])

@app.post("/conversations/{doc_id}")
def save_conversation(doc_id: str, message: dict):
    if doc_id not in conversations:
        conversations[doc_id] = []
    conversations[doc_id].append(message)
    return {"message": "Saved"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
