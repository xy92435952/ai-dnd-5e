"""
WF1 — 模组解析 LangGraph 图
4 节点线性链：extract → validate → gen_chunks → validate_chunks

长模组支持（v0.11）：
  - 文本 > 15000 字 时 extract 阶段自动按章节/字数切段，逐段调 LLM，
    合并 partial module_data（scenes 顺序 append，npcs/monsters/magic_items
    按 name+role/cr 去重）
  - chunks 阶段若 module_data 的 scenes+npcs+items 总数 > 15，按批次切分
    多次调 LLM 生成，合并；chunk_id 加批次前缀避免冲突
  - 失败重试 1 次，仍失败则跳过该段/批，记录到 _failed_segments
"""

import json
import logging
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

from services.graphs.module_parser_helpers import (
    _fill_monster_defaults,
    _merge_module_partials,
    _split_module_data_for_chunks,
    _split_module_text,
    _strip_code_block,
    _try_parse_json,
)
from services.graphs.module_parser_prompts import (
    CHUNK_SYSTEM,
    CHUNK_USER,
    EXTRACT_SYSTEM,
    EXTRACT_USER,
)
from services.llm import get_llm

logger = logging.getLogger(__name__)

# State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ModuleParserState(TypedDict):
    module_text: str
    llm_extract_output: str
    module_data: dict
    module_data_json: str
    llm_chunk_output: str
    rag_chunks: list
    error: str

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Graph nodes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _call_extract_llm(segment_text: str, segment_info: str = "") -> str:
    """单次 LLM 抽取。segment_info 用于 prompt 里标注段号。"""
    llm = get_llm(temperature=0.2, max_tokens=8000)
    user_msg = EXTRACT_USER.format(module_text=segment_text)
    if segment_info:
        user_msg = f"【{segment_info}】\n\n" + user_msg
    resp = await llm.ainvoke([
        SystemMessage(content=EXTRACT_SYSTEM + "\n\n重要：JSON字符串值中不要使用未转义的双引号，用中文引号「」代替。"),
        HumanMessage(content=user_msg),
    ])
    return resp.content


async def extract_structured_data(state: ModuleParserState) -> dict:
    module_text = state["module_text"]
    segments = _split_module_text(module_text)

    # 短模组：原逻辑
    if len(segments) == 1:
        output = await _call_extract_llm(segments[0])
        return {"llm_extract_output": output}

    # 长模组：逐段 LLM + 合并
    logger.info(
        "module_parser: 长模组分 %d 段处理（总 %d 字）",
        len(segments), len(module_text),
    )

    partials: list[dict] = []
    failed: list[int] = []
    for i, seg in enumerate(segments):
        seg_info = f"第 {i+1} 段 / 共 {len(segments)} 段"
        parsed = None
        # 最多 2 次尝试
        for attempt in range(2):
            try:
                raw = await _call_extract_llm(seg, seg_info)
                candidate = _try_parse_json(_strip_code_block(raw))
                if isinstance(candidate, dict):
                    parsed = candidate
                    break
            except Exception as e:
                logger.warning(
                    "段 %d 抽取失败（第 %d 次尝试）：%s",
                    i + 1, attempt + 1, e,
                )
        if parsed is not None:
            partials.append(parsed)
        else:
            logger.error("段 %d 两次尝试均失败，跳过", i + 1)
            failed.append(i + 1)

    if not partials:
        return {
            "llm_extract_output": "{}",
            "error": f"长模组全部 {len(segments)} 段解析失败",
        }

    merged = _merge_module_partials(partials)
    if failed:
        merged["_failed_segments"] = failed
        logger.warning("module_parser: 部分段失败，已跳过：%s", failed)

    return {"llm_extract_output": json.dumps(merged, ensure_ascii=False)}


async def validate_and_fill(state: ModuleParserState) -> dict:
    try:
        data = _try_parse_json(state["llm_extract_output"])

        top_defaults = {
            'level_min': 1, 'level_max': 5, 'recommended_party_size': 4,
            'class_restrictions': [], 'scenes': [], 'npcs': [],
            'monsters': [], 'key_rewards': [], 'magic_items': [],
            'tone': '标准冒险'
        }
        for k, v in top_defaults.items():
            if k not in data or data[k] is None:
                data[k] = v

        data['level_min'] = max(1, min(20, int(data['level_min'])))
        data['level_max'] = max(data['level_min'], min(20, int(data['level_max'])))
        data['recommended_party_size'] = max(1, min(6, int(data['recommended_party_size'])))
        data['monsters'] = [_fill_monster_defaults(m) for m in data.get('monsters', [])]

        return {
            "module_data": data,
            "module_data_json": json.dumps(data, ensure_ascii=False),
            "error": "",
        }
    except Exception as e:
        return {
            "module_data": {},
            "module_data_json": "{}",
            "error": f"解析失败: {e}",
        }


