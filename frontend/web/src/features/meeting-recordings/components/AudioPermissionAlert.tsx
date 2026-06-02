import { AlertTriangle, Mic } from 'lucide-react'

interface Props {
  message: string
  onRetry?: () => void
}

export function AudioPermissionAlert({ message, onRetry }: Props) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 p-4 rounded-lg border border-red-500/30 bg-red-500/10"
    >
      <AlertTriangle size={20} className="text-red-400 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-red-300">Accès micro refusé</div>
        <p className="text-xs text-red-200/80 mt-1">{message}</p>
        <p className="text-xs text-red-200/60 mt-2">
          Sur Chrome : cliquez sur l'icône cadenas dans la barre d'adresse → Site settings → Microphone → Allow.
        </p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-red-500/20 hover:bg-red-500/30 text-red-200 text-xs font-medium transition"
          >
            <Mic size={12} /> Réessayer
          </button>
        )}
      </div>
    </div>
  )
}
