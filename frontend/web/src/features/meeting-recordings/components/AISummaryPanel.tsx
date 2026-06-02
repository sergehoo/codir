// Affichage du résumé Markdown généré par Claude / DeepSeek.
// Pas de lib markdown lourde — rendu Markdown léger en pure CSS via classes.
import { RefreshCw, Sparkles } from 'lucide-react'

import { cn } from '@/utils/cn'

interface Props {
  summary: string
  minutes?: string
  onRegenerate?: () => void
  isRegenerating?: boolean
}

/** Mini-renderer Markdown : titres ##, listes -, gras **bold**. */
function renderMd(md: string): React.ReactNode {
  if (!md) return null
  const lines = md.split('\n')
  const out: React.ReactNode[] = []
  let listBuffer: string[] = []
  const flushList = () => {
    if (listBuffer.length === 0) return
    out.push(
      <ul key={`ul-${out.length}`} className="list-disc pl-5 space-y-1 my-2">
        {listBuffer.map((item, i) => (
          <li key={i} className="text-sm text-fg leading-relaxed">
            <span dangerouslySetInnerHTML={{ __html: bold(item) }} />
          </li>
        ))}
      </ul>,
    )
    listBuffer = []
  }
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) { flushList(); continue }
    if (line.startsWith('## ')) {
      flushList()
      out.push(
        <h3 key={`h-${out.length}`} className="text-sm font-semibold mt-4 mb-2 text-copper-400 uppercase tracking-wider">
          {line.slice(3)}
        </h3>,
      )
    } else if (line.startsWith('### ')) {
      flushList()
      out.push(
        <h4 key={`h4-${out.length}`} className="text-xs font-semibold mt-3 mb-1.5">
          {line.slice(4)}
        </h4>,
      )
    } else if (/^[-*]\s+/.test(line)) {
      listBuffer.push(line.replace(/^[-*]\s+/, ''))
    } else {
      flushList()
      out.push(
        <p key={`p-${out.length}`} className="text-sm text-fg leading-relaxed my-2">
          <span dangerouslySetInnerHTML={{ __html: bold(line) }} />
        </p>,
      )
    }
  }
  flushList()
  return out
}

function bold(s: string): string {
  // Échappe HTML basique puis applique **gras**
  const escaped = s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

export function AISummaryPanel({ summary, minutes, onRegenerate, isRegenerating }: Props) {
  const content = minutes && minutes.length > summary.length ? minutes : summary
  return (
    <div className="p-5 rounded-xl border border-border bg-bg-elevated">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-copper-500" />
          <span className="text-sm font-semibold">Compte rendu IA</span>
        </div>
        {onRegenerate && (
          <button
            type="button"
            onClick={onRegenerate}
            disabled={isRegenerating}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-fg-muted hover:text-fg hover:bg-fg/5 transition"
          >
            <RefreshCw size={12} className={cn(isRegenerating && 'animate-spin')} />
            Régénérer
          </button>
        )}
      </div>
      {content
        ? <div>{renderMd(content)}</div>
        : <p className="text-sm text-fg-muted">Aucun résumé généré pour le moment.</p>
      }
    </div>
  )
}
