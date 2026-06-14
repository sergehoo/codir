/**
 * AIChatToggleButton — bouton flottant pour ouvrir l'Assistant IA.
 * Caché quand le sidebar est ouvert.
 */
import { Bot } from 'lucide-react'

import { useAIChatStore } from '../store'

export function AIChatToggleButton() {
  const isOpen = useAIChatStore((s) => s.isOpen)
  const open = useAIChatStore((s) => s.open)

  if (isOpen) return null

  return (
    <button
      type="button"
      onClick={() => open()}
      className="fixed bottom-6 right-6 z-30 w-14 h-14 rounded-full bg-copper-gradient text-white shadow-2xl hover:shadow-copper hover:scale-105 transition grid place-items-center group"
      aria-label="Ouvrir l'Assistant CODIR"
      title="Assistant CODIR — Cliquez pour discuter"
    >
      <Bot size={22} />
      <span className="absolute -top-1 -right-1 w-3 h-3 bg-success rounded-full ring-2 ring-bg-base animate-pulse" />
    </button>
  )
}
