import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BellOff, BellRing, Bot, CheckCircle2, Mail, MessageSquare, Send, Smartphone, Sunrise } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { PremiumButton } from '@/components/widgets/PremiumButton'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { SkeletonList } from '@/components/widgets/Skeleton'

import { notificationsApi, notificationsKeys, type NotificationPreference } from './api'
import { usePushSubscription } from './usePushSubscription'

type ToggleRow = {
  key: keyof NotificationPreference
  label: string
  hint?: string
  icon?: React.ReactNode
}

const CHANNELS: ToggleRow[] = [
  { key: 'email_enabled',    label: 'Emails',     hint: 'Notifications par email',           icon: <Mail size={14} /> },
  { key: 'internal_enabled', label: 'In-app',     hint: 'Notifications dans l\'application', icon: <BellRing size={14} /> },
  { key: 'sms_enabled',      label: 'SMS',        hint: 'Bientôt — désactivé par défaut',    icon: <MessageSquare size={14} /> },
  { key: 'whatsapp_enabled', label: 'WhatsApp',   hint: 'Bientôt — désactivé par défaut',    icon: <Send size={14} /> },
  { key: 'push_enabled',     label: 'Push mobile', hint: 'Bientôt — désactivé par défaut',   icon: <Smartphone size={14} /> },
]

const EVENTS: ToggleRow[] = [
  { key: 'task_assignment_email', label: 'Email quand une tâche m\'est assignée' },
  { key: 'task_delegation_email', label: 'Email quand une tâche m\'est déléguée' },
  { key: 'daily_task_reminder',   label: 'Rappel quotidien de mes tâches (09h / 16h)' },
  { key: 'due_soon_alert',        label: 'Alerte échéance proche (J+1 / J+2)' },
  { key: 'overdue_alert',         label: 'Alerte tâche en retard' },
  { key: 'manager_summary',       label: 'Résumé manager (si je supervise une filiale/direction)' },
  { key: 'decision_alerts',       label: 'Alertes décisions CODIR' },
  { key: 'meeting_alerts',        label: 'Alertes réunions' },
]

