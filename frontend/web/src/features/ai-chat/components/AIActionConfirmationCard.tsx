/**
 * AIActionConfirmationCard — affichée sous un message assistant qui propose
 * une ou plusieurs actions (création de décision, tâche, plan…).
 *
 * L'utilisateur peut :
 *   - Confirmer → exécution réelle + lien vers l'objet créé
 *   - Annuler → status passe à "cancelled"
 *
 * États visuels selon le status :
 *   - pending   : carte cuivre, boutons Confirmer/Annuler actifs
 *   - confirmed : carte cuivre, loader (exécution en cours)
 *   - executed  : carte verte, lien vers l'objet
 *   - cancelled : carte gris-rayée, message "Annulée"
 *   - failed    : carte rouge, message d'erreur + bouton réessayer
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import {
  AlertTriangle, ArrowUpRight, Calendar, Check, CheckCircle2, Loader2,
  Sparkles, User as UserIcon, X,
} from 'lucide-react'

import { cn } from '@/utils/cn'

import { aiChatApi, aiChatKeys } from '../api'
import type { AIActionRequest, AIActionType } from '../types'

const ACTION_LABELS: Record<AIActionType, string> = {
  create_decision_draft: 'Créer une décision',
  create_action_task:    'Créer une tâche',
  create_action_plan:    'Créer un plan d\'action',
  assign_task:           'Réassigner une tâche',
  update_task_status:    'Modifier le statut',
  send_notification:     'Envoyer une notification',
}

interface Props {
  actionId: string
  conversationId: string
}

export function AIActionConfirmationCard({ actionId, conversationId }: Props) {
  const qc = useQueryClient()

  const { data: action, isLoading } = useQuery({
    queryKey: aiChatKeys.action(actionId),
    queryFn: () => aiChatApi.getAction(actionId),
    refetchInterval: (q) => {
      const data = q.state.data as AIActionRequest | undefined
      // Polling rapide tant qu'on est en pending/confirmed (transitoires)
      return data && (data.status === 'pending' || data.status === 'confirmed')
        ? 2000 : false
    },
  })

  const confirm = useMutation({
    mutationFn: () => aiChatApi.confirmAction(actionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: aiChatKeys.action(actionId) })
      qc.invalidateQueries({ queryKey: aiChatKeys.messages(conversationId) })
    },
  })

  const cancel = useMutation({
    mutationFn: () => aiChatApi.cancelAction(actionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: aiChatKeys.action(actionId) })
      qc.invalidateQueries({ queryKey: aiChatKeys.messages(conversationId) })
    },
  })

  if (isLoading || !action) {
    return (
      <div className="my-2 p-3 rounded-lg border border-border bg-bg-elevated flex items-center gap-2 text-xs text-fg-muted">
        <Loader2 size={13} className="animate-spin" /> Chargement de l'action…
      </div>
    )
  }

  const isPending   = action.status === 'pending'
  const isConfirmed = action.status === 'confirmed'
  const isExecuted  = action.status === 'executed'
  const isCancelled = action.status === 'cancelled'
  const isFailed    = action.status === 'failed'

  const colors = isExecuted
    ? 'border-emerald-500/40 bg-emerald-500/5'
    : isFailed
      ? 'border-red-500/40 bg-red-500/5'
      : isCancelled
        ? 'border-border bg-bg-base opacity-60'
        : 'border-copper-500/40 bg-copper-500/5'

  // Construit le lien vers l'objet créé selon result_object_type
  let resultLink: { to: string; params: any; label: string } | null = null
  if (isExecuted && action.result_object_id) {
    const t = action.result_object_type
    if (t === 'decisions.decision') {
      resultLink = {
        to: '/decisions/$id',
        params: { id: action.result_object_id },
        label: 'Voir la décision',
      }
    } else if (t === 'action_plans.actionplan') {
      resultLink = {
        to: '/action-plans/$id',
        params: { id: action.result_object_id },
        label: 'Voir le plan',
      }
    } else if (t === 'action_plans.actiontask') {
      resultLink = {
        to: '/tasks/$id',
        params: { id: action.result_object_id },
        label: 'Voir la tâche',
      }
    }
  }

  return (
    <div className={cn('my-2.5 rounded-lg border p-3', colors)}>
      <div className="flex items-center gap-2 mb-2 text-2xs uppercase tracking-widest font-semibold">
        <Sparkles size={11} className="text-copper-400" />
        <span className="text-copper-400">
          {ACTION_LABELS[action.action_type] ?? action.action_type}
        </span>
        <StatusBadge status={action.status} />
      </div>

      {/* Résumé de l'action (texte humain) */}
      {action.summary && (
        <p className="text-sm font-medium mb-2 leading-snug">
          {action.summary}
        </p>
      )}

      {/* Détails du payload (clés clés affichées si présentes) */}
      <PayloadPreview payload={action.payload} actionType={action.action_type} />

      {/* Erreur si échec */}
      {isFailed && action.error_message && (
        <div className="mt-2 p-2 rounded bg-red-500/10 text-red-300 text-xs flex items-start gap-2">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" />
          <span>{action.error_message}</span>
        </div>
      )}

      {/* Actions */}
      <div className="mt-3 flex items-center gap-2 flex-wrap">
        {isPending && (
          <>
            <button
              type="button"
              onClick={() => confirm.mutate()}
              disabled={confirm.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-copper-500 hover:bg-copper-600 text-white text-xs font-semibold disabled:opacity-50"
            >
              {confirm.isPending
                ? <Loader2 size={12} className="animate-spin" />
                : <Check size={12} />}
              Confirmer la création
            </button>
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border hover:bg-fg/5 text-xs font-medium text-fg-muted disabled:opacity-50"
            >
              <X size={12} /> Annuler
            </button>
          </>
        )}

        {isConfirmed && (
          <div className="text-xs text-fg-muted flex items-center gap-2">
            <Loader2 size={12} className="animate-spin" /> Exécution en cours…
          </div>
        )}

        {isExecuted && resultLink && (
          <Link
            to={resultLink.to}
            params={resultLink.params}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 text-xs font-semibold border border-emerald-500/30"
          >
            {resultLink.label}
            <ArrowUpRight size={11} />
          </Link>
        )}

        {isFailed && (
          <button
            type="button"
            onClick={() => confirm.mutate()}
            disabled={confirm.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-red-500/40 hover:bg-red-500/5 text-xs font-medium text-red-300 disabled:opacity-50"
          >
            <Loader2 size={12} className={confirm.isPending ? 'animate-spin' : 'hidden'} />
            Réessayer
          </button>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: AIActionRequest['status'] }) {
  const STYLE: Record<AIActionRequest['status'], string> = {
    pending:   'bg-copper-500/15 text-copper-400 border-copper-500/30',
    confirmed: 'bg-copper-500/25 text-copper-400 border-copper-500/40',
    executed:  'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    cancelled: 'bg-fg/10 text-fg-muted border-border',
    failed:    'bg-red-500/15 text-red-300 border-red-500/30',
  }
  const LABEL: Record<AIActionRequest['status'], string> = {
    pending:   'En attente',
    confirmed: 'En cours',
    executed:  '✓ Créée',
    cancelled: 'Annulée',
    failed:    'Échec',
  }
  return (
    <span className={cn(
      'ml-auto text-2xs px-1.5 py-0.5 rounded border tracking-wider',
      STYLE[status],
    )}>
      {LABEL[status]}
    </span>
  )
}

function PayloadPreview({
  payload,
}: { payload: Record<string, unknown>; actionType: AIActionType }) {
  // Sélection des clés pertinentes selon le type d'action
  const ROWS: Array<[string, string, any]> = []  // [icon-name, label, value]

  const title = payload.title as string | undefined
  if (title) ROWS.push(['title', 'Titre', title])

  const description = payload.description as string | undefined
  if (description) ROWS.push(['desc', 'Description', description])

  const assignee = (payload.assignee_email || payload.assignee_name) as string | undefined
  if (assignee) ROWS.push(['user', 'Responsable', assignee])

  const dueDate = (payload.due_date || payload.deadline
                   || payload.target_end_date) as string | undefined
  if (dueDate) ROWS.push(['cal', 'Échéance', dueDate])

  const priority = payload.priority as string | undefined
  if (priority) ROWS.push(['prio', 'Priorité', priority])

  if (ROWS.length === 0) return null

  return (
    <dl className="text-xs space-y-1 mt-2 pl-1 border-l-2 border-copper-500/20 pl-2.5">
      {ROWS.map(([key, label, value]) => (
        <div key={key} className="flex items-start gap-2">
          {key === 'cal' && <Calendar size={11} className="text-fg-subtle mt-0.5 shrink-0" />}
          {key === 'user' && <UserIcon size={11} className="text-fg-subtle mt-0.5 shrink-0" />}
          {key === 'prio' && <CheckCircle2 size={11} className="text-fg-subtle mt-0.5 shrink-0" />}
          <dt className="text-fg-muted text-2xs uppercase tracking-wider shrink-0 w-20 pt-0.5">
            {label}
          </dt>
          <dd className="flex-1 text-fg">{String(value)}</dd>
        </div>
      ))}
    </dl>
  )
}
