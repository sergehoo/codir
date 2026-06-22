/**
 * LiveCodirMode — overlay plein écran pour piloter un CODIR en direct.
 *
 * - Affiche par défaut TOUTES les tâches ouvertes (toutes réunions confondues)
 * - Meeting devient un FILTRE optionnel (pas obligatoire)
 * - Édition inline : statut, deadline, responsable, priorité, commentaire
 * - Sélection multiple → bulk update (status / deadline / assignee / priorité + comment)
 * - Bouton "Générer le CR" actif uniquement si un meeting est filtré
 * - Sortie via bouton X ou touche Esc
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { format, parseISO } from 'date-fns'
import { fr } from 'date-fns/locale'
import { Download, Plus, Scale, Search, Square, SquareCheck, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { apiClient } from '@/api/client'
import { decisionsApi } from '@/features/decisions/api'

import { actionPlansApi, meetingsExportApi, plansKeys } from './api'
import type { ActionPlan, ActionTask, Paginated } from '@/types'

interface Meeting {
  id: string
  title: string
  scheduled_start: string
  status: string
}

interface User {
  id: string
  email: string
  first_name: string
  last_name: string
}

// ─── Mappings statuts → label + couleur ────────────────────────────
const STATUS_OPTIONS: { value: string; label: string; tone: string }[] = [
  { value: 'todo',        label: 'Non démarré', tone: 'bg-slate-100 text-slate-700' },
  { value: 'in_progress', label: 'En cours',    tone: 'bg-blue-100  text-blue-800'  },
  { value: 'blocked',     label: 'En attente',  tone: 'bg-amber-100 text-amber-800' },
  { value: 'overdue',     label: 'En retard',   tone: 'bg-red-100   text-red-800'   },
  { value: 'done',        label: 'Terminé',     tone: 'bg-green-100 text-green-800' },
]

const PRIORITY_OPTIONS = [
  { value: 'low',      label: 'Faible' },
  { value: 'medium',   label: 'Moyen' },
  { value: 'high',     label: 'Élevé' },
  { value: 'critical', label: 'Critique' },
]

// ─── Composant principal ────────────────────────────────────────────
export function LiveCodirMode({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()

  const { data: meetings } = useQuery({
    queryKey: ['meetings', 'recent-codir'],
    queryFn: async () => {
      const r = await apiClient.get<Paginated<Meeting> | Meeting[]>(
        '/meetings/?ordering=-scheduled_start&page_size=20',
      )
      const list = Array.isArray(r.data) ? r.data : r.data.results
      return list
    },
  })

  // ── Filtres (tous optionnels — "" = pas de filtre) ──
  const [filterMeetingId, setFilterMeetingId] = useState<string>('')
  const [filterAssignee, setFilterAssignee]   = useState<string>('')
  const [filterStatus, setFilterStatus]       = useState<string>('')
  const [filterSubsidiary, setFilterSubsidiary] = useState<string>('')
  const [filterDirection, setFilterDirection]   = useState<string>('')
  const [filterScope, setFilterScope]         = useState<'open' | 'all'>('open')
  const [search, setSearch]                   = useState('')
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set())
  const [bulkComment, setBulkComment]         = useState('')
  // Lot Live — Quick create inline.
  // `quickTaskCtx` porte le contexte hiérarchique pré-rempli quand on clique
  // sur un bouton "+ Tâche" inline (filiale/direction/dossier). null = modal
  // ouverte sans préremplissage (bouton global topbar).
  const [quickTaskOpen, setQuickTaskOpen]         = useState(false)
  const [quickTaskCtx, setQuickTaskCtx]           = useState<{
    subsidiaryId?: string
    subsidiaryName?: string
    directionId?: string
    directionName?: string
    planId?: string
    planTitle?: string
  } | null>(null)
  const [quickDecisionOpen, setQuickDecisionOpen] = useState(false)

  const openQuickTask = (ctx: typeof quickTaskCtx = null) => {
    setQuickTaskCtx(ctx)
    setQuickTaskOpen(true)
  }

  // ── Chargement des tâches : par défaut TOUTES (toutes réunions confondues) ──
  // Si filterMeetingId est défini → restriction à ce meeting via le filterset DRF
  // NB : on utilise `/tasks/all/` (2 segments) au lieu de `/tasks/` car ce
  // dernier peut être capté par `<pk>/` du plans_router selon l'ordre des URLs.
  const { data: tasksRaw, isLoading: tasksLoading } = useQuery({
    queryKey: ['live-codir', 'tasks', filterMeetingId, filterScope],
    queryFn: async () => {
      const params = new URLSearchParams({ page_size: '500' })
      if (filterMeetingId) params.set('meeting', filterMeetingId)
      const r = await apiClient.get<Paginated<ActionTask> | ActionTask[]>(
        `/action-plans/tasks/all/?${params.toString()}`,
      )
      return r.data
    },
    refetchInterval: 15_000,
  })

  const tasks = useMemo<ActionTask[]>(() => {
    if (!tasksRaw) return []
    const arr = Array.isArray(tasksRaw) ? tasksRaw : tasksRaw.results
    return arr ?? []
  }, [tasksRaw])

  // Liste des users de l'org pour les selects (assignee)
  const { data: users } = useQuery({
    queryKey: ['users', 'org'],
    queryFn: async () => {
      const r = await apiClient.get<Paginated<User> | User[]>('/auth/users/?page_size=200')
      return Array.isArray(r.data) ? r.data : r.data.results ?? []
    },
  })

  // Filtres + recherche
  const filtered = useMemo(() => {
    return tasks.filter((t) => {
      // Périmètre : par défaut on cache les terminées + annulées
      if (filterScope === 'open' && ['done', 'cancelled'].includes(t.status)) return false
      if (filterStatus && t.status !== filterStatus) return false
      if (filterAssignee && t.assignee !== filterAssignee) return false
      if (filterSubsidiary) {
        // "__none__" = tâches sans filiale rattachée (cas Groupe)
        if (filterSubsidiary === '__none__') {
          if (t.subsidiary_id) return false
        } else if (t.subsidiary_id !== filterSubsidiary) {
          return false
        }
      }
      if (filterDirection) {
        if (filterDirection === '__none__') {
          if (t.direction_id) return false
        } else if (t.direction_id !== filterDirection) {
          return false
        }
      }
      if (search) {
        const s = search.toLowerCase()
        const assigneeName = users?.find((u) => u.id === t.assignee)
        const fullName = assigneeName
          ? `${assigneeName.first_name} ${assigneeName.last_name}`.toLowerCase()
          : ''
        const hit = (
          (t.title || '').toLowerCase().includes(s) ||
          (t.description_md || '').toLowerCase().includes(s) ||
          fullName.includes(s)
        )
        if (!hit) return false
      }
      return true
    })
  }, [tasks, filterStatus, filterAssignee, filterSubsidiary, filterDirection, filterScope, search, users])

  // Liste unique des filiales présentes dans les tâches chargées
  const subsidiaryOptions = useMemo(() => {
    const map = new Map<string, string>()
    let hasNone = false
    tasks.forEach((t) => {
      if (t.subsidiary_id && t.subsidiary_name) {
        map.set(t.subsidiary_id, t.subsidiary_name)
      } else {
        hasNone = true
      }
    })
    const arr = Array.from(map.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))
    if (hasNone) arr.push({ id: '__none__', name: 'Sans filiale (Groupe)' })
    return arr
  }, [tasks])

  // Liste unique des directions — filtrée par filiale sélectionnée si applicable.
  // Aligné sur la logique de récupération de ActionPlansListPage : on s'appuie
  // sur `direction_id` / `direction_name` exposés par l'API tâches.
  const directionOptions = useMemo(() => {
    const map = new Map<string, string>()
    let hasNone = false
    tasks.forEach((t) => {
      // Si une filiale est filtrée, ne lister que les directions de cette filiale
      if (filterSubsidiary) {
        if (filterSubsidiary === '__none__') {
          if (t.subsidiary_id) return
        } else if (t.subsidiary_id !== filterSubsidiary) {
          return
        }
      }
      if (t.direction_id && t.direction_name) {
        map.set(t.direction_id, t.direction_name)
      } else {
        hasNone = true
      }
    })
    const arr = Array.from(map.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))
    if (hasNone) arr.push({ id: '__none__', name: 'Sans direction' })
    return arr
  }, [tasks, filterSubsidiary])

  // Groupement hiérarchique : Filiale → Direction → Dossier → Tâches.
  // Aligné avec ActionPlansListPage : "Sans filiale" et "Sans direction"
  // remontent en fin de liste (pas tri alpha pur).
  const groupedTasks = useMemo(() => {
    const SUB_DEFAULT = 'Sans filiale (Groupe)'
    const DIR_DEFAULT = 'Sans direction'

    type PlanGroup = { planId: string; planTitle: string; tasks: ActionTask[] }
    type DirGroup  = { dirId: string; dirName: string; plans: Map<string, PlanGroup> }
    type SubGroup  = { subId: string; subName: string; dirs: Map<string, DirGroup> }

    const subs = new Map<string, SubGroup>()
    for (const t of filtered) {
      const subId   = t.subsidiary_id ?? '__none__'
      const subName = t.subsidiary_name ?? SUB_DEFAULT
      const dirId   = t.direction_id ?? '__none__'
      const dirName = t.direction_name ?? DIR_DEFAULT
      const planId   = t.action_plan
      const planTitle = t.action_plan_title || 'Dossier'

      let sub = subs.get(subId)
      if (!sub) {
        sub = { subId, subName, dirs: new Map() }
        subs.set(subId, sub)
      }
      let dir = sub.dirs.get(dirId)
      if (!dir) {
        dir = { dirId, dirName, plans: new Map() }
        sub.dirs.set(dirId, dir)
      }
      let plan = dir.plans.get(planId)
      if (!plan) {
        plan = { planId, planTitle, tasks: [] }
        dir.plans.set(planId, plan)
      }
      plan.tasks.push(t)
    }

    // Tri qui pousse les valeurs "défaut" (sans filiale/direction) en fin de liste.
    const sortPushDefaultLast = <T,>(arr: T[], getLabel: (x: T) => string, defaultLabel: string) =>
      arr.sort((a, b) => {
        const la = getLabel(a)
        const lb = getLabel(b)
        if (la === defaultLabel) return 1
        if (lb === defaultLabel) return -1
        return la.localeCompare(lb)
      })

    return sortPushDefaultLast(
      Array.from(subs.values()).map((sub) => ({
        ...sub,
        directions: sortPushDefaultLast(
          Array.from(sub.dirs.values()).map((dir) => ({
            ...dir,
            plans: Array.from(dir.plans.values())
              .sort((a, b) => a.planTitle.localeCompare(b.planTitle))
              .map((p) => ({
                ...p,
                tasks: [...p.tasks].sort(
                  (a, b) => (a.order ?? 9999) - (b.order ?? 9999),
                ),
              })),
          })),
          (d) => d.dirName,
          DIR_DEFAULT,
        ),
      })),
      (s) => s.subName,
      SUB_DEFAULT,
    )
  }, [filtered])

  // ─── Mutations ──
  const updateMut = useMutation({
    mutationFn: async (vars: {
      taskId: string
      patch: { status?: string; due_date?: string | null; priority?: string }
    }) => {
      // On utilise le bulk endpoint avec 1 seule tâche pour rester DRY
      return actionPlansApi.bulkUpdate([vars.taskId], vars.patch)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['live-codir', 'tasks'] })
      qc.invalidateQueries({ queryKey: plansKeys.all })
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Erreur de sauvegarde'),
  })

  const delegateMut = useMutation({
    mutationFn: ({ taskId, assignee }: { taskId: string; assignee: string }) =>
      actionPlansApi.delegateTask(taskId, assignee),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['live-codir', 'tasks'] })
      toast.success('Tâche déléguée')
    },
    onError: () => toast.error('Échec de la délégation'),
  })

  const commentMut = useMutation({
    mutationFn: ({ taskId, body_md }: { taskId: string; body_md: string }) =>
      actionPlansApi.addTaskComment(taskId, body_md),
    onSuccess: () => toast.success('Commentaire ajouté'),
    onError: () => toast.error('Échec de l\'ajout du commentaire'),
  })

  const bulkMut = useMutation({
    mutationFn: (updates: any) =>
      actionPlansApi.bulkUpdate(Array.from(selectedTaskIds), updates),
    onSuccess: (data) => {
      toast.success(`${data.updated} tâche(s) mises à jour`)
      setSelectedTaskIds(new Set())
      setBulkComment('')
      qc.invalidateQueries({ queryKey: ['live-codir', 'tasks'] })
      qc.invalidateQueries({ queryKey: plansKeys.all })
    },
    onError: () => toast.error('Échec du bulk update'),
  })

  // ─── Helpers UI ──
  const toggleSelect = (id: string) => {
    setSelectedTaskIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  const selectAll = () => setSelectedTaskIds(new Set(filtered.map((t) => t.id)))
  const clearSelection = () => setSelectedTaskIds(new Set())

  // Esc → sortie
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // ─── Stats résumé ──
  const stats = useMemo(() => {
    const total = filtered.length
    return {
      total,
      done:      filtered.filter((t) => t.status === 'done').length,
      progress:  filtered.filter((t) => t.status === 'in_progress').length,
      blocked:   filtered.filter((t) => t.status === 'blocked').length,
      overdue:   filtered.filter((t) => t.status === 'overdue').length,
      todo:      filtered.filter((t) => t.status === 'todo').length,
    }
  }, [filtered])

  const currentMeeting = meetings?.find((m) => m.id === filterMeetingId)

  return (
    <div className="fixed inset-0 z-50 bg-bg-base text-fg overflow-y-auto">
      {/* ─── Top bar ─── */}
      <header className="sticky top-0 z-10 bg-bg-elevated border-b border-border shadow-sm">
        <div className="px-8 py-4 flex items-center gap-4">
          <div className="flex-1">
            <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold mb-1">
              Live CODIR Mode
            </div>
            <div className="serif text-xl font-bold leading-tight">
              {filterMeetingId && currentMeeting
                ? `${currentMeeting.title} — ${format(parseISO(currentMeeting.scheduled_start), 'd MMM yyyy', { locale: fr })}`
                : 'Toutes les tâches actives'}
            </div>
            <div className="text-xs text-fg-muted mt-0.5">
              {filterMeetingId
                ? 'Filtré sur 1 réunion · changez le filtre ci-dessous pour voir d\'autres réunions'
                : 'Toutes réunions confondues · utilisez le filtre Réunion pour cibler'}
            </div>
          </div>

          {/* Lot Live — Quick create : éviter de quitter la page ─────── */}
          <button
            type="button"
            onClick={() => openQuickTask(null)}
            title="Créer une tâche sans quitter le Live CODIR"
            className="px-3 py-2 rounded-md bg-bg-base border border-border hover:border-copper-500 hover:text-copper-400 text-sm font-medium flex items-center gap-2"
          >
            <Plus size={15} /> Tâche
          </button>

          <button
            type="button"
            onClick={() => setQuickDecisionOpen(true)}
            title="Acter une décision sans quitter le Live CODIR"
            className="px-3 py-2 rounded-md bg-bg-base border border-border hover:border-copper-500 hover:text-copper-400 text-sm font-medium flex items-center gap-2"
          >
            <Scale size={15} /> Décision
          </button>

          <button
            type="button"
            onClick={() => {
              if (!filterMeetingId) return
              window.open(meetingsExportApi.exportCrDocxUrl(filterMeetingId), '_blank')
            }}
            disabled={!filterMeetingId}
            title={filterMeetingId
              ? 'Génère le CR du CODIR filtré'
              : 'Sélectionnez d\'abord une réunion via le filtre ci-dessous'}
            className="px-4 py-2 rounded-md bg-copper-500 hover:bg-copper-400 text-white text-sm font-semibold flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Download size={16} /> Générer le CR
          </button>

          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-md hover:bg-bg-base text-fg-muted hover:text-fg"
            title="Quitter le Live Mode (Esc)"
          >
            <X size={22} />
          </button>
        </div>

        {/* Stats ribbon */}
        <div className="px-8 pb-3 flex flex-wrap items-center gap-3 text-sm">
          <Stat label="Total"      value={stats.total} />
          <Stat label="Terminé"    value={stats.done}     tone="success" />
          <Stat label="En cours"   value={stats.progress} tone="info" />
          <Stat label="Bloqué"     value={stats.blocked}  tone="warning" />
          <Stat label="En retard"  value={stats.overdue}  tone="danger" />
          <Stat label="Non démarré" value={stats.todo} />
        </div>

        {/* Filtres */}
        <div className="px-8 pb-4 flex flex-wrap items-center gap-3 text-sm border-t border-border pt-3">
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher…"
              className="w-full pl-9 pr-3 py-2 rounded-md bg-bg-base border border-border"
            />
          </div>

          {/* Filtre réunion (optionnel) */}
          <select
            value={filterMeetingId}
            onChange={(e) => setFilterMeetingId(e.target.value)}
            className="bg-bg-base border border-border rounded-md px-3 py-2 min-w-[220px]"
            title="Filtrer par réunion CODIR"
          >
            <option value="">Toutes réunions</option>
            {meetings?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.title.slice(0, 40)} — {format(parseISO(m.scheduled_start), 'd MMM yyyy', { locale: fr })}
              </option>
            ))}
          </select>

          {/* Périmètre : ouvertes uniquement vs toutes */}
          <select
            value={filterScope}
            onChange={(e) => setFilterScope(e.target.value as 'open' | 'all')}
            className="bg-bg-base border border-border rounded-md px-3 py-2"
            title="Périmètre"
          >
            <option value="open">Tâches ouvertes</option>
            <option value="all">Toutes (incl. terminées)</option>
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-bg-base border border-border rounded-md px-3 py-2"
          >
            <option value="">Tous statuts</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <select
            value={filterAssignee}
            onChange={(e) => setFilterAssignee(e.target.value)}
            className="bg-bg-base border border-border rounded-md px-3 py-2 min-w-[200px]"
          >
            <option value="">Tous responsables</option>
            {users?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.first_name} {u.last_name}
              </option>
            ))}
          </select>

          {/* Filtre filiale */}
          <select
            value={filterSubsidiary}
            onChange={(e) => {
              setFilterSubsidiary(e.target.value)
              // Reset direction si elle n'appartient plus à la nouvelle filiale
              setFilterDirection('')
            }}
            className="bg-bg-base border border-border rounded-md px-3 py-2 min-w-[180px]"
            title="Filtrer par filiale"
          >
            <option value="">Toutes filiales</option>
            {subsidiaryOptions.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          {/* Filtre direction (limité à la filiale sélectionnée si applicable) */}
          <select
            value={filterDirection}
            onChange={(e) => setFilterDirection(e.target.value)}
            className="bg-bg-base border border-border rounded-md px-3 py-2 min-w-[180px]"
            title="Filtrer par direction"
            disabled={directionOptions.length === 0}
          >
            <option value="">Toutes directions</option>
            {directionOptions.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </div>
      </header>

      {/* ─── Modals Quick Create (Live) ─── */}
      {quickTaskOpen && (
        <QuickCreateTaskModal
          users={users || []}
          defaultMeetingId={filterMeetingId || ''}
          preset={quickTaskCtx || {}}
          onClose={() => { setQuickTaskOpen(false); setQuickTaskCtx(null) }}
          onCreated={() => {
            qc.invalidateQueries({ queryKey: ['live-codir', 'tasks'] })
            qc.invalidateQueries({ queryKey: plansKeys.all })
            toast.success('Tâche créée')
            setQuickTaskOpen(false)
            setQuickTaskCtx(null)
          }}
        />
      )}
      {quickDecisionOpen && (
        <QuickCreateDecisionModal
          users={users || []}
          defaultMeetingId={filterMeetingId || ''}
          onClose={() => setQuickDecisionOpen(false)}
          onCreated={() => {
            qc.invalidateQueries({ queryKey: ['live-codir', 'tasks'] })
            qc.invalidateQueries({ queryKey: ['decisions'] })
            toast.success('Décision créée')
            setQuickDecisionOpen(false)
          }}
        />
      )}

      {/* ─── Bulk action bar ─── */}
      {selectedTaskIds.size > 0 && (
        <BulkActionBar
          count={selectedTaskIds.size}
          users={users || []}
          onClear={clearSelection}
          onApply={(updates) => bulkMut.mutate(updates)}
          loading={bulkMut.isPending}
          comment={bulkComment}
          onCommentChange={setBulkComment}
        />
      )}

      {/* ─── Liste des tâches ─── */}
      <main className="px-8 py-6 space-y-2">
        {tasksLoading && <div className="text-center text-fg-muted py-12">Chargement…</div>}

        {!tasksLoading && filtered.length === 0 && (
          <div className="text-center text-fg-muted py-12">
            {filterMeetingId || filterStatus || filterAssignee || filterSubsidiary || filterDirection || search
              ? 'Aucune tâche ne correspond aux filtres — relâchez les critères.'
              : filterScope === 'open'
                ? 'Aucune tâche ouverte. Basculez sur "Toutes" pour voir les terminées.'
                : 'Aucune tâche en base.'}
          </div>
        )}

        {filtered.length > 0 && (
          <div className="flex items-center justify-between text-2xs uppercase tracking-widest text-fg-muted font-semibold pb-2">
            <button
              type="button"
              onClick={selectedTaskIds.size === filtered.length ? clearSelection : selectAll}
              className="flex items-center gap-2 hover:text-fg"
            >
              {selectedTaskIds.size === filtered.length ? <SquareCheck size={14} /> : <Square size={14} />}
              {selectedTaskIds.size === filtered.length ? 'Tout désélectionner' : 'Tout sélectionner'}
            </button>
            <span>{filtered.length} tâche(s)</span>
          </div>
        )}

        {/* ─── Groupement hiérarchique : Filiale → Direction → Plan → Tâches ─── */}
        {groupedTasks.map((sub) => (
          <section key={sub.subId} className="mb-8 last:mb-0">
            {/* Niveau 1 — Filiale */}
            <header className="flex items-center gap-3 pb-2 mb-3 border-b border-copper-500/30">
              <span className="w-1 h-6 bg-copper-500 rounded-full" />
              <h2 className="serif text-xl font-semibold">{sub.subName}</h2>
              <span className="text-2xs uppercase tracking-wider text-copper-400 font-semibold bg-copper-500/10 px-2 py-0.5 rounded">
                {sub.directions.reduce(
                  (acc, d) => acc + d.plans.reduce((a, p) => a + p.tasks.length, 0),
                  0,
                )} tâches
              </span>
              {/* + Tâche au niveau Filiale */}
              <button
                type="button"
                onClick={() => openQuickTask({
                  subsidiaryId:   sub.subId === '__none__' ? '' : sub.subId,
                  subsidiaryName: sub.subName,
                })}
                title={`Ajouter une tâche pour ${sub.subName}`}
                className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-copper-500/30 text-copper-400 text-xs font-semibold hover:bg-copper-500/10 hover:border-copper-500/60 transition"
              >
                <Plus size={12} /> Tâche
              </button>
            </header>

            {sub.directions.map((dir) => (
              <div key={`${sub.subId}-${dir.dirId}`} className="mb-5 last:mb-0">
                {/* Niveau 2 — Direction */}
                <div className="flex items-center gap-3 mb-2 ml-1">
                  <span className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
                    {dir.dirName}
                  </span>
                  <span className="flex-1 h-px bg-border" />
                  <span className="text-2xs text-fg-subtle">
                    {dir.plans.length} Dossier{dir.plans.length > 1 ? 's' : ''}
                  </span>
                  {/* + Tâche au niveau Direction */}
                  <button
                    type="button"
                    onClick={() => openQuickTask({
                      subsidiaryId:   sub.subId === '__none__' ? '' : sub.subId,
                      subsidiaryName: sub.subName,
                      directionId:    dir.dirId === '__none__' ? '' : dir.dirId,
                      directionName:  dir.dirName,
                    })}
                    title={`Ajouter une tâche pour ${dir.dirName}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-2xs uppercase tracking-wider text-fg-muted hover:text-copper-400 hover:bg-copper-500/10 transition"
                  >
                    <Plus size={11} /> Tâche
                  </button>
                </div>

                {dir.plans.map((plan) => (
                  <div
                    key={`${dir.dirId}-${plan.planId}`}
                    className="mb-3 last:mb-0 ml-3"
                  >
                    {/* Niveau 3 — Dossier (plan d'action) */}
                    <div className="flex items-center gap-2 mb-1.5 px-1">
                      <span className="text-2xs uppercase tracking-wider text-copper-400 font-semibold">
                        Dossier
                      </span>
                      <span className="text-sm font-medium truncate text-fg">{plan.planTitle}</span>
                      <span className="text-2xs text-fg-subtle">
                        · {plan.tasks.length} tâche{plan.tasks.length > 1 ? 's' : ''}
                      </span>
                      {/* + Tâche au niveau Dossier (le plus utile — 1-clic) */}
                      <button
                        type="button"
                        onClick={() => openQuickTask({
                          subsidiaryId:   sub.subId === '__none__' ? '' : sub.subId,
                          subsidiaryName: sub.subName,
                          directionId:    dir.dirId === '__none__' ? '' : dir.dirId,
                          directionName:  dir.dirName,
                          planId:         plan.planId,
                          planTitle:      plan.planTitle,
                        })}
                        title={`Ajouter une tâche au dossier "${plan.planTitle}"`}
                        className="ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded text-2xs text-copper-400 hover:bg-copper-500/10 transition"
                      >
                        <Plus size={11} /> Tâche ici
                      </button>
                    </div>

                    {/* Niveau 4 — Tâches */}
                    <div className="space-y-1.5 ml-2">
                      {plan.tasks.map((task) => (
                        <TaskRow
                          key={task.id}
                          task={task}
                          users={users || []}
                          selected={selectedTaskIds.has(task.id)}
                          onToggleSelect={() => toggleSelect(task.id)}
                          onUpdate={(patch) => updateMut.mutate({ taskId: task.id, patch })}
                          onDelegate={(assignee) => delegateMut.mutate({ taskId: task.id, assignee })}
                          onComment={(body_md) => commentMut.mutate({ taskId: task.id, body_md })}
                          saving={updateMut.isPending || delegateMut.isPending}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </section>
        ))}
      </main>

      {/* ─── Footer info ─── */}
      <footer className="px-8 py-4 border-t border-border text-2xs text-fg-muted text-center">
        {currentMeeting ? `${currentMeeting.title} · ` : ''}
        Esc pour quitter · Auto-refresh toutes les 15s · {filtered.length} tâche{filtered.length > 1 ? 's' : ''} affichée{filtered.length > 1 ? 's' : ''}
      </footer>
    </div>
  )
}

// ─── Sous-composants ────────────────────────────────────────────────

function Stat({ label, value, tone = 'neutral' }: { label: string; value: number; tone?: string }) {
  const colors: Record<string, string> = {
    neutral: 'bg-bg-base',
    success: 'bg-green-50 text-green-800',
    info:    'bg-blue-50  text-blue-800',
    warning: 'bg-amber-50 text-amber-800',
    danger:  'bg-red-50   text-red-800',
  }
  return (
    <span className={`px-3 py-1 rounded-md text-xs font-semibold flex items-center gap-2 ${colors[tone]}`}>
      <span className="opacity-60 uppercase tracking-wide">{label}</span>
      <span className="tabular-nums">{value}</span>
    </span>
  )
}

function StatusPill({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const current = STATUS_OPTIONS.find((s) => s.value === value) ?? STATUS_OPTIONS[0]
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`px-3 py-1 rounded-md text-xs font-semibold border-0 cursor-pointer ${current.tone}`}
    >
      {STATUS_OPTIONS.map((s) => (
        <option key={s.value} value={s.value}>{s.label}</option>
      ))}
    </select>
  )
}

interface TaskRowProps {
  task: ActionTask
  users: User[]
  selected: boolean
  onToggleSelect: () => void
  onUpdate: (patch: { status?: string; due_date?: string | null; priority?: string }) => void
  onDelegate: (assignee: string) => void
  onComment: (body_md: string) => void
  saving: boolean
}

function TaskRow({
  task, users, selected, onToggleSelect, onUpdate, onDelegate, onComment, saving,
}: TaskRowProps) {
  const [comment, setComment] = useState('')
  const [showComment, setShowComment] = useState(false)

  const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== 'done'

  return (
    <div
      className={`p-3 rounded-md border ${
        selected ? 'border-copper-500 bg-copper-50/30' : 'border-border bg-bg-elevated'
      } ${isOverdue ? 'border-l-4 border-l-red-500' : ''}`}
    >
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={onToggleSelect}
          className="mt-1 text-fg-muted hover:text-copper-500"
        >
          {selected ? <SquareCheck size={18} /> : <Square size={18} />}
        </button>

        <div className="flex-1 min-w-0">
          <div className="font-medium text-base truncate" title={task.title}>
            {task.order ? (
              <span className="text-copper-400 font-mono text-sm font-semibold mr-2 tabular">
                #{task.order.toString().padStart(2, '0')}
              </span>
            ) : null}
            {task.title}
          </div>
          {task.description_md && (
            <div className="text-sm text-fg-muted line-clamp-1 mt-0.5">
              {task.description_md}
            </div>
          )}
        </div>

        {/* Statut */}
        <div className="shrink-0">
          <StatusPill value={task.status} onChange={(v) => onUpdate({ status: v })} />
        </div>

        {/* Deadline */}
        <input
          type="date"
          value={task.due_date || ''}
          onChange={(e) => onUpdate({ due_date: e.target.value || null })}
          className={`w-36 px-2 py-1 rounded-md border border-border bg-bg-base text-sm ${
            isOverdue ? 'text-red-700 font-semibold' : ''
          }`}
        />

        {/* Assignee */}
        <select
          value={task.assignee || ''}
          onChange={(e) => e.target.value && onDelegate(e.target.value)}
          className="w-44 px-2 py-1 rounded-md border border-border bg-bg-base text-sm"
        >
          <option value="">— Non assigné —</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.first_name} {u.last_name}
            </option>
          ))}
        </select>

        {/* Priorité */}
        <select
          value={task.priority || 'medium'}
          onChange={(e) => onUpdate({ priority: e.target.value })}
          className="px-2 py-1 rounded-md border border-border bg-bg-base text-xs"
        >
          {PRIORITY_OPTIONS.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>

        {/* Commentaire */}
        <button
          type="button"
          onClick={() => setShowComment((v) => !v)}
          className="px-2 py-1 text-xs rounded-md hover:bg-bg-base text-fg-muted"
          title="Ajouter un commentaire de CODIR"
        >
          💬
        </button>
      </div>

      {showComment && (
        <div className="mt-3 ml-9 flex gap-2">
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && comment.trim()) {
                onComment(comment.trim())
                setComment('')
                setShowComment(false)
              }
            }}
            placeholder='Note du CODIR : "Reporté au 25/05", "Bloqué — attente budget"…'
            className="flex-1 px-3 py-2 rounded-md border border-border bg-bg-base text-sm"
            autoFocus
          />
          <button
            type="button"
            onClick={() => {
              if (comment.trim()) {
                onComment(comment.trim())
                setComment('')
                setShowComment(false)
              }
            }}
            className="px-3 py-2 rounded-md bg-copper-500 hover:bg-copper-400 text-white text-sm font-semibold"
          >
            Ajouter
          </button>
        </div>
      )}

      {saving && (
        <div className="text-2xs text-fg-muted mt-2 ml-9">Sauvegarde…</div>
      )}
    </div>
  )
}

function BulkActionBar({
  count, users, onClear, onApply, loading, comment, onCommentChange,
}: {
  count: number
  users: User[]
  onClear: () => void
  onApply: (updates: any) => void
  loading: boolean
  comment: string
  onCommentChange: (v: string) => void
}) {
  const [status, setStatus]   = useState('')
  const [dueDate, setDueDate] = useState('')
  const [assignee, setAssignee] = useState('')
  const [priority, setPriority] = useState('')

  const handleApply = () => {
    const updates: any = {}
    if (status)   updates.status = status
    if (dueDate)  updates.due_date = dueDate
    if (assignee) updates.assignee = assignee
    if (priority) updates.priority = priority
    if (comment.trim()) updates.comment = comment.trim()
    if (Object.keys(updates).length === 0) {
      toast.error('Renseignez au moins un champ à modifier')
      return
    }
    onApply(updates)
    setStatus(''); setDueDate(''); setAssignee(''); setPriority('')
  }

  return (
    <div className="sticky top-[185px] z-10 bg-copper-500 text-white px-8 py-3 shadow-lg flex items-center gap-3 flex-wrap">
      <div className="font-semibold text-sm">
        {count} tâche{count > 1 ? 's' : ''} sélectionnée{count > 1 ? 's' : ''} →
      </div>

      <select
        value={status} onChange={(e) => setStatus(e.target.value)}
        className="px-3 py-1 rounded-md bg-white text-fg text-sm"
      >
        <option value="">Statut…</option>
        {STATUS_OPTIONS.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </select>

      <input
        type="date" value={dueDate}
        onChange={(e) => setDueDate(e.target.value)}
        className="px-3 py-1 rounded-md bg-white text-fg text-sm"
      />

      <select
        value={assignee} onChange={(e) => setAssignee(e.target.value)}
        className="px-3 py-1 rounded-md bg-white text-fg text-sm"
      >
        <option value="">Responsable…</option>
        {users.map((u) => (
          <option key={u.id} value={u.id}>
            {u.first_name} {u.last_name}
          </option>
        ))}
      </select>

      <select
        value={priority} onChange={(e) => setPriority(e.target.value)}
        className="px-3 py-1 rounded-md bg-white text-fg text-sm"
      >
        <option value="">Priorité…</option>
        {PRIORITY_OPTIONS.map((p) => (
          <option key={p.value} value={p.value}>{p.label}</option>
        ))}
      </select>

      <input
        type="text"
        value={comment}
        onChange={(e) => onCommentChange(e.target.value)}
        placeholder="Commentaire (optionnel)"
        className="flex-1 min-w-[200px] px-3 py-1 rounded-md bg-white text-fg text-sm"
      />

      <button
        type="button"
        onClick={handleApply}
        disabled={loading}
        className="px-4 py-1 rounded-md bg-white text-copper-700 text-sm font-bold hover:bg-copper-50"
      >
        {loading ? '…' : 'Appliquer'}
      </button>

      <button
        type="button"
        onClick={onClear}
        className="px-2 py-1 rounded-md hover:bg-copper-400 text-sm"
      >
        Annuler
      </button>
    </div>
  )
}


// ─── QuickCreateTaskModal ───────────────────────────────────────────
// Crée une tâche directement depuis le Live CODIR. Si une réunion est
// filtrée, on récupère le plan d'action lié (decision_meeting). Sinon
// on liste tous les plans actifs pour rattachement explicite.

interface QuickTaskPreset {
  subsidiaryId?: string
  subsidiaryName?: string
  directionId?: string
  directionName?: string
  planId?: string
  planTitle?: string
}

function QuickCreateTaskModal({
  users, defaultMeetingId: _defaultMeetingId, preset, onClose, onCreated,
}: {
  users: User[]
  /** Réservé pour usage futur (rattacher une tâche à une réunion). */
  defaultMeetingId: string
  preset: QuickTaskPreset
  onClose: () => void
  onCreated: () => void
}) {
  const [title, setTitle]         = useState('')
  // planId pré-sélectionné depuis le preset si fourni (clic "+ Tâche ici" sur un dossier)
  const [planId, setPlanId]       = useState(preset.planId || '')
  const [assignee, setAssignee]   = useState('')
  const [dueDate, setDueDate]     = useState('')
  const [priority, setPriority]   = useState('medium')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Liste des plans actifs pour rattachement. On les filtre côté front sur
  // subsidiary/direction si un preset est fourni — UX beaucoup plus rapide
  // en réunion (la liste passe de 50 plans à 3-5).
  const { data: plansRaw, isLoading: plansLoading } = useQuery({
    queryKey: ['plans', 'active-for-live'],
    queryFn: async () => {
      const r = await apiClient.get<Paginated<ActionPlan> | ActionPlan[]>(
        '/action-plans/?page_size=200',
      )
      return Array.isArray(r.data) ? r.data : r.data.results ?? []
    },
  })
  const plans = useMemo<ActionPlan[]>(() => {
    let arr = (plansRaw || []).filter(
      (p) => !['completed', 'cancelled'].includes(p.status as string),
    )
    // Filtre subsidiary si défini dans le preset (les plans n'ayant pas cette
    // filiale sont cachés pour réduire le bruit)
    if (preset.subsidiaryId) {
      arr = arr.filter((p) =>
        (p as any).subsidiary_id === preset.subsidiaryId
        || (p as any).subsidiary === preset.subsidiaryId,
      )
    }
    if (preset.directionId) {
      arr = arr.filter((p) =>
        (p as any).direction_id === preset.directionId
        || (p as any).direction === preset.directionId,
      )
    }
    return arr
  }, [plansRaw, preset.subsidiaryId, preset.directionId])

  // Esc → fermer
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const createMut = useMutation({
    mutationFn: async () => {
      if (!planId) throw new Error('Choisissez un Dossier parent')
      if (!title.trim()) throw new Error('Le titre est obligatoire')
      return actionPlansApi.addTask(planId, {
        title: title.trim(),
        description_md: description.trim() || undefined,
        assignee: assignee || undefined,
        due_date: dueDate || undefined,
        priority,
        status: 'todo',
      } as any)
    },
    onSuccess: () => onCreated(),
    onError: (e: any) => setError(e?.response?.data?.detail || e?.message || 'Erreur de création'),
  })

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center p-6"
         onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-xl bg-bg-elevated border border-border rounded-xl shadow-2xl overflow-hidden">
        <header className="px-6 py-4 border-b border-border flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
              Nouvelle tâche
            </div>
            <h3 className="serif text-lg font-semibold mt-0.5">Créer une tâche d'action</h3>
            {/* Breadcrumb du contexte pré-rempli (cliquer "+ Tâche ici" remplit ça) */}
            {(preset.subsidiaryName || preset.directionName || preset.planTitle) && (
              <div className="flex items-center gap-1.5 mt-1.5 text-2xs text-copper-400 font-medium flex-wrap">
                <span className="uppercase tracking-wider text-fg-muted">Contexte :</span>
                {preset.subsidiaryName && (
                  <span className="px-1.5 py-0.5 rounded bg-copper-500/10">{preset.subsidiaryName}</span>
                )}
                {preset.directionName && (
                  <>
                    <span className="text-fg-subtle">›</span>
                    <span className="px-1.5 py-0.5 rounded bg-copper-500/10">{preset.directionName}</span>
                  </>
                )}
                {preset.planTitle && (
                  <>
                    <span className="text-fg-subtle">›</span>
                    <span className="px-1.5 py-0.5 rounded bg-copper-500/10 truncate max-w-[180px]" title={preset.planTitle}>
                      {preset.planTitle}
                    </span>
                  </>
                )}
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1 text-fg-muted hover:text-fg shrink-0" title="Fermer (Esc)">
            <X size={18} />
          </button>
        </header>

        <form
          onSubmit={(e) => { e.preventDefault(); setError(null); createMut.mutate() }}
          className="px-6 py-5 space-y-4"
        >
          <div>
            <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
              Titre <span className="text-danger">*</span>
            </label>
            <input
              type="text" value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="Ex. Préparer le budget Q3"
              autoFocus required
              className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
            />
          </div>

          <div>
            <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
              Dossier parent <span className="text-danger">*</span>
            </label>
            <select
              value={planId} onChange={(e) => setPlanId(e.target.value)}
              required
              className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
            >
              <option value="">
                {plansLoading ? 'Chargement…' : '— Choisir un Dossier —'}
              </option>
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} {p.subsidiary_name ? `(${p.subsidiary_name})` : ''}
                </option>
              ))}
            </select>
            {!preset.planId && plans.length === 0 && !plansLoading && (
              <p className="text-2xs text-warning mt-1">
                Aucun Dossier ne correspond au contexte sélectionné. Élargissez le filtre
                ou créez un Dossier depuis « Suivi Projets/Dossiers ».
              </p>
            )}
            {preset.subsidiaryName && (
              <p className="text-2xs text-fg-subtle mt-1">
                Liste filtrée sur <strong>{preset.subsidiaryName}</strong>
                {preset.directionName && <> · <strong>{preset.directionName}</strong></>}.
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
                Responsable
              </label>
              <select
                value={assignee} onChange={(e) => setAssignee(e.target.value)}
                className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
              >
                <option value="">— Non assigné —</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>{u.first_name} {u.last_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
                Échéance
              </label>
              <input
                type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
              Priorité
            </label>
            <select
              value={priority} onChange={(e) => setPriority(e.target.value)}
              className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
            >
              {PRIORITY_OPTIONS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
              Description (optionnel)
            </label>
            <textarea
              value={description} onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Précisions, livrables attendus, prérequis…"
              className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
            />
          </div>

          {error && (
            <div className="text-xs text-danger bg-danger/10 px-3 py-2 rounded">{error}</div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-md text-sm text-fg-muted hover:text-fg">
              Annuler
            </button>
            <button type="submit" disabled={createMut.isPending}
              className="px-4 py-2 rounded-md bg-copper-500 hover:bg-copper-400 text-white text-sm font-semibold disabled:opacity-50">
              {createMut.isPending ? 'Création…' : 'Créer la tâche'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}


// ─── QuickCreateDecisionModal ───────────────────────────────────────
// Acte une décision en `proposed` (à valider plus tard). Rattachée au
// meeting filtré si applicable, sinon décision libre.

function QuickCreateDecisionModal({
  users, defaultMeetingId, onClose, onCreated,
}: {
  users: User[]
  defaultMeetingId: string
  onClose: () => void
  onCreated: () => void
}) {
  const [title, setTitle]             = useState('')
  const [description, setDescription] = useState('')
  const [responsible, setResponsible] = useState('')
  const [priority, setPriority]       = useState('medium')
  const [deadline, setDeadline]       = useState('')
  const [isConfidential, setIsConfidential] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const createMut = useMutation({
    mutationFn: async () => {
      if (!title.trim()) throw new Error('Le titre est obligatoire')
      const payload: any = {
        title: title.trim(),
        description_md: description.trim() || undefined,
        responsible: responsible || undefined,
        priority,
        deadline: deadline || undefined,
        is_confidential: isConfidential,
        status: 'proposed',
      }
      if (defaultMeetingId) payload.meeting = defaultMeetingId
      return decisionsApi.create(payload)
    },
    onSuccess: () => onCreated(),
    onError: (e: any) => setError(e?.response?.data?.detail || e?.message || 'Erreur de création'),
  })

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center p-6"
         onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-xl bg-bg-elevated border border-border rounded-xl shadow-2xl overflow-hidden">
        <header className="px-6 py-4 border-b border-border flex items-center justify-between">
          <div>
            <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
              Nouvelle décision
            </div>
            <h3 className="serif text-lg font-semibold mt-0.5">Acter une décision</h3>
            {defaultMeetingId && (
              <div className="text-2xs text-fg-subtle mt-1">
                Rattachée à la réunion filtrée
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1 text-fg-muted hover:text-fg" title="Fermer (Esc)">
            <X size={18} />
          </button>
        </header>

        <form
          onSubmit={(e) => { e.preventDefault(); setError(null); createMut.mutate() }}
          className="px-6 py-5 space-y-4"
        >
          <div>
            <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
              Titre <span className="text-danger">*</span>
            </label>
            <input
              type="text" value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="Ex. Valider le budget Q3 à 3.2M€"
              autoFocus required
              className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
            />
          </div>

          <div>
            <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
              Description / contexte (optionnel)
            </label>
            <textarea
              value={description} onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Contexte, options envisagées, rationale…"
              className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
                Responsable
              </label>
              <select
                value={responsible} onChange={(e) => setResponsible(e.target.value)}
                className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
              >
                <option value="">— Non assigné —</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>{u.first_name} {u.last_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
                Échéance
              </label>
              <input
                type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)}
                className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 items-end">
            <div>
              <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
                Priorité
              </label>
              <select
                value={priority} onChange={(e) => setPriority(e.target.value)}
                className="w-full px-3 py-2 bg-bg-base border border-border rounded-md text-sm"
              >
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <label className="inline-flex items-center gap-2 text-sm pb-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isConfidential}
                onChange={(e) => setIsConfidential(e.target.checked)}
              />
              <span>Confidentiel</span>
            </label>
          </div>

          <div className="text-2xs text-fg-subtle bg-fg/[0.03] px-3 py-2 rounded">
            La décision sera créée au statut « Proposée ». Vous pourrez la valider plus tard
            depuis la page Décisions.
          </div>

          {error && (
            <div className="text-xs text-danger bg-danger/10 px-3 py-2 rounded">{error}</div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-md text-sm text-fg-muted hover:text-fg">
              Annuler
            </button>
            <button type="submit" disabled={createMut.isPending}
              className="px-4 py-2 rounded-md bg-copper-500 hover:bg-copper-400 text-white text-sm font-semibold disabled:opacity-50">
              {createMut.isPending ? 'Création…' : 'Créer la décision'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
