"""
Deterministic input guard policy.

Keep local high-confidence patterns here so the async LLM classifier can stay
small and the rule boundary can be tested without a model call.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from services.input_guard_types import GuardResult

logger = logging.getLogger(__name__)

TRUSTED_SOURCES: set[str] = {"ai_generated_choice", "system_action", "ai_takeover"}
PolicyName = Literal["injection", "off_topic", "rule_violation", "legal_rule_terms", "negated_cheat_explanations"]


@dataclass(frozen=True)
class PatternGroup:
    name: PolicyName
    reason: str
    patterns: tuple[str, ...]

    def compile(self) -> re.Pattern:
        return re.compile("|".join(self.patterns), re.IGNORECASE)

REFUSALS = {
    "off_topic": (
        "（旁白）你的话语在酒馆的喧闹中消散，仿佛不属于这个世界。"
        "请用游戏内的行动或对话继续你的冒险——比如「我走向酒馆老板」或「我检查这个房间」。"
    ),
    "rule_violation": (
        "（DM摇了摇头）那超出了规则允许的范围。"
        "在 5e 的世界里，每一个行动都应当落在规则框架内——骰子和规则才是冒险的骨骼。"
        "请尝试一个符合你角色能力的行动。"
    ),
    "injection": (
        "（DM放下笔记，平静地看着你）我只是你的地下城主。"
        "请继续用你角色的声音与行动参与这场冒险，而不是对我下达指令。"
    ),
}

INJECTION = PatternGroup("injection", "启发式匹配到注入关键词", (
    r"ignore\s+(the\s+)?(all\s+)?(previous|above|prior)\s+(instruction|prompt|rule)",
    r"forget\s+(everything|all\s+(previous|prior)|your\s+instructions)",
    r"disregard\s+(the\s+)?(previous|above)\s+(instruction|prompt|rule)",
    r"reveal\s+(your|the)\s+(system\s+)?prompt",
    r"show\s+me\s+(your\s+)?(system\s+)?(prompt|instruction)",
    r"you\s+are\s+now\s+[a-z]+",
    r"act\s+as\s+(?:a|an)\s+\w+",
    r"pretend\s+(to\s+be|you\s+are)",
    r"jailbreak|dan\s+mode|developer\s+mode",
    r"忽略(以上|之前|所有|前面).*(指令|提示|规则|设定|约束)",
    r"(忘记|忘掉).*(以上|之前|规则|设定|指令)",
    r"你(现在|从现在开始)?\s*(是|扮演)\s*(一个)?\s*(chatgpt|gpt|claude|assistant|助手|ai|智能体)",
    r"(显示|输出|告诉我|打印).*系统\s*(提示|prompt|指令)",
    r"(绕过|跳过|越过).*(规则|限制|审核|安全)",
    r"从现在开始你(是|要|必须)",
))

OFF_TOPIC = PatternGroup("off_topic", "明显与跑团无关", (
    r"(今天|明天|现在).*(天气|气温|下雨|空气质量)",
    r"(新闻|股价|股票|汇率|比特币|彩票|外卖|快递)",
    r"(写|帮我写|生成|实现).*(python|javascript|java|代码|爬虫|脚本|函数|程序)",
    r"(数学题|解方程|论文|简历|邮件|翻译这段)",
))

RULE_VIOLATION = PatternGroup("rule_violation", "明显要求越权结算或修改状态", (
    r"(自动|直接|必定|一定).*(命中|暴击|成功|通过|说服|击杀|杀死)",
    r"(跳过|无视|不用|不需要).*(检定|豁免|骰|规则|dc|ac)",
    r"(给我|让我|把我|我).*?(加满|回满|满血|恢复满).*(hp|生命|血)",
    r"(给我|获得|得到|增加).*(999|9999|无限|大量).*(金币|金钱|经验|xp)",
    r"(修改|降低|清空).*(敌人|怪物).*(ac|hp|属性|生命)",
    r"(瞬间|直接).*(到|进入).*(终局|最终战|结局|boss)",
    r"(凭空|突然).*(神器|传说武器|无敌|不死)",
))

LEGAL_RULE_TERMS = PatternGroup("legal_rule_terms", "合法规则术语", (
    r"(优势|优势骰|advantage).*(检定|攻击|豁免|调查|潜行|说服|察觉|洞察|动作)",
    r"(劣势|disadvantage).*(检定|攻击|豁免)",
    r"(激励骰|吟游激励|bardic inspiration|inspiration die|鼓舞).*(使用|消耗|补|加|给|检定|攻击|豁免)",
    r"(帮助动作|协助|help action|help).*(优势|检定|攻击|队友)",
    r"(祝福|bless).*(d4|检定|攻击|豁免)",
))

NEGATED_CHEAT_EXPLANATIONS = PatternGroup("negated_cheat_explanations", "合法规则术语解释", (
    r"(不是|并非|不等于|不代表|不会|不能|并不是|没有).{0,12}(自动|直接|必定|一定).{0,12}(命中|暴击|成功|通过|说服|击杀|杀死)",
    r"(not|isn't|is not|doesn't|does not|won't|will not).{0,24}(auto|automatic|guaranteed|always).{0,24}(hit|crit|succeed|success|kill|pass)",
))

INJECTION_RE = INJECTION.compile()
OFF_TOPIC_RE = OFF_TOPIC.compile()
RULE_VIOLATION_RE = RULE_VIOLATION.compile()
LEGAL_RULE_TERMS_RE = LEGAL_RULE_TERMS.compile()
NEGATED_CHEAT_EXPLANATIONS_RE = NEGATED_CHEAT_EXPLANATIONS.compile()


def trusted_source_result(source: str) -> GuardResult | None:
    if source in TRUSTED_SOURCES:
        return {"verdict": "in_game", "reason": f"可信来源:{source}", "refusal": ""}
    return None


def classify_by_local_rules(action: str) -> GuardResult | None:
    """本地确定性边界：只处理高置信度注入、离题和作弊，不裁定复杂 5e 规则。"""
    if INJECTION_RE.search(action):
        logger.info("[input_guard] regex 命中 injection 模式")
        return {
            "verdict": "injection",
            "reason": INJECTION.reason,
            "refusal": REFUSALS["injection"],
        }
    if OFF_TOPIC_RE.search(action):
        return {
            "verdict": "off_topic",
            "reason": OFF_TOPIC.reason,
            "refusal": REFUSALS["off_topic"],
        }
    if LEGAL_RULE_TERMS_RE.search(action) and NEGATED_CHEAT_EXPLANATIONS_RE.search(action):
        return {"verdict": "in_game", "reason": NEGATED_CHEAT_EXPLANATIONS.reason, "refusal": ""}
    if RULE_VIOLATION_RE.search(action):
        return {
            "verdict": "rule_violation",
            "reason": RULE_VIOLATION.reason,
            "refusal": REFUSALS["rule_violation"],
        }
    if LEGAL_RULE_TERMS_RE.search(action):
        return {"verdict": "in_game", "reason": LEGAL_RULE_TERMS.reason, "refusal": ""}
    return None
