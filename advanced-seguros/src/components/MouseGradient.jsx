import { useState, useEffect } from 'react'

export default function MouseGradient() {
  const [style, setStyle] = useState({ left: '0px', top: '0px', opacity: 0 })

  useEffect(() => {
    const onMove = (e) => setStyle({ left: `${e.clientX}px`, top: `${e.clientY}px`, opacity: 1 })
    const onLeave = () => setStyle(prev => ({ ...prev, opacity: 0 }))
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseleave', onLeave)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseleave', onLeave)
    }
  }, [])

  return <div id="mouse-gradient" style={style} />
}
