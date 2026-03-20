export default function AnimatedBackground() {
  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <pattern id="gridPattern" width="60" height="60" patternUnits="userSpaceOnUse">
          <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(100, 116, 139, 0.08)" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#gridPattern)" />
      <line x1="0" y1="20%" x2="100%" y2="20%" className="grid-line" style={{ animationDelay: '0.5s' }} />
      <line x1="0" y1="80%" x2="100%" y2="80%" className="grid-line" style={{ animationDelay: '1s' }} />
      <line x1="20%" y1="0" x2="20%" y2="100%" className="grid-line" style={{ animationDelay: '1.5s' }} />
      <line x1="80%" y1="0" x2="80%" y2="100%" className="grid-line" style={{ animationDelay: '2s' }} />
      <circle cx="20%" cy="20%" r="2" className="detail-dot" style={{ animationDelay: '2.5s' }} />
      <circle cx="80%" cy="20%" r="2" className="detail-dot" style={{ animationDelay: '2.7s' }} />
      <circle cx="20%" cy="80%" r="2" className="detail-dot" style={{ animationDelay: '2.9s' }} />
      <circle cx="80%" cy="80%" r="2" className="detail-dot" style={{ animationDelay: '3.1s' }} />
    </svg>
  )
}
