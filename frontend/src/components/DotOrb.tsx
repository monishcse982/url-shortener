import { useEffect, useRef } from 'react'

export default function DotOrb() {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const element = canvas.current
    const context = element?.getContext('2d')
    if (!element || !context) return
    let visible = true
    let frame = 0
    let phase = 0
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const start = () => { if (!reduced && visible && !document.hidden && !frame) draw() }
    const stop = () => { if (frame) cancelAnimationFrame(frame); frame = 0 }
    const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; if (visible) start(); else stop() })
    const onVisibility = () => { if (document.hidden) stop(); else start() }
    observer.observe(element)
    document.addEventListener('visibilitychange', onVisibility)
    function draw() {
      if (!context || !element) return
      const size = 300
      const ratio = window.devicePixelRatio || 1
      if (element.width !== size * ratio) { element.width = size * ratio; element.height = size * ratio }
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      context.clearRect(0, 0, size, size)
      for (let y = 12; y < size; y += 12) for (let x = 12; x < size; x += 12) {
        const dx = (x - size / 2) / 145
        const dy = (y - size / 2) / 145
        const distance = Math.sqrt(dx * dx + dy * dy)
        if (distance >= 1) continue
        const shade = Math.max(0, 1 - distance * distance)
        const drift = 0.88 + 0.12 * Math.sin(phase + x * 0.04 + y * 0.02)
        context.globalAlpha = shade * drift
        context.fillStyle = '#ff5a36'
        context.beginPath()
        context.arc(x, y, 1.5 + 2.7 * shade, 0, Math.PI * 2)
        context.fill()
      }
      context.globalAlpha = 1
      phase += 0.009
      if (!reduced && visible && !document.hidden) frame = requestAnimationFrame(() => { frame = 0; draw() })
    }
    draw()
    return () => { observer.disconnect(); document.removeEventListener('visibilitychange', onVisibility); stop() }
  }, [])
  return <canvas ref={canvas} className="dot-orb" width="300" height="300" aria-hidden="true" />
}
