export default function ActionBtn({ children, primary, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 12, padding: "5px 12px", borderRadius: 6, border: "none", cursor: "pointer", fontWeight: 500, whiteSpace: "nowrap", transition: "all 0.15s",
        background: primary ? "#1A1A18" : "#F0F0EC",
        color: primary ? "#FFFFFF" : "#5A5A56",
      }}
      onMouseEnter={e => { e.target.style.opacity = "0.8"; }}
      onMouseLeave={e => { e.target.style.opacity = "1"; }}
    >
      {children}
    </button>
  );
}
