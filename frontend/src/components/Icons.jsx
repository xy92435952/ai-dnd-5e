/**
 * RPG SVG 图标库 — 桌游奇幻风格
 * 所有图标为手绘 SVG path，24x24 viewBox
 * 灵感来源：game-icons.net (CC BY 3.0)
 */

const Icon = ({ d, size = 24, color = 'currentColor', className = '', style = {} }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={color}
    className={className} style={{ flexShrink: 0, ...style }}>
    <path d={d} />
  </svg>
)

// ── 武器 ─────────────────────────────────────────────

export const SwordIcon = (p) => <Icon {...p} d="M6.92 5.51l-2.06.44.44 2.06 1.03-.22L17.67 19.12l1.42-1.41L7.74 6.36l.22-1.03-.22-1.02zm8.48 2.39l2.12-2.13 1.42 1.42-2.13 2.12-1.41-1.41zm-3.54 3.54l-1.41-1.41 7.07-7.07 1.41 1.41-7.07 7.07z" />

export const ShieldIcon = (p) => <Icon {...p} d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 2.18l7 3.12v5.7c0 4.83-3.23 9.36-7 10.57-3.77-1.21-7-5.74-7-10.57V6.3l7-3.12z" />

export const AxeIcon = (p) => <Icon {...p} d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zM7.5 7.5l4 4-4 4V7.5zm9 9l-4-4 4-4v8z" />

export const BowIcon = (p) => <Icon {...p} d="M4.27 3L3 4.27l3.75 3.75C5.06 9.83 4 12 4 14.5c0 3.58 2.42 6.58 5.71 7.47l.29.03.29-.03C13.58 21.08 16 18.08 16 14.5c0-2.5-1.06-4.67-2.75-6.48L17 4.27 15.73 3l-2.75 2.75C11.78 4.94 10.44 4.5 9 4.5S6.22 4.94 5.02 5.75L4.27 3z" />

export const WandIcon = (p) => <Icon {...p} d="M7.5 5.6L5 7l1.4 2.5L5 12l2.5 1.4L9 16l2.5-1.4L14 16l1.4-2.5L18 12l-2.5-1.4L17 8l-2.5-1.4L13 4l-2.5 1.4L9 4 7.5 5.6zM12 9c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3z" />

// ── 角色类 ───────────────────────────────────────────

export const SkullIcon = (p) => <Icon {...p} d="M12 2C6.48 2 2 6.48 2 12c0 3.69 2.47 6.86 6 8.25V22h8v-1.75c3.53-1.39 6-4.56 6-8.25 0-5.52-4.48-10-10-10zM9 14c-.83 0-1.5-.67-1.5-1.5S8.17 11 9 11s1.5.67 1.5 1.5S9.83 14 9 14zm6 0c-.83 0-1.5-.67-1.5-1.5S14.17 11 15 11s1.5.67 1.5 1.5S15.83 14 15 14z" />

export const HelmIcon = (p) => <Icon {...p} d="M12 2C7.58 2 4 5.58 4 10v4c0 1.1.9 2 2 2h1v-4c0-2.76 2.24-5 5-5s5 2.24 5 5v4h1c1.1 0 2-.9 2-2v-4c0-4.42-3.58-8-8-8zm-3 12v4h6v-4H9z" />

export const HeartIcon = (p) => <Icon {...p} d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />

export const MagicIcon = (p) => <Icon {...p} d="M7.5 5.6L10 4 12.5 5.6 14 4l1.4 2.5L18 7.5l-1 3 1 3-2.6 1L14 17.5l-1.5-1.5L10 17.5 8.6 15 6 14l1-3-1-3 2.5-1L7.5 5.6zM12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4z" />

// ── UI 元素 ──────────────────────────────────────────

export const DiceD20Icon = (p) => <Icon {...p} d="M12 2L1.5 9.64V18l10.5 4 10.5-4V9.64L12 2zm0 2.24L19.8 9.5H4.2L12 4.24zM3.5 10.5h7L7 17.5l-3.5-7zm10 0h7l-3.5 7-3.5-7zM12 19.76l-3.5-7h7l-3.5 7z" />

export const ScrollIcon = (p) => <Icon {...p} d="M19 3H5c-1.1 0-2 .9-2 2v2c0 .55.22 1.05.59 1.41L7 11.83V20c0 .55.45 1 1 1h8c.55 0 1-.45 1-1v-8.17l3.41-3.42c.37-.36.59-.86.59-1.41V5c0-1.1-.9-2-2-2zm-5 16H10v-6h4v6zM19 7.17l-3.41 3.42c-.37.36-.59.86-.59 1.41H9c0-.55-.22-1.05-.59-1.41L5 7.17V5h14v2.17z" />

export const BookIcon = (p) => <Icon {...p} d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z" />

export const UploadIcon = (p) => <Icon {...p} d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z" />

export const TrashIcon = (p) => <Icon {...p} d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />

export const PlayIcon = (p) => <Icon {...p} d="M8 5v14l11-7z" />

export const BackIcon = (p) => <Icon {...p} d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />

export const SaveIcon = (p) => <Icon {...p} d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z" />

export const RestIcon = (p) => <Icon {...p} d="M12.5 7C12.5 5.89 13.39 5 14.5 5H18V3H14.5C12.29 3 10.5 4.79 10.5 7s1.79 4 4 4H18v-2h-3.5c-1.11 0-2-.89-2-2zM6 13v-2h6V9H6c-1.1 0-2 .9-2 2v2c0 1.1.9 2 2 2h6v-2H6zM20 17H4v2h16v-2z" />

export const JournalIcon = (p) => <Icon {...p} d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" />