export function NotificationPreferencesPage() {
  const qc = useQueryClient()
  const push = usePushSubscription()
  const { data, isLoading } = useQuery({
    queryKey: notificationsKeys.preference(),
    queryFn: () => notificationsApi.preference(),
  })

  const [draft, setDraft] = useState<Partial<NotificationPreference>>({})
  useEffect(() => { if (data) setDraft(data) }, [data])

  const save = useMutation({
    mutationFn: () => notificationsApi.updatePreference(draft),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: notificationsKeys.preference() })
      toast.success('Préférences enregistrées')
    },
    onError: () => toast.error('Échec de l\'enregistrement'),
  })

  const testMail = useMutation({
    mutationFn: () => notificationsApi.testEmail(),
    onSuccess: (r) => toast.success(r.detail),
    onError: () => toast.error('Échec de l\'envoi'),
  })

  const toggle = (key: keyof NotificationPreference) =>
    setDraft((d) => ({ ...d, [key]: !d[key] }))

  if (isLoading) return <div className="p-10"><SkeletonList rows={6} /></div>

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Mon compte"
        title="Préférences notifications"
        description="Choisissez ce qui vous parvient et par quel canal."
      />

      <section className="px-10 py-8 space-y-8 max-w-3xl">
        {/* Canaux */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Canaux</h2>
          </div>
          <div className="card divide-y divide-border">
            {CHANNELS.map((r) => (
              <ToggleLine
                key={r.key}
                label={r.label} hint={r.hint} icon={r.icon}
                checked={!!draft[r.key]}
                onChange={() => toggle(r.key)}
              />
            ))}
          </div>
        </div>

        {/* Push Web (Lot 6) — bouton dédié car flow asynchrone */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
              Notifications push mobile
            </h2>
          </div>
          <div className="card p-5">
            {!push.supported && (
              <div className="text-sm text-fg-muted">
                Votre navigateur ne supporte pas les notifications push.
                Utilisez Chrome, Edge, Safari ou Firefox récent.
              </div>
            )}
            {push.supported && (
              <div className="flex items-start gap-4 flex-wrap">
                <div className="flex-1 min-w-[240px]">
                  <div className="text-sm font-medium text-fg">
                    {push.subscribed
                      ? '✓ Notifications push activées sur cet appareil'
                      : 'Recevez les alertes en temps réel, même app fermée'}
                  </div>
                  <p className="text-xs text-fg-muted mt-1 leading-relaxed">
                    Une tâche assignée, une décision approuvée, une réunion qui démarre…
                    chaque alerte importante s'affiche en notification système. Vous pouvez
                    aussi installer CODIR comme une app via le menu du navigateur.
                  </p>
                  {push.permission === 'denied' && (
                    <p className="text-xs text-warning mt-2">
                      ⚠ Permission refusée dans le navigateur. Réactivez les notifications dans
                      les paramètres du site.
                    </p>
                  )}
                  {push.error && (
                    <p className="text-xs text-danger mt-2">{push.error}</p>
                  )}
                </div>
                <PremiumButton
                  variant={push.subscribed ? 'secondary' : 'primary'}
                  size="md"
                  disabled={push.loading || push.permission === 'denied'}
                  onClick={async () => {
                    try {
                      if (push.subscribed) await push.disable()
                      else                  await push.enable()
                      toast.success(push.subscribed
                        ? 'Notifications push désactivées'
                        : 'Notifications push activées')
                    } catch { /* erreur déjà capturée dans le hook */ }
                  }}
                >
                  {push.loading
                    ? '...'
                    : push.subscribed
                      ? 'Désactiver sur cet appareil'
                      : 'Activer les notifications push'}
                </PremiumButton>
              </div>
            )}
          </div>
        </div>

        {/* Événements */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Événements</h2>
          </div>
          <div className="card divide-y divide-border">
            {EVENTS.map((r) => (
              <ToggleLine
                key={r.key}
                label={r.label} hint={r.hint}
                checked={!!draft[r.key]}
                onChange={() => toggle(r.key)}
              />
            ))}
          </div>
        </div>

        {/* Briefing matinal quotidien */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Briefing matinal</h2>
          </div>
          <div className="card p-5">
            <div className="flex items-start gap-4 flex-wrap">
              <div className="flex-1 min-w-[240px]">
                <div className="flex items-center gap-2 text-sm font-medium text-fg">
                  <Sunrise size={15} className="text-copper-400" />
                  Recevoir mon briefing chaque matin par email + push
                </div>
                <p className="text-xs text-fg-muted mt-1 leading-relaxed">
                  Synthèse personnalisée du jour (tâches, réunions, décisions, alertes IA).
                  Vous pouvez l'écouter via la lecture vocale du navigateur depuis la page
                  briefing. Désactivable à tout moment.
                </p>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <div className="flex items-center gap-2">
                  <label className="text-2xs uppercase tracking-wider text-fg-muted font-semibold">
                    Heure
                  </label>
                  <select
                    value={draft.daily_briefing_hour ?? 7}
                    onChange={(e) => setDraft((d) => ({
                      ...d, daily_briefing_hour: parseInt(e.target.value, 10),
                    }))}
                    disabled={!draft.daily_briefing_enabled}
                    className="bg-bg-base border border-border rounded-md px-2 py-1.5 text-sm tabular disabled:opacity-50"
                  >
                    {Array.from({ length: 24 }, (_, h) => (
                      <option key={h} value={h}>
                        {h.toString().padStart(2, '0')}:00
                      </option>
                    ))}
                  </select>
                </div>
                <Switch
                  checked={draft.daily_briefing_enabled ?? true}
                  onChange={() => toggle('daily_briefing_enabled')}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Assistant IA — Lot 2 */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Assistant IA</h2>
          </div>
          <div className="card divide-y divide-border">
            <ToggleLine
              icon={<Bot size={14} />}
              label="Agent IA proactif"
              hint={
                "L'IA scrute en arrière-plan les plans et décisions qui dérivent, "
                + "et vous envoie un message d'alerte dans le sidebar chat avec une "
                + "suggestion d'action. Ciblé : vous ne recevez que les sujets dont "
                + "vous êtes responsable. Fréquence : toutes les 4h, max 3 alertes "
                + "par scan, cooldown 5j par sujet."
              }
              checked={draft.proactive_agent_enabled ?? true}
              onChange={() => toggle('proactive_agent_enabled')}
            />
          </div>
        </div>

        {/* Heures de silence */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <span className="divider-accent" />
            <h2 className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">Heures de silence</h2>
          </div>
          <div className="card p-5 grid grid-cols-2 gap-4">
            <div>
              <label className="label">Début</label>
              <input
                type="time"
                className="input"
                value={(draft.quiet_hours_start ?? '') as string}
                onChange={(e) => setDraft((d) => ({ ...d, quiet_hours_start: e.target.value || null }))}
              />
            </div>
            <div>
              <label className="label">Fin</label>
              <input
                type="time"
                className="input"
                value={(draft.quiet_hours_end ?? '') as string}
                onChange={(e) => setDraft((d) => ({ ...d, quiet_hours_end: e.target.value || null }))}
              />
            </div>
            <p className="col-span-2 text-2xs text-fg-subtle">
              Les emails ne sont jamais envoyés pendant cette plage horaire (sauf urgences critiques).
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-4 pt-2">
          <PremiumButton
            variant="ghost" size="sm"
            onClick={() => testMail.mutate()}
            loading={testMail.isPending}
          >
            <Mail size={13} /> Envoyer un email de test
          </PremiumButton>
          <PremiumButton
            onClick={() => save.mutate()}
            loading={save.isPending}
            disabled={!draft || JSON.stringify(draft) === JSON.stringify(data)}
          >
            <CheckCircle2 size={14} /> Enregistrer
          </PremiumButton>
        </div>
      </section>
    </div>
  )
}

function ToggleLine({ label, hint, icon, checked, onChange }: {
  label: string; hint?: string; icon?: React.ReactNode;
  checked: boolean; onChange: () => void;
}) {
  return (
    <label className="flex items-center gap-4 px-5 py-3.5 cursor-pointer hover:bg-fg/[0.02] transition">
      {icon && <span className="text-fg-muted">{icon}</span>}
      <div className="flex-1 min-w-0">
        <div className="text-sm">{label}</div>
        {hint && <div className="text-2xs text-fg-subtle mt-0.5">{hint}</div>}
      </div>
      <Switch checked={checked} onChange={onChange} />
    </label>
  )
}

function Switch({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      type="button"
      onClick={onChange}
      className={`relative w-10 h-5 rounded-full transition shrink-0 ${
        checked ? 'bg-copper-500' : 'bg-fg/15'
      }`}
      aria-pressed={checked}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
          checked ? 'translate-x-5' : ''
        }`}
      />
    </button>
  )
}

export { BellOff }  // unused export silenced — gardé pour future "global off" toggle
