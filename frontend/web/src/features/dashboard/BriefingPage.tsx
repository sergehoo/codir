/**
 * BriefingPage — Briefing matinal vocal (Lot 4).
 *
 * Affiche le briefing du jour en markdown ET propose un lecteur TTS basé sur
 * `window.speechSynthesis` (Web Speech API native — gratuit, sans serveur).
 *
 * Stratégie TTS :
 *   1. Au mount, on liste les voix disponibles via `speechSynthesis.getVoices()`.
 *   2. On sélectionne automatiquement la meilleure voix française :
 *      priorité aux voix "natural", "premium", "neural" (Google, Microsoft),
 *      sinon n'importe quelle voix fr-FR / fr-CA.
 *   3. Boutons Play/Pause/Stop + slider vitesse (0.7×–1.3×).
 *   4. Mise en évidence du paragraphe en cours via highlight CSS (option simple
 *      avec onboundary).
 *
 * Pas de fallback si l'API n'est pas supportée — message clair invitant à
 * utiliser un navigateur moderne (Chrome/Edge/Safari ont speechSynthesis natif).
 */
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  AlertTriangle, Calendar, CheckSquare, Gauge, Pause, Play,
  RefreshCw, RotateCcw, Scale, Sparkles, Square, Target, Volume2,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { PremiumButton } from '@/components/widgets/PremiumButton'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { useAuthStore } from '@/stores/auth'
import { cn } from '@/utils/cn'

import { dashboardApi } from './api'


/** Convertit un markdown simple en HTML (h2/h3 + listes + bold). Pas besoin
 *  d'une lib complète — le briefing produit côté backend est très structuré. */
function renderSimpleMarkdown(md: string): string {
  if (!md) return ''
  const lines = md.split('\n')
  const out: string[] = []
  let inList = false
  for (const raw of lines) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      if (inList) { out.push('</ul>'); inList = false }
      out.push('')
      continue
    }
    const h2 = line.match(/^## (.+)$/)
    const h3 = line.match(/^### (.+)$/)
    const li = line.match(/^- (.+)$/)
    let html: string
    if (h2)      html = `<h2>${esc(h2[1])}</h2>`
    else if (h3) html = `<h3>${esc(h3[1])}</h3>`
    else if (li) {
      if (!inList) { out.push('<ul>'); inList = true }
      html = `<li>${formatInline(li[1])}</li>`
    } else {
      if (inList) { out.push('</ul>'); inList = false }
      html = `<p>${formatInline(line)}</p>`
    }
    out.push(html)
  }
  if (inList) out.push('</ul>')
  return out.join('\n')
}

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function formatInline(s: string): string {
  return esc(s).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}


/** Sélectionne automatiquement la meilleure voix française disponible. */
function pickBestFrenchVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (!voices.length) return null
  const fr = voices.filter((v) => v.lang.toLowerCase().startsWith('fr'))
  if (!fr.length) return null

  // Priorité 1 : voix premium/neural identifiables par leur nom
  const premium = fr.find((v) =>
    /natural|premium|neural|enhanced|google/i.test(v.name)
  )
  if (premium) return premium

  // Priorité 2 : voix par défaut (souvent la meilleure de l'OS)
  const def = fr.find((v) => v.default)
  if (def) return def

  // Priorité 3 : fr-FR avant fr-CA / fr-BE
  const frFR = fr.find((v) => v.lang.toLowerCase() === 'fr-fr')
  if (frFR) return frFR

  return fr[0]
}


