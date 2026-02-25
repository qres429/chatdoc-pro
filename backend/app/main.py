from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import sqlite3
import hashlib

app = FastAPI(title="ChatDoc Pro API")

# CORS配置 - 仅允许特定域名
ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# 数据库初始化
def init_db():
    conn = sqlite3.connect('chatdoc.db')
    c = conn.cursor()
    
    # 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
    
    # 文档表
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, 
                  content TEXT, vector_ids TEXT, uploaded_at TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    # 对话表
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (id INTEGER PRIMARY KEY, user_id INTEGER, doc_id INTEGER,
                  role TEXT, content TEXT, created_at TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(id),
                  FOREIGN KEY(doc_id) REFERENCES documents(id))''')
    
    # API Key表
    c.execute('''CREATE TABLE IF NOT EXISTS api_keys
                 (id INTEGER PRIMARY KEY, user_id INTEGER, key TEXT,
                  model TEXT, created_at TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()

init_db()

# 依赖
def get_db():
    conn = sqlite3.connect('chatdoc.db')
    conn.row_factory = sqlite3.Row
    return conn

class User(BaseModel):
    username: str
    password: str

class Question(BaseModel):
    doc_id: int
    question: str
    api_key: str
    model: str = "gpt-3.5-turbo"

class ApiKey(BaseModel):
    key: str
    model: str = "gpt-3.5-turbo"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@app.get("/")
def root():
    return {"message": "ChatDoc Pro API v2.0", "status": "running"}

# 用户认证
@app.post("/register")
def register(user: User):
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                    (user.username, hash_password(user.password)))
        conn.commit()
        return {"message": "User registered"}
    except sqlite3.IntegrityError:
        return {"error": "Username exists"}
    finally:
        conn.close()

@app.post("/login")
def login(user: User):
    conn = get_db()
    cur = conn.execute("SELECT id FROM users WHERE username=? AND password=?",
                       (user.username, hash_password(user.password)))
    result = cur.fetchone()
    conn.close()
    if result:
        return {"token": f"user_{result[0]}", "user_id": result[0]}
    return {"error": "Invalid credentials"}

# 文档管理
@app.get("/documents")
def list_documents(user_id: int):
    conn = get_db()
    cur = conn.execute("SELECT * FROM documents WHERE user_id=?", (user_id,))
    docs = [dict(row) for row in cur.fetchall()]
    conn.close()
    return docs

@app.post("/documents")
async def upload_document(file: UploadFile = File(...), user_id: int = 1):
    content = await file.read()
    
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO documents (user_id, name, content, uploaded_at) VALUES (?, ?, ?, ?)",
        (user_id, file.filename, content.decode('utf-8', errors='ignore'), datetime.now().isoformat())
    )
    doc_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    return {"id": doc_id, "name": file.filename, "message": "Document uploaded"}

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int, user_id: int = 1):
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE id=? AND user_id=?", (doc_id, user_id))
    conn.commit()
    conn.close()
    return {"message": "Document deleted"}

# AI问答
@app.post("/chat")
def ask_question(question: Question, user_id: int = 1):
    conn = get_db()
    
    # 获取文档
    cur = conn.execute("SELECT * FROM documents WHERE id=?", (question.doc_id,))
    doc = cur.fetchone()
    if not doc:
        conn.close()
        return {"error": "Document not found"}
    
    # 实际API调用示例（需要真实API Key）
    # 这里使用模拟响应，生产环境应调用OpenAI/Claude API
    if question.api_key and question.api_key.startswith("sk-"):
        # 真实API调用逻辑
        answer = f"基于文档《{doc['name']}》的回答：\n\n{question.question}\n\n[这是AI的智能回答，包含对文档内容的分析和总结...]"
    else:
        # 无API Key时的提示
        answer = f"基于文档《{doc['name']}》的回答：\n\n请配置有效的API Key以获取AI回答。\n\n文档内容摘要：{doc['content'][:500]}..."
    
    # 保存对话
    conn.execute(
        "INSERT INTO conversations (user_id, doc_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, question.doc_id, 'user', question.question, datetime.now().isoformat())
    )
    conn.execute(
        "INSERT INTO conversations (user_id, doc_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, question.doc_id, 'assistant', answer, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    return {"answer": answer, "sources": [doc['name']]}

# 对话历史
@app.get("/conversations/{doc_id}")
def get_conversations(doc_id: int, user_id: int = 1):
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM conversations WHERE user_id=? AND doc_id=? ORDER BY created_at",
        (user_id, doc_id)
    )
    msgs = [dict(row) for row in cur.fetchall()]
    conn.close()
    return msgs

# API Key管理
@app.post("/api-keys")
def save_api_key(api_key: ApiKey, user_id: int = 1):
    conn = get_db()
    conn.execute(
        "INSERT INTO api_keys (user_id, key, model, created_at) VALUES (?, ?, ?, ?)",
        (user_id, api_key.key, api_key.model, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"message": "API Key saved"}

@app.get("/api-keys")
def list_api_keys(user_id: int = 1):
    conn = get_db()
    cur = conn.execute("SELECT id, model, created_at FROM api_keys WHERE user_id=?", (user_id,))
    keys = [dict(row) for row in cur.fetchall()]
    conn.close()
    return keys

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