async def _call_chunks_llm(sub_module_data_json: str, batch_info: str = "") -> list[dict]:
    """单次 LLM 生成 chunks，返回解析后的 list[dict]（失败返回空）。"""
    llm = get_llm(temperature=0.3, max_tokens=4000)
    user_msg = CHUNK_USER.format(module_data_json=sub_module_data_json)
    if batch_info:
        user_msg = f"【{batch_info}】\n\n" + user_msg
    resp = await llm.ainvoke([
        SystemMessage(content=CHUNK_SYSTEM + "\n\n重要：JSON字符串值中不要使用未转义的双引号，用中文引号「」代替。"),
        HumanMessage(content=user_msg),
    ])
    text = _strip_code_block(resp.content or "[]")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = _try_parse_json(text)
        except Exception:
            return []
    if isinstance(parsed, dict):
        chunks = parsed.get("chunks") or parsed.get("rag_chunks") or []
    elif isinstance(parsed, list):
        chunks = parsed
    else:
        chunks = []
    return [c for c in chunks if isinstance(c, dict)]


async def generate_rag_chunks(state: ModuleParserState) -> dict:
    module_data = state.get("module_data")
    if not module_data:
        return {"llm_chunk_output": "[]"}

    sub_batches = _split_module_data_for_chunks(module_data)

    # 单批：走原逻辑（保持与短模组行为兼容）
    if len(sub_batches) == 1:
        chunks = await _call_chunks_llm(state["module_data_json"])
        return {"llm_chunk_output": json.dumps(chunks, ensure_ascii=False)}

    # 多批：分批生成 + 合并
    logger.info(
        "module_parser: RAG chunks 分 %d 批生成（总 %d scene/%d npc/%d item）",
        len(sub_batches),
        len(module_data.get("scenes") or []),
        len(module_data.get("npcs") or []),
        len(module_data.get("magic_items") or []),
    )

    all_chunks: list[dict] = []
    for i, sub in enumerate(sub_batches):
        sub_json = json.dumps(sub, ensure_ascii=False)
        batch_info = f"批次 {i+1} / 共 {len(sub_batches)}"
        batch_chunks: list[dict] = []
        for attempt in range(2):
            try:
                batch_chunks = await _call_chunks_llm(sub_json, batch_info)
                if batch_chunks:
                    break
            except Exception as e:
                logger.warning(
                    "RAG 批次 %d 生成失败（第 %d 次尝试）：%s",
                    i + 1, attempt + 1, e,
                )
        # chunk_id 加批次前缀，避免 ChromaDB 主键冲突
        for chunk in batch_chunks:
            orig_id = chunk.get("chunk_id") or "chunk"
            chunk["chunk_id"] = f"b{i}_{orig_id}"
        all_chunks.extend(batch_chunks)

    return {"llm_chunk_output": json.dumps(all_chunks, ensure_ascii=False)}


async def validate_rag_chunks(state: ModuleParserState) -> dict:
    try:
        text = _strip_code_block(state.get("llm_chunk_output", "[]"))
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # 尝试修复未转义引号
            parsed = _try_parse_json(text)
        # 支持两种格式：直接数组 [...] 或包裹对象 {"chunks": [...]}
        if isinstance(parsed, dict):
            chunks = parsed.get("chunks", parsed.get("rag_chunks", list(parsed.values())[0] if parsed else []))
            if not isinstance(chunks, list):
                chunks = []
        elif isinstance(parsed, list):
            chunks = parsed
        else:
            chunks = []

        validated = []
        for i, chunk in enumerate(chunks):
            if not isinstance(chunk, dict) or not chunk.get('content'):
                continue
            chunk.setdefault('chunk_id', f'chunk_{i}')
            chunk.setdefault('source_type', 'unknown')
            chunk.setdefault('summary', chunk['content'][:100])
            chunk.setdefault('tags', [])
            chunk.setdefault('entities', [])
            chunk.setdefault('searchable_questions', [])
            for field in ('tags', 'entities', 'searchable_questions'):
                if not isinstance(chunk[field], list):
                    chunk[field] = []
            validated.append(chunk)

        return {"rag_chunks": validated}
    except Exception:
        return {"rag_chunks": []}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Build graph
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_module_parser_graph():
    g = StateGraph(ModuleParserState)
    g.add_node("extract_structured_data", extract_structured_data)
    g.add_node("validate_and_fill", validate_and_fill)
    g.add_node("generate_rag_chunks", generate_rag_chunks)
    g.add_node("validate_rag_chunks", validate_rag_chunks)

    g.set_entry_point("extract_structured_data")
    g.add_edge("extract_structured_data", "validate_and_fill")
    g.add_edge("validate_and_fill", "generate_rag_chunks")
    g.add_edge("generate_rag_chunks", "validate_rag_chunks")
    g.add_edge("validate_rag_chunks", END)

    return g.compile()


async def run_module_parser(module_text: str) -> tuple[dict, list]:
    graph = build_module_parser_graph()
    result = await graph.ainvoke({
        "module_text": module_text,
        "llm_extract_output": "",
        "module_data": {},
        "module_data_json": "",
        "llm_chunk_output": "",
        "rag_chunks": [],
        "error": "",
    })
    return result.get("module_data", {}), result.get("rag_chunks", [])