export const CheckpointIcon = (p) => <Icon {...p} d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zM6 20V4h7v5h5v11H6z" />

// ── 战斗动作 ─────────────────────────────────────────

export const AttackIcon = (p) => <Icon {...p} d="M6.92 5.51l-2.06.44.44 2.06 1.03-.22L17.67 19.12l1.42-1.41L7.74 6.36l.22-1.03-.22-1.02z" />

export const SpellIcon = (p) => <Icon {...p} d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />

export const MoveIcon = (p) => <Icon {...p} d="M13.5 5.5c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zM9.8 8.9L7 23h2.1l1.8-8 2.1 2v6h2v-7.5l-2.1-2 .6-3C14.8 12 16.8 13 19 13v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1L6 8.3V13h2V9.6l1.8-.7z" />

export const DefendIcon = (p) => <Icon {...p} d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z" />

export const DashIcon = (p) => <Icon {...p} d="M13.49 5.48c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm-3.6 13.9l1-4.4 2.1 2v6h2v-7.5l-2.1-2 .6-3c1.3 1.5 3.3 2.5 5.5 2.5v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1l-5.2 2.2v4.7h2v-3.4l1.8-.7-1.6 8.1z" />

export const DisengageIcon = (p) => <Icon {...p} d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />

export const HelpIcon = (p) => <Icon {...p} d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z" />

export const OffhandIcon = (p) => <Icon {...p} d="M19.12 17.67l-1.41 1.42L6.36 7.74l.22-1.03L5.51 6.92l-.44 2.06 2.06.44 1.03-.22L19.12 17.67zM7.5 5.6L5 7l1.4 2.5-1 3 1 3L9 17l3-1.5L15 17l1.4-2.5 2.6-1-1-3 1-3L16.5 5.6 15 4l-3 2-3-2-1.5 1.6z" />

// ── 角色职业图标 ─────────────────────────────────────

export const FighterIcon = (p) => <SwordIcon {...p} />
export const PaladinIcon = (p) => <ShieldIcon {...p} />
export const BarbarianIcon = (p) => <AxeIcon {...p} />
export const RangerIcon = (p) => <BowIcon {...p} />
export const RogueIcon = (p) => <Icon {...p} d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z" />
export const MonkIcon = (p) => <Icon {...p} d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-5.5-2.5l7.51-3.49L17.5 6.5 9.99 9.99 6.5 17.5zm5.5-6.6c.61 0 1.1.49 1.1 1.1s-.49 1.1-1.1 1.1-1.1-.49-1.1-1.1.49-1.1 1.1-1.1z" />
export const ClericIcon = (p) => <Icon {...p} d="M19 6h-3V3h-2v3h-4V3H8v3H5C3.9 6 3 6.9 3 8v11c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 13H5V8h14v11zM13 10h-2v3H8v2h3v3h2v-3h3v-2h-3v-3z" />
export const DruidIcon = (p) => <Icon {...p} d="M17.12 10a6.46 6.46 0 00-1.72-3.4 6.46 6.46 0 00-2.16-1.47C14.41 3.3 16 1.4 16 1.4S12.76 2 11.5 3.66c-.77-.3-1.6-.46-2.46-.46C6.24 3.2 4 5.4 4 8.16c0 .67.14 1.32.38 1.92C2.95 10.87 2 12.2 2 13.76c0 2.24 1.87 4.06 4.18 4.06.6 0 1.16-.13 1.68-.36.72 1.55 2.31 2.64 4.14 2.64 2.53 0 4.58-2 4.58-4.46 0-.4-.06-.78-.16-1.15 1.76-.68 3-2.33 3-4.25 0-1.38-.67-2.6-1.7-3.4z" />
export const BardIcon = (p) => <Icon {...p} d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
export const WizardIcon = (p) => <WandIcon {...p} />
export const SorcererIcon = (p) => <MagicIcon {...p} />
export const WarlockIcon = (p) => <SkullIcon {...p} />

// ── 职业名到图标映射 ─────────────────────────────────
const CLASS_ICON_MAP = {
  Fighter: FighterIcon, 战士: FighterIcon,
  Paladin: PaladinIcon, 圣武士: PaladinIcon,
  Barbarian: BarbarianIcon, 野蛮人: BarbarianIcon,
  Ranger: RangerIcon, 游侠: RangerIcon,
  Rogue: RogueIcon, 游荡者: RogueIcon,
  Monk: MonkIcon, 武僧: MonkIcon,
  Cleric: ClericIcon, 牧师: ClericIcon,
  Druid: DruidIcon, 德鲁伊: DruidIcon,
  Bard: BardIcon, 吟游诗人: BardIcon,
  Wizard: WizardIcon, 法师: WizardIcon,
  Sorcerer: SorcererIcon, 术士: SorcererIcon,
  Warlock: WarlockIcon, 邪术师: WarlockIcon,
}

export function ClassIcon({ className, ...props }) {
  const Comp = CLASS_ICON_MAP[className] || SwordIcon
  return <Comp {...props} />
}

// ── 默认导出所有 ─────────────────────────────────────
export default {
  SwordIcon, ShieldIcon, AxeIcon, BowIcon, WandIcon,
  SkullIcon, HelmIcon, HeartIcon, MagicIcon,
  DiceD20Icon, ScrollIcon, BookIcon, UploadIcon, TrashIcon,
  PlayIcon, BackIcon, SaveIcon, RestIcon, JournalIcon, CheckpointIcon,
  AttackIcon, SpellIcon, MoveIcon, DefendIcon, DashIcon, DisengageIcon, HelpIcon, OffhandIcon,
  ClassIcon,
}
