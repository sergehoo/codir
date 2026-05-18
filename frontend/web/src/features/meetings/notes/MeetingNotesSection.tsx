/**
 * Section éditoriale autour de l'éditeur + panneaux latéraux + Live Mode.
 * Utilisable en intégration dans la MeetingDetailPage.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Maximize2, Minimize2, RefreshCw, Sparkles, Zap } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { PremiumButton } from '@/components/widgets/PremiumButton'

import { meetingsApi, meetingsKeys, type SmartNotesResponse } from '../api'
import { DetectedActionsPanel } from './DetectedActionsPanel'
import { DetectedDecisionsPanel } from './DetectedDecisionsPanel'
import { MentionedUsersPanel } from './MentionedUsersPanel'
import { SmartMeetingEditor } from './SmartMeetingEditor'

export function MeetingNotesSection({ meetingId }: { meetingId: string }) {
  const qc = useQueryClient()
  const [saving, setSaving] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [live, setLive] = useState(false)
  const currentJsonRef = useRef<any>(null)
  const currentPlainRef = useRef<string>('')

  const { data, isLoading } = useQuery<SmartNotesResponse>({
    queryKey: meetingsKeys.smartNotes(meetingId),
    queryFn: () => meetingsApi.smartNotes(meetingId),
  })

  const autosave = useMutation({
    mutationFn: () =>
      meetingsApi.autosaveNotes(meetingId, {
        content_json: currentJsonRef.current,
        content_md: currentPlainRef.current,
      }),
    onMutate: () => setSaving('saving'),
    onSuccess: () => {
      setSaving('saved')
      qc.invalidateQueries({ queryKey: meetingsKeys.smartNotes(meetingId) })
      // Reset to idle after 1.5s
      window.setTimeout(() => setSaving('idle'), 1500)
    },
    onError: () => {
      setSaving('error')
      window.setTimeout(() => setSaving('idle'), 3000)
    },
  })

  const reparse = useMutation({
    mutationFn: () => meetingsApi.parseNotes(meetingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: meetingsKeys.smartNotes(meetingId) })
      toast.success('Notes re-parsées')
    },
  })

  const onChange = useCallback((json: any, plain: string) => {
    currentJsonRef.current = json
    currentPlainRef.current = plain
  }, [])

  const onAutosave = useCallback(() => {
    if (!currentJsonRef.current) return
    autosave.mutate()
  }, [autosave])

  // Esc pour sortir du Live Mode
  useEffect(() => {
    if (!live) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setLive(false) }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [live])

  if (isLoading) {
    return <div className="text-fg-subtle px-10 py-8">Chargement des notes…</div>
  }

  const initialJson = data?.note?.content_json ?? null
  const detectedDecisions = data?.detected_decisions ?? []
  const orphanActions = data?.orphan_actions ?? []
  const mentions = data?.mentions ?? []

  return (
    <section className={live
      ? 'fixed inset-0 z-40 bg-bg-base overflow-auto'
      : 'px-10 py-8 border-t border-border'}>

      {/* Header */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <span className="divider-accent" />
        <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold flex items-center gap-2">
          <Sparkles size={13} className="text-copper-400" /> Notes intelligentes
        </h2>
        <p className="text-xs text-fg-subtle ml-2 hidden md:block">
          <code className="text-copper-400 font-mono">#</code> décision ·{' '}
          <code className="text-copper-400 font-mono">*</code> action ·{' '}
          <code className="text-success font-mono">&gt;</code> tâche ·{' '}
          <code className="text-copper-400 font-mono">@</code> mention ·{' '}
          <code className="text-copper-400 font-mono">22/08/2026</code> échéance ·{' '}
          <code className="text-copper-400 font-mono">!high</code> priorité
        </p>
        <div className="flex items-center gap-2 ml-auto">
          <PremiumButton size="sm" variant="ghost" iconLeft={<RefreshCw size={12} />}
            onClick={() => reparse.mutate()} loading={reparse.isPending}>
            Re-parser
          </PremiumButton>
          <PremiumButton size="sm" variant="secondary"
            iconLeft={live ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
            onClick={() => setLive((v) => !v)}>
            {live ? 'Quitter' : 'Live mode'}
          </PremiumButton>
        </div>
      </div>

      {/* Split layout */}
      <div className={`grid gap-8 ${live ? 'grid-cols-1 lg:grid-cols-[1fr_360px] max-w-7xl mx-auto px-10' : 'grid-cols-1 lg:grid-cols-[1fr_320px]'}`}>
        {/* Éditeur */}
        <div className="min-w-0">
          <SmartMeetingEditor
            meetingId={meetingId}
            initialJson={initialJson}
            onChange={onChange}
            onAutosave={onAutosave}
            saving={saving}
          />
        </div>

        {/* Panneaux latéraux */}
        <aside className="space-y-6 lg:border-l lg:border-border lg:pl-6">
          <DetectedDecisionsPanel meetingId={meetingId} decisions={detectedDecisions} />
          {orphanActions.length > 0 && (
            <DetectedActionsPanel meetingId={meetingId} actions={orphanActions} />
          )}
          <MentionedUsersPanel mentions={mentions} />

          {/* Footer rappel raccourcis */}
          <div className="text-2xs text-fg-subtle border-t border-border/60 pt-3 mt-6 space-y-1 uppercase tracking-wider">
            <div className="flex items-center gap-2 text-fg-muted font-semibold mb-1">
              <Zap size={11} /> Raccourcis
            </div>
            <Shortcut k="#"   l="Décision" />
            <Shortcut k="*"   l="Action" />
            <Shortcut k=">"   l="Tâche" />
            <Shortcut k="@"   l="Mention" />
            <Shortcut k="!"   l="Prio. !high !med …" />
            <Shortcut k="⌘D"  l="Échéance (datepicker)" />
            <Shortcut k="Tab" l="Indenter / desc." />
            <Shortcut k="⌘S"  l="Sauvegarder" />
          </div>
        </aside>
      </div>
    </section>
  )
}

function Shortcut({ k, l }: { k: string; l: string }) {
  return (
    <div className="flex items-center gap-2 text-2xs">
      <kbd className="px-1.5 py-0.5 rounded bg-bg-subtle border border-border font-mono text-copper-400 min-w-[24px] text-center">
        {k}
      </kbd>
      <span className="text-fg-subtle">{l}</span>
    </div>
  )
}
