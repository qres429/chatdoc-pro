from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import json
import asyncio

from ..config.database import get_db
from ..config.settings import settings
from ..models.models import User, Conversation, Message, Document
from ..middleware.auth import get_current_user

router = APIRouter()


class MessageCreate(BaseModel):
    content: str
    conversation_id: Optional[int] = None


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    messages: List[MessageResponse] = []
    
    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    document_ids: Optional[List[int]] = None


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取对话列表"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.post("/send")
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """发送消息并获取AI回复"""
    
    # 获取或创建对话
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == current_user.id
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")
    else:
        conversation = Conversation(
            title=request.message[:50],
            user_id=current_user.id
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
    
    # 保存用户消息
    user_message = Message(
        role="user",
        content=request.message,
        conversation_id=conversation.id
    )
    db.add(user_message)
    await db.commit()
    
    # 获取文档上下文
    context = ""
    if request.document_ids:
        result = await db.execute(
            select(Document).where(Document.id.in_(request.document_ids))
        )
        docs = result.scalars().all()
        context = "\n\n".join([f"文档: {d.name}\n{d.content[:1000]}" for d in docs])
    
    # 生成AI回复（使用真实的OpenAI API）
    ai_response = await generate_ai_response(request.message, context)
    
    # 保存AI消息
    assistant_message = Message(
        role="assistant",
        content=ai_response,
        conversation_id=conversation.id
    )
    db.add(assistant_message)
    await db.commit()
    
    return {
        "conversation_id": conversation.id,
        "message": ai_response
    }


async def generate_ai_response(question: str, context: str = "") -> str:
    """生成AI回复"""
    try:
        from openai import AsyncOpenAI
        
        if not settings.OPENAI_API_KEY:
            return "请配置 OPENAI_API_KEY 环境变量"
        
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        system_prompt = "你是一个专业的文档分析助手，帮助用户理解文档内容并回答问题。"
        if context:
            system_prompt += f"\n\n参考文档内容：\n{context}"
        
        response = await client.chat.completions.create(
            model=settings.DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"AI回复生成失败: {str(e)}"


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取对话详情"""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
        .options(selectinload(Conversation.messages))
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除对话"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    await db.delete(conversation)
    await db.commit()
    
    return {"success": True}
