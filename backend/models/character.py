from sqlalchemy import Column, String, Integer, Text, Boolean, JSON, ForeignKey, DateTime
from sqlalchemy.sql import func
from database import Base
import uuid


class Character(Base):
    __tablename__ = "characters"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True)
    # 多人联机：标识此角色由哪个真人玩家操控（v0.9 起）
    # is_player=True 且 user_id 非空 → 真人玩家角色
    # is_player=True 且 user_id 为空 → 单人模式玩家角色（向后兼容）
    # is_player=False                → AI 队友（user_id 必为空）
    user_id    = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    is_player  = Column(Boolean, default=True)
    name       = Column(String(100), nullable=False)

    # ── 基础属性 ───────────────────────────────────────────
    race       = Column(String(50),  nullable=False)
    char_class = Column(String(50),  nullable=False)
    subclass   = Column(String(100), nullable=True)
    level      = Column(Integer,     default=1)
    background = Column(String(100), nullable=True)
    alignment  = Column(String(50),  nullable=True)

    # 六维能力值（已含种族加值的最终值）
    ability_scores = Column(JSON, nullable=False)
    # {"str":15,"dex":13,"con":14,"int":10,"wis":12,"cha":8}

    # ── 衍生属性（由 calc_derived 计算，存入 DB 避免重复计算）──
    derived = Column(JSON, nullable=True)
    # {
    #   hp_max, ac, initiative, proficiency_bonus,
    #   attack_bonus, ranged_attack_bonus,
    #   spell_save_dc, spell_attack_bonus, spell_ability, caster_type,
    #   ability_modifiers: {str,dex,con,int,wis,cha},
    #   saving_throws: {str,dex,con,int,wis,cha},   ← 含熟练加值
    #   spell_slots_max: {"1st":4,...},               ← 满血法术位（只读参考）
    #   hit_die, cantrips_count,
    # }

    hp_current = Column(Integer, nullable=False)

    # ── 法术系统 ───────────────────────────────────────────
    # spell_slots: 当前剩余法术位（消耗后减少，长休后重置）
    spell_slots = Column(JSON, default=dict)
    # {"1st":3,"2nd":2,...}  对于Warlock: {"5th":2}

    # 已知法术（法师=法术书，术士=已知列表，其他=职业表默认全部）
    known_spells    = Column(JSON, default=list)   # ["cure-wounds","fireball",...]
    # 当前已备法术（法师/牧师/德鲁伊每次长休重新备）
    prepared_spells = Column(JSON, default=list)
    # 戏法（0环，无限使用）
    cantrips        = Column(JSON, default=list)   # ["fire-bolt","guidance",...]
    # 专注追踪
    concentration   = Column(String(100), nullable=True)  # 当前专注的法术名，None表示未专注

    # ── 熟练项 ────────────────────────────────────────────
    # 技能熟练（精确追踪，修复"全部熟练"bug）
    proficient_skills = Column(JSON, default=list)   # ["运动","隐匿"]
    # 豁免熟练（由职业决定，calc_derived已处理但单独存储方便查询）
    proficient_saves  = Column(JSON, default=list)   # ["str","con"]

    # ── 战斗风格 ──────────────────────────────────────────
    fighting_style = Column(String(50), nullable=True)  # "Archery" / "Defense" / ...

    # ── 语言与工具 ────────────────────────────────────────
    languages = Column(JSON, default=list)              # ["Common","Elvish"]
    tool_proficiencies = Column(JSON, default=list)     # ["Thieves' Tools"]

    # ── 专长 ──────────────────────────────────────────────
    feats = Column(JSON, default=list)                  # [{"name":"Alert"},{"name":"Tough"}]

    # ── 装备 ──────────────────────────────────────────────
    equipment = Column(JSON, default=dict)
    # {"weapons":[{"name":"Longsword",...}],"armor":[{...}],"shield":{...},"gear":[...],"gold":10}

    # ── AI 队友专用字段 ────────────────────────────────────
    personality      = Column(Text,         nullable=True)
    speech_style     = Column(String(100),  nullable=True)
    combat_preference= Column(String(100),  nullable=True)
    backstory        = Column(Text,         nullable=True)
    catchphrase      = Column(String(200),  nullable=True)

    # ── 状态条件 ──────────────────────────────────────────
    conditions = Column(JSON, default=list)
    # ["poisoned","prone","blinded",...]  → 战斗中影响骰子结果
    condition_durations = Column(JSON, default=dict)
    # {"poisoned": 3, "prone": 2}  # 剩余回合数；无键=永久条件

    # ── 濒死豁免（HP归零后启用）─────────────────────────────
    death_saves = Column(JSON, nullable=True)
    # {"successes": 0, "failures": 0, "stable": false}

    # ── 生命骰与职业资源 ────────────────────────────────────
    hit_dice_remaining = Column(Integer, nullable=True)  # 短休可用生命骰数量
    class_resources = Column(JSON, default=dict)
    # {"rage_uses": 2, "second_wind_used": false, "action_surge_used": false, "raging": false, ...}

    # ── 双职业 ────────────────────────────────────────────
    multiclass_info = Column(JSON, nullable=True)
    # {"char_class": "Fighter", "level": 2}

    created_at = Column(DateTime, server_default=func.now())