export function BriefingPage() {
  const user = useAuthStore((s) => s.user)
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['briefing', 'today'],
    queryFn: () => dashboardApi.briefing(),
    staleTime: 5 * 60_000,
  })

  // ── État TTS ─────────────────────────────────────────────
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [selectedVoice, setSelectedVoice] = useState<SpeechSynthesisVoice | null>(null)
  const [rate, setRate] = useState(1.0)
  const [playing, setPlaying] = useState(false)
  const [paused, setPaused] = useState(false)
  const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  // Charge la liste des voix (asynchrone sur Chrome — onvoiceschanged)
  useEffect(() => {
    if (!ttsSupported) return
    const loadVoices = () => {
      const list = window.speechSynthesis.getVoices()
      setVoices(list)
      const best = pickBestFrenchVoice(list)
      if (best && !selectedVoice) setSelectedVoice(best)
    }
    loadVoices()
    window.speechSynthesis.addEventListener('voiceschanged', loadVoices)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', loadVoices)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ttsSupported])

  // Stop la lecture si on quitte la page
  useEffect(() => {
    return () => {
      if (ttsSupported) window.speechSynthesis.cancel()
    }
  }, [ttsSupported])

  const frenchVoices = useMemo(
    () => voices.filter((v) => v.lang.toLowerCase().startsWith('fr')),
    [voices],
  )

  function speak() {
    if (!ttsSupported || !data?.vocal_text) return
    window.speechSynthesis.cancel()  // stop toute lecture en cours

    const u = new SpeechSynthesisUtterance(data.vocal_text)
    if (selectedVoice) u.voice = selectedVoice
    u.lang = selectedVoice?.lang || 'fr-FR'
    u.rate = rate
    u.pitch = 1.0
    u.onstart = () => { setPlaying(true); setPaused(false) }
    u.onend   = () => { setPlaying(false); setPaused(false) }
    u.onerror = () => { setPlaying(false); setPaused(false) }
    utteranceRef.current = u
    window.speechSynthesis.speak(u)
  }

  function togglePause() {
    if (!ttsSupported) return
    if (paused) {
      window.speechSynthesis.resume()
      setPaused(false)
    } else {
      window.speechSynthesis.pause()
      setPaused(true)
    }
  }

  function stop() {
    if (!ttsSupported) return
    window.speechSynthesis.cancel()
    setPlaying(false)
    setPaused(false)
  }

  // Re-générer le briefing (refetch backend)
  const regenerate = useMutation({
    mutationFn: () => refetch(),
  })

  // ── Render ──────────────────────────────────────────────
  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Mon assistant"
        title="Briefing du jour"
        description="Votre synthèse personnalisée — à lire ou à écouter."
      />

      <div className="px-10 py-8 max-w-5xl space-y-6">

        {/* Sommaire + lecteur vocal + tagline IA */}
        <div className="card p-6 bg-bg-elevated">
          <div className="flex items-start gap-4 flex-wrap">
            <div className="flex-1 min-w-[280px]">
              <div className="flex items-center gap-2 text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-2">
                <Sparkles size={12} className="text-copper-400" />
                <span>Synthèse exécutive — {user?.first_name || ''}</span>
              </div>
              <p className="text-base text-fg leading-relaxed">
                {isLoading ? 'Chargement de votre briefing…' : (data?.summary || '')}
              </p>
              {/* Tagline IA — phrase d'accroche contextuelle (Claude ou fallback) */}
              {data?.tagline && (
                <blockquote className="mt-3 pl-3 border-l-2 border-copper-500/40 text-sm text-fg-muted italic leading-relaxed">
                  {data.tagline}
                </blockquote>
              )}
            </div>

            <PremiumButton
              variant="secondary" size="sm"
              iconLeft={<RefreshCw size={13} className={isRefetching ? 'animate-spin' : ''} />}
              onClick={() => regenerate.mutate()}
              disabled={isLoading || isRefetching}
            >
              Actualiser
            </PremiumButton>
          </div>

          {/* Mini cartes KPI : chiffres clés du briefing */}
          {data && !isLoading && (
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3 mt-5">
              {(data.stats.my_tasks_overdue ?? 0) > 0 && (
                <BriefingKpi
                  icon={<AlertTriangle size={14} className="text-danger" />}
                  label="En retard" value={data.stats.my_tasks_overdue!} tone="danger"
                />
              )}
              <BriefingKpi
                icon={<CheckSquare size={14} className="text-copper-400" />}
                label="Aujourd'hui" value={data.stats.my_tasks_today}
              />
              {(data.stats.my_tasks_week ?? 0) > 0 && (
                <BriefingKpi
                  icon={<Target size={14} className="text-info" />}
                  label="Cette semaine" value={data.stats.my_tasks_week!}
                />
              )}
              <BriefingKpi
                icon={<Calendar size={14} className="text-info" />}
                label="Réunions jour" value={data.stats.meetings_today}
              />
              {(data.stats.meetings_week ?? 0) > 0 && (
                <BriefingKpi
                  icon={<Calendar size={14} className="text-fg-muted" />}
                  label="Réunions semaine" value={data.stats.meetings_week!}
                />
              )}
              {data.stats.decisions_pending > 0 && (
                <BriefingKpi
                  icon={<Scale size={14} className="text-warning" />}
                  label="Décisions" value={data.stats.decisions_pending} tone="warning"
                />
              )}
              {data.stats.at_risk > 0 && (
                <BriefingKpi
                  icon={<AlertTriangle size={14} className="text-warning" />}
                  label="À surveiller" value={data.stats.at_risk} tone="warning"
                />
              )}
              {typeof data.stats.epi_score === 'number' && data.stats.epi_score > 0 && (
                <BriefingKpi
                  icon={<Gauge size={14} className="text-success" />}
                  label="EPI Score" value={data.stats.epi_score} tone="success"
                />
              )}
              {(data.stats.team_overdue ?? 0) > 0 && (
                <BriefingKpi
                  icon={<AlertTriangle size={14} className="text-warning" />}
                  label="Équipe (retards)" value={data.stats.team_overdue!} tone="warning"
                />
              )}
            </div>
          )}

          {/* Lecteur TTS */}
          {ttsSupported ? (
            <div className="mt-5 pt-5 border-t border-border">
              <div className="flex items-center gap-3 flex-wrap">
                {!playing ? (
                  <PremiumButton
                    variant="primary" size="md"
                    iconLeft={<Play size={14} />}
                    onClick={speak}
                    disabled={!data?.vocal_text}
                  >
                    Écouter mon briefing
                  </PremiumButton>
                ) : (
                  <>
                    <PremiumButton
                      variant="secondary" size="md"
                      iconLeft={paused ? <Play size={14} /> : <Pause size={14} />}
                      onClick={togglePause}
                    >
                      {paused ? 'Reprendre' : 'Pause'}
                    </PremiumButton>
                    <PremiumButton
                      variant="secondary" size="md"
                      iconLeft={<Square size={13} />}
                      onClick={stop}
                    >
                      Arrêter
                    </PremiumButton>
                  </>
                )}

                {/* Vitesse */}
                <div className="flex items-center gap-2 text-2xs uppercase tracking-wider text-fg-muted">
                  <span>Vitesse</span>
                  <input
                    type="range"
                    min="0.7" max="1.3" step="0.1"
                    value={rate}
                    onChange={(e) => setRate(parseFloat(e.target.value))}
                    className="w-24"
                  />
                  <span className="font-mono tabular text-fg">{rate.toFixed(1)}×</span>
                </div>

                {/* Sélecteur voix (si plus d'une voix FR dispo) */}
                {frenchVoices.length > 1 && (
                  <div className="flex items-center gap-2 ml-auto text-2xs uppercase tracking-wider text-fg-muted">
                    <Volume2 size={12} />
                    <select
                      value={selectedVoice?.name || ''}
                      onChange={(e) => {
                        const v = frenchVoices.find((vc) => vc.name === e.target.value)
                        if (v) setSelectedVoice(v)
                      }}
                      className="bg-bg border border-border rounded px-2 py-1 text-xs normal-case"
                    >
                      {frenchVoices.map((v) => (
                        <option key={v.name} value={v.name}>
                          {v.name} ({v.lang})
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="mt-5 pt-5 border-t border-border text-xs text-fg-muted">
              La lecture vocale n'est pas supportée par ce navigateur. Utilisez Chrome, Edge, Safari ou Firefox récent.
            </div>
          )}
        </div>

        {/* Contenu markdown */}
        <div className={cn(
          'card p-8 prose prose-sm max-w-none',
          'prose-headings:font-serif prose-headings:text-fg',
          'prose-h2:text-xl prose-h2:mt-0 prose-h2:mb-3 prose-h2:text-copper-400',
          'prose-h3:text-base prose-h3:text-fg prose-h3:mt-5 prose-h3:mb-2 prose-h3:font-semibold',
          'prose-p:text-fg prose-p:leading-relaxed',
          'prose-li:text-fg prose-li:my-1',
          'prose-strong:text-fg prose-strong:font-semibold',
        )}>
          {isLoading ? (
            <div className="space-y-3">
              <div className="h-6 bg-fg/[0.05] rounded animate-pulse w-1/3" />
              <div className="h-4 bg-fg/[0.05] rounded animate-pulse w-2/3" />
              <div className="h-4 bg-fg/[0.05] rounded animate-pulse w-1/2" />
              <div className="h-4 bg-fg/[0.05] rounded animate-pulse w-3/4" />
            </div>
          ) : data?.markdown ? (
            <div dangerouslySetInnerHTML={{ __html: renderSimpleMarkdown(data.markdown) }} />
          ) : (
            <div className="text-fg-muted">
              <RotateCcw size={14} className="inline mr-1.5" />
              Aucun briefing disponible. Actualisez ou réessayez plus tard.
            </div>
          )}

          {data?.generated_at && (
            <div className="mt-6 pt-4 border-t border-border text-2xs uppercase tracking-wider text-fg-subtle">
              <Calendar size={11} className="inline mr-1.5" />
              Généré le {new Date(data.generated_at).toLocaleString('fr-FR', {
                day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


/** Mini-tuile KPI compacte affichée dans le briefing matinal. */
function BriefingKpi({
  icon, label, value, tone = 'neutral',
}: {
  icon: React.ReactNode
  label: string
  value: number
  tone?: 'neutral' | 'danger' | 'warning' | 'success' | 'info'
}) {
  const toneBg: Record<string, string> = {
    neutral: 'bg-fg/[0.04]',
    danger:  'bg-danger/10',
    warning: 'bg-warning/10',
    success: 'bg-success/10',
    info:    'bg-info/10',
  }
  return (
    <div className={`rounded-lg p-3 ${toneBg[tone]} flex flex-col gap-1.5`}>
      <div className="flex items-center gap-1.5 text-2xs uppercase tracking-wider text-fg-muted font-semibold">
        {icon}
        <span className="truncate">{label}</span>
      </div>
      <div className="text-2xl font-serif tabular tracking-tight text-fg">{value}</div>
    </div>
  )
}
