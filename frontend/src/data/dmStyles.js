export const DM_STYLES = [
  {
    key: 'classic',
    label: '经典桌游',
    summary: '规则清晰、叙事均衡，像一位老练桌边 DM。',
    accent: '#d8b45f',
  },
  {
    key: 'dark_fantasy',
    label: '黑暗奇幻',
    summary: '压迫、阴影、代价与危险感更强。',
    accent: '#a64a56',
  },
  {
    key: 'lighthearted',
    label: '轻松冒险',
    summary: '明快、幽默、适合新手和轻松局。',
    accent: '#68b684',
  },
  {
    key: 'epic_crpg',
    label: '史诗 CRPG',
    summary: '电影感、强剧情、队友互动更有戏。',
    accent: '#7fb8f8',
  },
  {
    key: 'hardcore',
    label: '硬核规则',
    summary: '资源、风险、战术后果更明确。',
    accent: '#d07a3a',
  },
]

export const DEFAULT_DM_STYLE = 'classic'

export function getDmStyle(key) {
  return DM_STYLES.find(s => s.key === key) || DM_STYLES[0]
}
