import uuid
import aiofiles
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_authorized_module, get_user_id
from config import settings
from database import get_db
from models import Module
from schemas.module_responses import ModuleDetail, ModuleListItem, ModuleUploadResponse
from services.background_job_limits import JobLimitExceeded, module_parse_limiter
from services.langgraph_client import langgraph_client as dify_client
from services.local_rag_uploader import rag_uploader
from services.module_parser import extract_text, get_file_type, is_allowed_file, truncate_text

router = APIRouter(prefix="/modules", tags=["modules"])


@router.post("/upload", response_model=ModuleUploadResponse)
async def upload_module(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    if not is_allowed_file(file.filename):
        raise HTTPException(400, "unsupported file type")

    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(400, f"file too large, max {settings.max_upload_mb}MB")

    try:
        parse_reservation = module_parse_limiter.reserve(
            max_backlog=settings.module_parse_max_backlog,
        )
    except JobLimitExceeded as exc:
        raise HTTPException(429, exc.detail) from exc

    file_type = get_file_type(file.filename)
    file_id = str(uuid.uuid4())
    save_name = f"{file_id}.{file_type}"
    save_path = Path(settings.upload_dir) / save_name

    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    module = Module(
        id=file_id,
        user_id=user_id,
        name=Path(file.filename).stem,
        file_path=str(save_path),
        file_type=file_type,
        parse_status="processing",
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)

    background_tasks.add_task(
        _parse_module_bg,
        file_id,
        str(save_path),
        file_type,
        parse_reservation,
    )

    return {"id": module.id, "name": module.name, "status": "processing"}


async def _parse_module_bg(module_id: str, file_path: str, file_type: str, parse_reservation=None):
    import logging

    logger = logging.getLogger(__name__)
    from database import AsyncSessionLocal

    try:
        if parse_reservation is not None:
            await parse_reservation.acquire_run_slot(
                max_concurrent=settings.module_parse_max_concurrent,
            )
        async with AsyncSessionLocal() as db:
            try:
                text = await extract_text(file_path, file_type)
                text = truncate_text(text)

                parsed, rag_chunks = await dify_client.parse_module(text)
                print(
                    f"[BG] module {module_id}: parsed keys={list(parsed.keys())[:5]}, "
                    f"monsters={len(parsed.get('monsters', []))}, chunks={len(rag_chunks)}",
                    flush=True,
                )

                result = await db.execute(select(Module).where(Module.id == module_id))
                module = result.scalar_one_or_none()
                if module:
                    module.parsed_content = parsed
                    module.level_min = parsed.get("level_min", 1)
                    module.level_max = parsed.get("level_max", 5)
                    module.recommended_party_size = parsed.get("recommended_party_size", 4)
                    module.parse_status = "done"
                    await db.commit()

                if rag_chunks:
                    try:
                        uploaded = await rag_uploader.upload_module_chunks(module_id, rag_chunks)
                        logger.info("module %s: uploaded %s RAG chunks", module_id, uploaded)
                    except Exception as rag_err:
                        logger.warning(
                            "module %s: RAG upload failed without blocking module use: %s",
                            module_id,
                            rag_err,
                        )

            except Exception as e:
                logger.error("module %s: parse failed: %s", module_id, e, exc_info=True)
                result = await db.execute(select(Module).where(Module.id == module_id))
                module = result.scalar_one_or_none()
                if module:
                    module.parse_status = "failed"
                    module.parse_error = str(e)
                    await db.commit()
    finally:
        if parse_reservation is not None:
            parse_reservation.release()


@router.get("/", response_model=list[ModuleListItem])
async def list_modules(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    result = await db.execute(
        select(Module).where(Module.user_id == user_id).order_by(Module.created_at.desc())
    )
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


@router.get("/{module_id}", response_model=ModuleDetail)
async def get_module(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    module = await get_authorized_module(module_id, db, user_id)
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
async def delete_module(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    module = await get_authorized_module(module_id, db, user_id, require_owner=True)

    file_path = Path(module.file_path)
    if module.file_path and file_path.exists():
        file_path.unlink()

    await db.delete(module)
    await db.commit()

    try:
        await rag_uploader.delete_module_chunks(module_id)
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning("RAG cleanup failed for module %s: %s", module_id, e)

    return {"ok": True}
