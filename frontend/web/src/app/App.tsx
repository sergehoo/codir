import { RouterProvider, createRouter, createRoute, createRootRoute, Outlet, redirect } from '@tanstack/react-router'

import { Shell } from '@/components/layout/Shell'
import { LoginPage } from '@/features/auth/LoginPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { MeetingsListPage } from '@/features/meetings/MeetingsListPage'
import { MeetingDetailPage } from '@/features/meetings/MeetingDetailPage'
import { MeetingCreatePage } from '@/features/meetings/MeetingCreatePage'
import { DecisionsListPage } from '@/features/decisions/DecisionsListPage'
import { DecisionDetailPage } from '@/features/decisions/DecisionDetailPage'
import { ActionPlansListPage } from '@/features/action-plans/ActionPlansListPage'
import { ActionPlanDetailPage } from '@/features/action-plans/ActionPlanDetailPage'
import { LiveCodirPage } from '@/features/action-plans/LiveCodirPage'
import { MyTasksPage } from '@/features/action-plans/MyTasksPage'
import { TaskDetailPage } from '@/features/action-plans/TaskDetailPage'
import { DocumentsPage } from '@/features/documents/DocumentsPage'
import { NotificationsPage } from '@/features/notifications/NotificationsPage'
import { NotificationPreferencesPage } from '@/features/notifications/NotificationPreferencesPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { MeetingSeriesPage } from '@/features/settings/MeetingSeriesPage'
import { MembersPage } from '@/features/settings/MembersPage'
import { SubsidiariesPage } from '@/features/settings/SubsidiariesPage'
import { SpeakerMappingPage } from '@/features/meeting-recordings/pages/SpeakerMappingPage'
import { RecordingSummaryPage } from '@/features/meeting-recordings/pages/RecordingSummaryPage'
import { useAuthStore } from '@/stores/auth'

const rootRoute = createRootRoute({ component: () => <Outlet /> })

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
})

const shellRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'shell',
  component: Shell,
  // Guard d'auth : si pas de JWT en store, on bounce vers /login
  beforeLoad: () => {
    const token = useAuthStore.getState().accessToken
    if (!token) throw redirect({ to: '/login' })
  },
})

const dashboardRoute = createRoute({ getParentRoute: () => shellRoute, path: '/', component: DashboardPage })
const meetingsList = createRoute({ getParentRoute: () => shellRoute, path: '/meetings', component: MeetingsListPage })
const meetingNew = createRoute({ getParentRoute: () => shellRoute, path: '/meetings/new', component: MeetingCreatePage })
const meetingDetail = createRoute({
  getParentRoute: () => shellRoute,
  path: '/meetings/$id',
  component: MeetingDetailPage,
})
const decisionsList = createRoute({ getParentRoute: () => shellRoute, path: '/decisions', component: DecisionsListPage })
const decisionDetail = createRoute({
  getParentRoute: () => shellRoute,
  path: '/decisions/$id',
  component: DecisionDetailPage,
})
const plansList = createRoute({ getParentRoute: () => shellRoute, path: '/action-plans', component: ActionPlansListPage })
const planDetail = createRoute({
  getParentRoute: () => shellRoute,
  path: '/action-plans/$id',
  component: ActionPlanDetailPage,
})
const myTasks = createRoute({ getParentRoute: () => shellRoute, path: '/my-tasks', component: MyTasksPage })
const liveCodir = createRoute({ getParentRoute: () => shellRoute, path: '/live-codir', component: LiveCodirPage })
const taskDetail = createRoute({ getParentRoute: () => shellRoute, path: '/tasks/$id', component: TaskDetailPage })
const notifs = createRoute({ getParentRoute: () => shellRoute, path: '/notifications', component: NotificationsPage })
const notifPrefs = createRoute({ getParentRoute: () => shellRoute, path: '/notifications/preferences', component: NotificationPreferencesPage })
const documents = createRoute({ getParentRoute: () => shellRoute, path: '/documents', component: DocumentsPage })
const profile = createRoute({ getParentRoute: () => shellRoute, path: '/profile', component: ProfilePage })
const settingsMembers = createRoute({ getParentRoute: () => shellRoute, path: '/settings/members', component: MembersPage })
const settingsSubsidiaries = createRoute({ getParentRoute: () => shellRoute, path: '/settings/subsidiaries', component: SubsidiariesPage })
const settingsMeetingSeries = createRoute({ getParentRoute: () => shellRoute, path: '/settings/meeting-series', component: MeetingSeriesPage })

// ── Meeting recordings : identification voix + résumé IA ──
const recordingSpeakers = createRoute({
  getParentRoute: () => shellRoute,
  path: '/meetings/$meetingId/recordings/$recordingId/speakers',
  component: SpeakerMappingPage,
})
const recordingSummary = createRoute({
  getParentRoute: () => shellRoute,
  path: '/meetings/$meetingId/recordings/$recordingId/summary',
  component: RecordingSummaryPage,
})

const routeTree = rootRoute.addChildren([
  loginRoute,
  shellRoute.addChildren([
    dashboardRoute, meetingsList, meetingNew, meetingDetail,
    decisionsList, decisionDetail, plansList, planDetail,
    myTasks, liveCodir, taskDetail, notifs, notifPrefs, documents,
    profile, settingsMembers, settingsSubsidiaries, settingsMeetingSeries,
    recordingSpeakers, recordingSummary,
  ]),
])

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}

export default function App() {
  return <RouterProvider router={router} />
}
