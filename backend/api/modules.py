import uuid
import aiofiles
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import Module
from config import settings
from services.module_parser import extract_text, get_file_type, is_allowed_file, truncate_text
from services.langgraph_client import langgraph_client as dify_client
from services.local_rag_uploader import rag_uploader
from api.deps import get_user_id

router = APIRouter(prefix="/modules", tags=["modules"])


@router.post("/upload")
async def upload_module(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """上传模组文件，异步解析"""
    if not is_allowed_file(file.filename):
        raise HTTPException(400, "不支持的文件格式，请上传 PDF / DOCX / MD / TXT")

    # 检查文件大小
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(400, f"文件过大，最大支持 {settings.max_upload_mb}MB")

    # 保存文件
    file_type = get_file_type(file.filename)
    file_id = str(uuid.uuid4())
    save_name = f"{file_id}.{file_type}"
    save_path = Path(settings.upload_dir) / save_name

    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    # 去掉扩展名作为模组名
    module_name = Path(file.filename).stem

    # 创建数据库记录
    module = Module(
        id=file_id,
        user_id=user_id,
        name=module_name,
        file_path=str(save_path),
        file_type=file_type,
        parse_status="processing",
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)

    # 后台解析
    background_tasks.add_task(_parse_module_bg, file_id, str(save_path), file_type)

    return {"id": module.id, "name": module.name, "status": "processing"}


async def _parse_module_bg(module_id: str, file_path: str, file_type: str):
    """后台任务：提取文本 → LangGraph WF1 → 更新数据库 → 上传 RAG chunks"""
    import logging
    logger = logging.getLogger(__name__)
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            text = await extract_text(file_path, file_type)
            text = truncate_text(text)
            logger.info(f"模组 {module_id}: 文本提取完成, {len(text)} 字符, 开始 AI 解析...")

            # WF1 返回 (module_data_dict, rag_chunks_list)
            parsed, rag_chunks = await dify_client.parse_module(text)
            print(f"[BG] 模组 {module_id}: parsed keys={list(parsed.keys())[:5]}, monsters={len(parsed.get('monsters',[]))}, chunks={len(rag_chunks)}", flush=True)
            logger.info(f"模组 {module_id}: AI 解析完成, parsed keys={list(parsed.keys())[:5]}, chunks={len(rag_chunks)}")

            result = await db.execute(select(Module).where(Module.id == module_id))
            module = result.scalar_one_or_none()
            if module:
                module.parsed_content = parsed
                module.level_min = parsed.get("level_min", 1)
                module.level_max = parsed.get("level_max", 5)
                module.recommended_party_size = parsed.get("recommended_party_size", 4)
                module.parse_status = "done"
                await db.commit()
                logger.info(f"模组 {module_id}: 数据库更新完成")

            # 上传 RAG chunks 到 Dify Knowledge Base（失败不影响主流程）
            if rag_chunks:
                try:
                    uploaded = await rag_uploader.upload_module_chunks(module_id, rag_chunks)
                    import logging
                    logging.getLogger(__name__).info(
                        f"模组 {module_id}: RAG 上传完成，共 {uploaded} 个 chunks"
                    )
                except Exception as rag_err:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"模组 {module_id}: RAG 上传失败（不影响模组使用）: {rag_err}"
                    )

        except Exception as e:
            logger.error(f"模组 {module_id}: 解析失败: {e}", exc_info=True)
            result = await db.execute(select(Module).where(Module.id == module_id))
            module = result.scalar_one_or_none()
            if module:
                module.parse_status = "failed"
                module.parse_error = str(e)
                await db.commit()


@router.get("/")
async def list_modules(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_user_id)):
    """获取当前用户的模组列表"""
    result = await db.execute(select(Module).where(Module.user_id == user_id).order_by(Module.created_at.desc()))
    modules = result.scalars().all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "file_type": m.file_type,
            "parse_status": m.parse_status,
            "level_min": m.level_min,
            "level_max": m.level_max,
            "recommended_party_size": m.recommended_party_size,
            "setting": (m.parsed_content or {}).get("setting", ""),
            "tone": (m.parsed_content or {}).get("tone", ""),
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in modules
    ]


@router.get("/{module_id}")
async def get_module(module_id: str, db: AsyncSession = Depends(get_db)):
    """获取模组详情"""
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, "模组不存在")
    return {
        "id": module.id,
        "name": module.name,
        "file_type": module.file_type,
        "parse_status": module.parse_status,
        "parse_error": module.parse_error,
        "level_min": module.level_min,
        "level_max": module.level_max,
        "recommended_party_size": module.recommended_party_size,
        "parsed_content": module.parsed_content,
        "created_at": module.created_at.isoformat() if module.created_at else None,
    }


@router.delete("/{module_id}")
async def delete_module(module_id: str, db: AsyncSession = Depends(get_db)):
    """删除模组"""
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(404, "模组不存在")

    # 删除文件
    file_path = Path(module.file_path)
    if file_path.exists():
        file_path.unlink()

    await db.delete(module)
    await db.commit()

    # 清理 Dify Knowledge Base 中的对应 chunks（异步，失败不影响主流程）
    try:
        await rag_uploader.delete_module_chunks(module_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"清理模组 RAG chunks 失败: {e}")

    return {"ok": True}
