"""
用户认证路由 — 注册 / 登录 / JWT 鉴权
"""
import jwt
import bcrypt
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models.user import User
from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = settings.llm_api_key[:32] + "_jwt_secret"  # 用 API key 前缀派生
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7


# ── Schemas ──────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str
    user_id: str
    username: str
    display_name: str


# ── JWT 工具 ─────────────────────────────────────────

def create_token(user_id: str, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的认证令牌")


# ── 密码哈希 ─────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── Endpoints ────────────────────────────────────────

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户"""
    if len(req.username) < 2 or len(req.username) > 30:
        raise HTTPException(400, "用户名长度需要 2-30 个字符")
    if len(req.password) < 4:
        raise HTTPException(400, "密码长度至少 4 个字符")

    # 检查用户名是否已存在
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "用户名已被注册")

    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name or req.username,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_token(user.id, user.username)
    return TokenResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")

    token = create_token(user.id, user.username)
    return TokenResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
    )


@router.get("/me")
async def get_current_user_info(user: dict = Depends(lambda: None)):
    """获取当前用户信息（需要在 header 中带 token）"""
    # 实际由 get_current_user 依赖处理
    pass
