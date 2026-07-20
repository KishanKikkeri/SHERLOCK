import { useEffect, useRef } from 'react'

export function Waveform({
  getAnalyser,
  active,
  className,
}: {
  getAnalyser: () => AnalyserNode | null
  active: boolean
  className?: string
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !active) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Canvas strokeStyle can't read CSS custom properties directly (it's
    // not part of the CSS cascade) — resolve the actual colors once here
    // rather than re-reading getComputedStyle on every frame.
    const rootStyle = getComputedStyle(document.documentElement)
    const accentColor = rootStyle.getPropertyValue('--accent').trim() || '#0369A1'
    const borderColor = rootStyle.getPropertyValue('--border').trim() || '#334155'

    const draw = () => {
      const analyser = getAnalyser()
      const { width, height } = canvas
      ctx.clearRect(0, 0, width, height)

      if (!analyser) {
        // No mic stream yet (e.g. permission not granted) — flat line,
        // not an empty canvas, so it reads as "idle" not "broken".
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(0, height / 2)
        ctx.lineTo(width, height / 2)
        ctx.stroke()
        rafRef.current = requestAnimationFrame(draw)
        return
      }

      const data = new Uint8Array(analyser.frequencyBinCount)
      analyser.getByteTimeDomainData(data)

      ctx.strokeStyle = accentColor
      ctx.lineWidth = 2
      ctx.beginPath()
      const step = width / data.length
      for (let i = 0; i < data.length; i++) {
        const v = data[i] / 128 - 1
        const y = height / 2 + v * (height / 2) * 0.9
        const x = i * step
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()

      rafRef.current = requestAnimationFrame(draw)
    }

    draw()
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [getAnalyser, active])

  return <canvas ref={canvasRef} width={480} height={64} className={className} />
}
