"""
HTTP 响应体 Pydantic schemas — 模组（modules）相关端点。

放独立文件避免 game_responses.py 越来越胖。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ModuleListItem(BaseModel):
    """对应 GET /modules/ 列表的每一项。"""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    file_type: str
    parse_status: str
    level_min: int = 1
    level_max: int = 5
    recommended_party_size: int = 4
    setting: str = ""
    tone: str = ""
    created_at: Optional[str] = None


class ModuleDetail(BaseModel):
    """对应 GET /modules/{id}。parsed_content 形状由 LangGraph WF1 决定，allow extra。"""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    file_type: str
    parse_status: str
    parse_error: Optional[str] = None
    level_min: int = 1
    level_max: int = 5
    recommended_party_size: int = 4
    parsed_content: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


class ModuleUploadResponse(BaseModel):
    """对应 POST /modules/upload。status 为 'processing' / 'done' / 'failed'。"""
    id: str
    name: str
    status: str


__all__ = ["ModuleListItem", "ModuleDetail", "ModuleUploadResponse"]
