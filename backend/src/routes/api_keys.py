# API Keys Routes
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from ..config.database import get_db
from ..models.models import ApiKey, User
from ..middleware.auth import get_current_user

router = APIRouter()


class ApiKeyCreate(BaseModel):
    name: str
    provider: str
    key: str


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    provider: str
    key: str  # 已脱敏
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的所有API Key"""
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id)
    )
    keys = result.scalars().all()
    
    # 脱敏处理
    for key in keys:
        if len(key.key) > 8:
            key.key = key.key[:8] + "****"
    
    return keys


@router.post("", response_model=ApiKeyResponse)
async def create_api_key(
    data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新的API Key"""
    api_key = ApiKey(
        name=data.name,
        provider=data.provider,
        key=data.key,
        user_id=current_user.id
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    # 脱敏返回
    api_key.key = api_key.key[:8] + "****"
    return api_key


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除API Key"""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="API Key不存在")
    
    await db.delete(api_key)
    await db.commit()
    
    return {"success": True}


@router.patch("/{key_id}/activate")
async def activate_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """激活API Key"""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="API Key不存在")
    
    # 停用其他Key
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id)
    )
    for key in result.scalars().all():
        key.is_active = (key.id == key_id)
    
    await db.commit()
    
    return {"success": True}
