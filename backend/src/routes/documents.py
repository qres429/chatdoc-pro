from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import os
import uuid

from ..config.database import get_db
from ..config.settings import settings
from ..models.models import User, Document
from ..middleware.auth import get_current_user

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class DocumentResponse(BaseModel):
    id: int
    name: str
    file_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    documents: List[DocumentResponse]
    total: int


@router.get("/", response_model=DocumentList)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取文档列表"""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    documents = result.scalars().all()
    
    # 获取总数
    result = await db.execute(
        select(Document).where(Document.user_id == current_user.id)
    )
    total = len(result.scalars().all())
    
    return {"documents": documents, "total": total}


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传文档"""
    # 检查文件类型
    allowed_types = ["pdf", "docx", "doc", "txt"]
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(status_code=400, detail="不支持的文件类型")
    
    # 保存文件
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.{file_ext}")
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 提取文本内容
    text_content = ""
    if file_ext == "txt":
        text_content = content.decode("utf-8", errors="ignore")
    elif file_ext == "pdf":
        # 简化处理，实际应使用 PyPDF2
        text_content = f"[PDF文档: {file.filename}]"
    elif file_ext in ["docx", "doc"]:
        text_content = f"[Word文档: {file.filename}]"
    
    # 创建文档记录
    document = Document(
        name=file.filename,
        file_type=file_ext,
        file_path=file_path,
        content=text_content,
        user_id=current_user.id
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    return document


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个文档"""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return document


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除文档"""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 删除文件
    if document.file_path and os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    await db.delete(document)
    await db.commit()
    
    return {"success": True, "message": "文档已删除"}
