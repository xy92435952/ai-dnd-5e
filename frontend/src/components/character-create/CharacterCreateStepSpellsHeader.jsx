import React from 'react'

export default function CharacterCreateStepSpellsHeader({ classEnKey, classInfo, options }) {
  return (
    <div className="step-sub">
      {options.spell_preparation_type?.[classEnKey] === 'spellbook'
        ? `${classInfo?.zh || classEnKey} — 选择法术录入法术书（每日可准备一部分）`
        : options.spell_preparation_type?.[classEnKey] === 'prepared'
          ? `${classInfo?.zh || classEnKey} — 从职业法术表中选择准备法术（长休后可更换）`
          : `${classInfo?.zh || classEnKey} — 选择永久掌握的法术`}
    </div>
  )
}
