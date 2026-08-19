/** Minimal stroke icons. Drawn inline rather than pulled from a library: there are seven of
 *  them, and this keeps the bundle and the dependency list where they are. */

type Props = { size?: number }

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  focusable: false,
})

export const ItemsIcon = ({ size = 20 }: Props) => (
  <svg {...base(size)}>
    <path d="M3 6h18M3 12h18M3 18h18" />
  </svg>
)

export const GalleryIcon = ({ size = 20 }: Props) => (
  <svg {...base(size)}>
    <rect x="3" y="3" width="7.5" height="7.5" />
    <rect x="13.5" y="3" width="7.5" height="7.5" />
    <rect x="3" y="13.5" width="7.5" height="7.5" />
    <rect x="13.5" y="13.5" width="7.5" height="7.5" />
  </svg>
)

export const AddIcon = ({ size = 20 }: Props) => (
  <svg {...base(size)}>
    <path d="M12 5v14M5 12h14" />
  </svg>
)

export const BoardsIcon = ({ size = 20 }: Props) => (
  <svg {...base(size)}>
    <rect x="3" y="3" width="18" height="18" />
    <path d="M3 9h18M9 21V9" />
  </svg>
)

export const BackIcon = ({ size = 16 }: Props) => (
  <svg {...base(size)}>
    <path d="M15 5l-7 7 7 7" />
  </svg>
)

export const CameraIcon = ({ size = 28 }: Props) => (
  <svg {...base(size)}>
    <path d="M3 8.5A1.5 1.5 0 014.5 7h2.2a1.5 1.5 0 001.3-.75l.8-1.4A1.5 1.5 0 0110.1 4h3.8a1.5 1.5 0 011.3.85l.8 1.4A1.5 1.5 0 0017.3 7h2.2A1.5 1.5 0 0121 8.5v9A1.5 1.5 0 0119.5 19h-15A1.5 1.5 0 013 17.5z" />
    <circle cx="12" cy="12.5" r="3.5" />
  </svg>
)

export const BoxIcon = ({ size = 24 }: Props) => (
  <svg {...base(size)}>
    <path d="M21 8.5v7a1.5 1.5 0 01-.8 1.32l-7.5 3.9a1.5 1.5 0 01-1.4 0l-7.5-3.9A1.5 1.5 0 013 15.5v-7" />
    <path d="M3.4 7.6l8.1-4.2a1.5 1.5 0 011.4 0l8.1 4.2-8.8 4.6z" />
    <path d="M12.2 12.2V21" />
  </svg>
)

export const SettingsIcon = ({ size = 20 }: Props) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
  </svg>
)
