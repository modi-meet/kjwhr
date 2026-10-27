import { useEffect, useState } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

/** True when the user asked for reduced motion. Charts then update without interpolation. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => (typeof window !== 'undefined' ? window.matchMedia(QUERY).matches : false))
  useEffect(() => {
    const mq = window.matchMedia(QUERY)
    const on = () => setReduced(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return reduced
}

/** Recharts series props: animate from the current on-screen path to the new one, no overshoot. */
export const chartMotion = (reduced: boolean) =>
  reduced
    ? { isAnimationActive: false as const }
    : { isAnimationActive: true as const, animationDuration: 420, animationEasing: 'ease-out' as const, animationBegin: 0 }
