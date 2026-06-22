/**
 * AIChatToggleButton — bouton flottant pour ouvrir l'Assistant IA.
 *
 * Caché quand le sidebar est ouvert.
 *
 * Lot 2 — Agent IA proactif : un badge rouge avec compteur apparaît quand
 * l'agent a émis des alertes non lues. Polling discret toutes les 60s.
 */
import { useQuery } from '@tanstack/react-query'
import { Bot } from 'lucide-react'

import { useAuthStore } from '@/stores/auth'

import { aiChatApi, aiChatKeys } from '../api'
import { useAIChatStore } from '../store'

export function AIChatToggleButton() {
  const isOpen = useAIChatStore((s) => s.isOpen)
  const open = useAIChatStore((s) => s.open)
  const token = useAuthStore((s) => s.accessToken)

  // Polling discret du compteur d'alertes proactives. 60s = équilibre entre
  // réactivité perçue et charge serveur. Désactivé sans token.
  const { data } = useQuery({
    queryKey: aiChatKeys.proactiveCount(),
    queryFn: () => aiChatApi.proactiveCount(),
    refetchInterval: 60_000,
    enabled: !!token && !isOpen,
    staleTime: 30_000,
  })
  const proactiveCount = data?.count ?? 0

  if (isOpen) return null

  return (
    <button
      type="button"
      onClick={() => open()}
      className="fixed bottom-6 right-6 z-30 w-14 h-14 rounded-full bg-copper-gradient text-white shadow-2xl hover:shadow-copper hover:scale-105 transition grid place-items-center group"
      aria-label={
        proactiveCount > 0
          ? `Assistant CODIR — ${proactiveCount} alerte(s) IA proactive(s)`
          : "Ouvrir l'Assistant CODIR"
      }
      title={
        proactiveCount > 0
          ? `${proactiveCount} alerte(s) proactive(s) de l'IA — cliquez pour voir`
          : 'Assistant CODIR — Cliquez pour discuter'
      }
    >
      <Bot size={22} />
      {proactiveCount > 0 ? (
        // Badge "alerte" rouge avec compteur — visible et pulsant
        <span className="absolute -top-1.5 -right-1.5 min-w-[20px] h-5 px-1.5 rounded-full bg-danger text-white text-[10px] font-bold leading-5 text-center ring-2 ring-bg-base animate-pulse">
          {proactiveCount > 9 ? '9+' : proactiveCount}
        </span>
      ) : (
        // Pastille "présence" verte par défaut
        <span className="absolute -top-1 -right-1 w-3 h-3 bg-success rounded-full ring-2 ring-bg-base animate-pulse" />
      )}
    </button>
  )
}
