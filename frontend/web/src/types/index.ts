// Types partagés — alignés sur backend DRF (apps/common/enums.py).

export type ID = string

export type UserMini = {
  id: ID
  email: string
  first_name: string
  last_name: string
  full_name: string
  avatar?: string
  is_executive?: boolean
}

export type Priority = 'low' | 'medium' | 'high' | 'critical'
export type ImpactLevel = 'low' | 'medium' | 'high' | 'strategic'
export type MeetingStatus = 'draft' | 'scheduled' | 'in_progress' | 'completed' | 'cancelled'
export type AgendaItemStatus = 'pending' | 'in_progress' | 'discussed' | 'postponed' | 'cancelled'
export type DecisionStatus = 'proposed' | 'approved' | 'in_progress' | 'completed' | 'cancelled' | 'postponed'
export type ActionPlanStatus = 'open' | 'in_progress' | 'completed' | 'blocked' | 'cancelled'
export type ActionTaskStatus = 'todo' | 'in_progress' | 'done' | 'blocked' | 'overdue' | 'cancelled'
export type AttendanceStatus = 'invited' | 'accepted' | 'declined' | 'present' | 'absent' | 'late'

export type Meeting = {
  id: ID
  title: string
  description?: string
  meeting_type: string
  status: MeetingStatus
  scheduled_start: string
  scheduled_end: string
  actual_start?: string | null
  actual_end?: string | null
  location?: string
  video_url?: string
  chair?: ID | null
  chair_detail?: UserMini
  secretary?: ID | null
  secretary_detail?: UserMini
  quorum_min: number
  quorum_reached: boolean
  participants_count?: number
  present_count?: number
  minutes_generated_at?: string | null
  created_at: string
  updated_at: string
}

export type MeetingParticipant = {
  id: ID
  meeting: ID
  user?: ID | null
  user_detail?: UserMini
  external_email?: string
  external_name?: string
  role: 'chair' | 'secretary' | 'member' | 'invited' | 'observer'
  is_required: boolean
  invited_at: string
}

export type MeetingAttendance = {
  id: ID
  meeting: ID
  participant: ID
  participant_detail?: MeetingParticipant
  status: AttendanceStatus
  arrived_at?: string | null
  left_at?: string | null
  comment?: string
}

export type AgendaItem = {
  id: ID
  agenda: ID
  order: number
  title: string
  description_md?: string
  priority: Priority
  estimated_duration_minutes: number
  actual_duration_minutes?: number | null
  responsible?: ID | null
  responsible_detail?: UserMini
  status: AgendaItemStatus
  discussion_notes_md?: string
  started_at?: string | null
  completed_at?: string | null
}

export type Agenda = {
  id: ID
  meeting: ID
  is_validated: boolean
  validated_at?: string | null
  validated_by_detail?: UserMini
  items: AgendaItem[]
  items_count: number
  total_estimated_minutes: number
  notes_md?: string
}

export type Decision = {
  id: ID
  ref: string
  title: string
  description_md?: string
  status: DecisionStatus
  priority: Priority
  impact: ImpactLevel
  responsible?: ID | null
  responsible_detail?: UserMini
  category?: ID | null
  direction?: ID | null
  deadline?: string | null
  is_confidential: boolean
  meeting?: ID | null
  agenda_item?: ID | null
  approved_at?: string | null
  completed_at?: string | null
  has_action_plan?: boolean
  created_at: string
  updated_at: string
}

export type ActionTaskComment = {
  id: ID
  body_md: string
  author?: ID
  author_detail?: UserMini
  /** Permission de modifier/supprimer ce commentaire (auteur ou exec/staff). */
  can_modify?: boolean
  created_at: string
  updated_at?: string
}

export type ActionTask = {
  id: ID
  action_plan: ID
  action_plan_title?: string
  parent?: ID | null
  /** Numéro d'ordre intra-plan (auto-incrémenté à la création). */
  order?: number
  title: string
  description_md?: string
  priority: Priority
  status: ActionTaskStatus
  /** Responsable principal (lead) — celui qui reçoit les rappels. */
  assignee?: ID | null
  assignee_detail?: UserMini
  /** Co-responsables (collaborateurs additionnels). */
  co_assignees?: ID[]
  co_assignees_detail?: UserMini[]
  due_date?: string | null
  progress_percent: number
  is_overdue: boolean
  started_at?: string | null
  completed_at?: string | null
  subsidiary_id?: ID | null
  subsidiary_name?: string | null
  direction_id?: ID | null
  direction_name?: string | null
  /** Permission de modifier/supprimer cette tâche. */
  can_modify?: boolean
  created_at?: string
  updated_at?: string
  /** Présents sur l'endpoint detail uniquement. */
  comments?: ActionTaskComment[]
  effort_estimate_hours?: number | null
  effort_actual_hours?: number | null
}

export type ActionPlan = {
  id: ID
  decision: ID
  decision_ref?: string
  title: string
  description_md?: string
  status: ActionPlanStatus
  progress_percent: number
  owner?: ID | null
  owner_detail?: UserMini
  start_date?: string | null
  target_end_date?: string | null
  actual_end_date?: string | null
  tasks_count: number
  tasks?: ActionTask[]
  subsidiary_id?: ID | null
  subsidiary_name?: string | null
  direction_id?: ID | null
  direction_name?: string | null
  /** True si l'utilisateur connecté peut créer des tâches sur ce plan. */
  can_add_tasks?: boolean
  /** True si l'utilisateur connecté peut modifier/supprimer ce plan. */
  can_modify?: boolean
}

export type Notification = {
  id: ID
  event: string
  level: 'info' | 'success' | 'warning' | 'danger'
  priority?: 'low' | 'normal' | 'high' | 'critical'
  channel?: 'internal' | 'email' | 'sms' | 'whatsapp' | 'push'
  status?: 'pending' | 'sent' | 'read' | 'failed' | 'skipped'
  title: string
  body?: string
  link_url?: string
  action_url?: string
  subsidiary?: ID | null
  subsidiary_name?: string | null
  direction?: ID | null
  direction_name?: string | null
  seen_at?: string | null
  read_at?: string | null
  sent_at?: string | null
  failed_at?: string | null
  email_sent_at?: string | null
  error_message?: string
  metadata?: Record<string, unknown>
  is_read?: boolean
  created_at: string
}

export type BetaDashboard = {
  kpis: {
    upcoming_meetings: number
    in_progress_meetings: number
    completed_meetings_30d?: number
    pending_decisions: number
    approved_decisions: number
    my_decisions: number
    active_plans: number
    overdue_tasks: number
    my_tasks_open: number
    my_tasks_overdue: number
  }
  upcoming_meetings: Pick<Meeting, 'id' | 'title' | 'scheduled_start' | 'scheduled_end' | 'status' | 'location' | 'video_url'>[]
  next_meeting_agenda?: { id: string; title: string }[]
  top_pending_decisions?: {
    id: string
    ref: string
    title: string
    deadline: string | null
    priority: string
    responsible: string | null
    meeting_title: string | null
  }[]
  recent_notifications: Notification[]
}

export type Paginated<T> = { results: T[]; next?: string | null; previous?: string | null; count?: number }
