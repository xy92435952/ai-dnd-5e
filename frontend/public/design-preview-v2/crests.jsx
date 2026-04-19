// 职业纹章 SVG — 每个职业一个辨识符号
// 用作 .portrait svg.crest
const Crest = {
  fighter: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M32 6 L36 40 L32 46 L28 40 Z" fill="currentColor" fillOpacity=".3"/>
      <path d="M32 6 L32 46"/>
      <circle cx="32" cy="48" r="3" fill="currentColor"/>
      <path d="M20 50 L44 50 M22 54 L42 54"/>
      <path d="M18 44 L26 44 M38 44 L46 44" strokeWidth="2"/>
    </svg>
  ),
  wizard: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M32 6 L42 34 L32 46 L22 34 Z" fill="currentColor" fillOpacity=".25"/>
      <path d="M32 6 L42 34 L32 46 L22 34 Z"/>
      <circle cx="32" cy="24" r="2.5" fill="currentColor"/>
      <path d="M14 48 L20 52 M50 48 L44 52 M32 52 L32 58"/>
      <circle cx="14" cy="48" r="1.5" fill="currentColor"/>
      <circle cx="50" cy="48" r="1.5" fill="currentColor"/>
      <circle cx="32" cy="58" r="1.5" fill="currentColor"/>
    </svg>
  ),
  cleric: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round">
      <circle cx="32" cy="32" r="22" strokeOpacity=".35"/>
      <path d="M32 12 L32 52 M18 32 L46 32" strokeWidth="3.5"/>
      <circle cx="32" cy="32" r="4" fill="currentColor"/>
      <path d="M22 20 L26 24 M42 20 L38 24 M22 44 L26 40 M42 44 L38 40" strokeWidth="2"/>
    </svg>
  ),
  rogue: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M32 10 L36 34 L32 40 L28 34 Z" fill="currentColor" fillOpacity=".4"/>
      <path d="M32 10 L32 40"/>
      <path d="M24 40 L40 40" strokeWidth="3"/>
      <path d="M18 48 L32 44 L46 48" />
      <circle cx="32" cy="52" r="3" fill="currentColor" fillOpacity=".6"/>
    </svg>
  ),
  paladin: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M32 8 L48 14 L48 34 C48 46 32 56 32 56 C32 56 16 46 16 34 L16 14 Z" fill="currentColor" fillOpacity=".2"/>
      <path d="M32 8 L48 14 L48 34 C48 46 32 56 32 56 C32 56 16 46 16 34 L16 14 Z"/>
      <path d="M32 20 L32 42 M24 28 L40 28" strokeWidth="3"/>
    </svg>
  ),
  ranger: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 46 Q32 10 50 46" />
      <path d="M14 46 L50 46" strokeDasharray="2 3" strokeOpacity=".6"/>
      <path d="M32 18 L32 52 M28 48 L32 52 L36 48" strokeWidth="2.2"/>
      <circle cx="32" cy="16" r="2" fill="currentColor"/>
    </svg>
  ),
  barbarian: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 44 L20 16 L28 28 L32 14 L36 28 L44 16 L50 44 Z" fill="currentColor" fillOpacity=".3"/>
      <path d="M14 44 L20 16 L28 28 L32 14 L36 28 L44 16 L50 44"/>
      <path d="M18 50 L46 50" strokeWidth="3"/>
    </svg>
  ),
  bard: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round">
      <path d="M32 10 C20 10 18 24 18 32 C18 44 24 52 32 52 C40 52 46 44 46 32 C46 24 44 10 32 10 Z" fill="currentColor" fillOpacity=".2"/>
      <path d="M24 20 L40 20 M26 28 L38 28 M28 36 L36 36 M30 44 L34 44"/>
      <circle cx="32" cy="16" r="2" fill="currentColor"/>
    </svg>
  ),
  druid: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M32 8 C40 18 44 24 44 32 C44 44 38 52 32 52 C26 52 20 44 20 32 C20 24 24 18 32 8 Z" fill="currentColor" fillOpacity=".25"/>
      <path d="M32 18 L32 52 M26 28 L32 34 L38 28 M24 38 L32 44 L40 38"/>
    </svg>
  ),
  sorcerer: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M32 8 L38 22 L52 24 L42 34 L46 50 L32 42 L18 50 L22 34 L12 24 L26 22 Z" fill="currentColor" fillOpacity=".3"/>
      <path d="M32 8 L38 22 L52 24 L42 34 L46 50 L32 42 L18 50 L22 34 L12 24 L26 22 Z"/>
      <circle cx="32" cy="30" r="3" fill="currentColor"/>
    </svg>
  ),
  warlock: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="32" cy="32" r="20" strokeOpacity=".4"/>
      <path d="M18 24 L32 44 L46 24" />
      <path d="M24 22 L20 16 M40 22 L44 16" strokeWidth="2"/>
      <circle cx="32" cy="32" r="5" fill="currentColor" fillOpacity=".6"/>
      <circle cx="32" cy="32" r="2" fill="currentColor"/>
    </svg>
  ),
  monk: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <circle cx="32" cy="32" r="20" strokeOpacity=".35"/>
      <path d="M32 12 C22 22 22 32 32 32 C22 32 22 42 32 52 C42 42 42 32 32 32 C42 32 42 22 32 12 Z" fill="currentColor" fillOpacity=".25"/>
      <circle cx="32" cy="22" r="2.5" fill="currentColor"/>
      <circle cx="32" cy="42" r="2.5" fill="currentColor"/>
    </svg>
  ),
  dm: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 16 L14 48 C14 50 16 52 18 52 L46 52 C48 52 50 50 50 48 L50 16 L46 20 L42 16 L38 20 L34 16 L30 20 L26 16 L22 20 L18 16 Z" fill="currentColor" fillOpacity=".2"/>
      <path d="M14 16 L14 48 C14 50 16 52 18 52 L46 52 C48 52 50 50 50 48 L50 16"/>
      <path d="M22 28 L42 28 M22 36 L42 36 M22 44 L36 44" strokeWidth="1.8"/>
    </svg>
  ),
  enemy: (
    <svg className="crest" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 20 L24 14 L32 22 L40 14 L50 20 L46 32 L50 48 L40 46 L32 54 L24 46 L14 48 L18 32 Z" fill="currentColor" fillOpacity=".3"/>
      <path d="M14 20 L24 14 L32 22 L40 14 L50 20 L46 32 L50 48 L40 46 L32 54 L24 46 L14 48 L18 32 Z"/>
      <circle cx="26" cy="30" r="2" fill="currentColor"/>
      <circle cx="38" cy="30" r="2" fill="currentColor"/>
    </svg>
  ),
};

window.Crest = Crest;
