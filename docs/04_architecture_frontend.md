# 04 — Architecture frontend (Web React)

## 1. Stack et versions

| Composant | Version | Rôle |
|---|---|---|
| React | 18.3 | Framework UI |
| TypeScript | 5.5 | Typage statique |
| Vite | 5.x | Bundler / dev server |
| TailwindCSS | 3.4 | Utility-first CSS |
| Shadcn/UI | dernière | Composants Radix + Tailwind |
| Tanstack Query | 5.x | Cache serveur / data fetching |
| Tanstack Router | 1.x | Routing typé (alternative React Router) |
| Zustand | 4.x | State client global léger |
| ECharts | 5.x | Charts complexes (heatmaps, radar, sankey) |
| Recharts | 2.x | Charts simples (sparklines, KPI cards) |
| Framer Motion | 11.x | Animations |
| React Hook Form + Zod | dernière | Formulaires + validation |
| date-fns | 3.x | Dates / fuseaux horaires |
| i18next | 23.x | Internationalisation |
| Sentry React | dernière | Error tracking |
| Playwright | 1.x | E2E |
| Vitest | 1.x | Tests unitaires |
| MSW | 2.x | Mock API en tests |

## 2. Structure du projet

```
frontend/web/
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── .env.example
├── public/
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── routes/                       ← Tanstack Router file-based
    │   ├── __root.tsx
    │   ├── auth/
    │   │   ├── login.tsx
    │   │   └── mfa.tsx
    │   ├── dashboard/
    │   │   ├── index.tsx             ← dashboard DG
    │   │   ├── daf.tsx               ← DAF
    │   │   ├── drh.tsx
    │   │   └── dsi.tsx
    │   ├── meetings/
    │   │   ├── index.tsx
    │   │   ├── $id.tsx               ← détail
    │   │   └── $id.live.tsx          ← mode live
    │   ├── decisions/
    │   ├── action-plans/
    │   ├── budgets/
    │   ├── risks/
    │   ├── documents/
    │   ├── reports/
    │   └── settings/
    ├── features/                     ← logique métier groupée par domaine
    │   ├── auth/
    │   │   ├── api.ts
    │   │   ├── hooks.ts
    │   │   ├── store.ts
    │   │   └── components/
    │   ├── meetings/
    │   ├── decisions/
    │   ├── dashboards/
    │   ├── ai-copilot/
    │   ├── notifications/
    │   └── realtime/
    ├── components/                   ← composants UI réutilisables
    │   ├── ui/                       ← Shadcn (button, card, dialog…)
    │   ├── charts/                   ← wrappers ECharts/Recharts
    │   ├── layout/                   ← Shell, Sidebar, Topbar, Breadcrumb
    │   ├── widgets/                  ← KPICard, DecisionCard, MeetingCard
    │   └── forms/                    ← FieldWrapper, MultiSelect, DatePicker
    ├── lib/
    │   ├── api/                      ← client axios + intercepteurs JWT
    │   ├── query/                    ← Tanstack Query client + keys
    │   ├── ws/                       ← WebSocket manager
    │   ├── auth/                     ← token storage, refresh, MFA
    │   ├── permissions/              ← RBAC client (cache, helpers)
    │   ├── i18n/
    │   ├── analytics/                ← événements produit (PostHog, Amplitude)
    │   └── utils/
    ├── styles/
    │   ├── globals.css
    │   └── tokens.css                ← design tokens CSS vars
    └── types/                        ← types globaux + types générés OpenAPI
```

## 3. Conventions et architecture

CODIR web suit une architecture **routes + features + composants** qui sépare clairement :

- les **routes** (`/routes`) : URL, layouts, chargement de page, redirections d'auth
- les **features** (`/features`) : la logique métier (hooks, API clients, store local)
- les **composants** (`/components`) : la présentation pure, sans appel API direct

Une page de route assemble : layout (depuis `/components/layout`) + composants UI (depuis `/components/widgets`) + hooks métier (depuis `/features/<domaine>/hooks`). Cette séparation rend chaque feature testable isolément et facilite le code-splitting par route.

## 4. Routing

Tanstack Router file-based, typé. Chaque fichier sous `routes/` est une route. Les segments dynamiques sont préfixés `$` (ex. `$id.tsx`). Les routes protégées passent par `beforeLoad` qui vérifie l'authentification et redirige vers `/auth/login?next=`.

Exemple :

```tsx
// routes/meetings/$id.tsx
import { createFileRoute } from '@tanstack/react-router'
import { meetingsApi } from '@/features/meetings/api'
import { MeetingDetail } from '@/features/meetings/components/MeetingDetail'

export const Route = createFileRoute('/meetings/$id')({
  beforeLoad: ({ context }) => context.auth.assertAuthenticated(),
  loader: ({ params, context }) =>
    context.queryClient.ensureQueryData(meetingsApi.detailQuery(params.id)),
  component: () => {
    const { id } = Route.useParams()
    return <MeetingDetail meetingId={id} />
  },
})
```

## 5. Data layer — Tanstack Query

Tanstack Query est l'unique mécanisme de récupération et de cache des données serveur. Convention :

- **Query keys** centralisées par feature : `meetings.detail(id)`, `meetings.list(filters)`, hiérarchiques pour invalidation cascade.
- **API client** axios avec intercepteurs (JWT refresh automatique, propagation `X-Request-ID`, gestion d'erreur normalisée).
- **Stale time** par défaut 30 s, **refetchOnWindowFocus** pour les dashboards, **WebSocket invalidation** pour les données temps réel (la WS push `invalidate: ["decisions", id]` et Tanstack rafraîchit).
- **Optimistic updates** sur les actions critiques (vote, mise à jour de décision) avec rollback automatique en cas d'erreur.

```ts
// features/decisions/api.ts
export const decisionsKeys = {
  all: ['decisions'] as const,
  lists: () => [...decisionsKeys.all, 'list'] as const,
  list: (filters: DecisionFilters) => [...decisionsKeys.lists(), filters] as const,
  details: () => [...decisionsKeys.all, 'detail'] as const,
  detail: (id: string) => [...decisionsKeys.details(), id] as const,
}

export const decisionsApi = {
  list: (filters: DecisionFilters) => apiClient.get<Page<Decision>>('/api/v1/decisions/', { params: filters }),
  detail: (id: string) => apiClient.get<Decision>(`/api/v1/decisions/${id}/`),
  vote: (id: string, vote: VotePayload) =>
    apiClient.post<Decision>(`/api/v1/decisions/${id}/votes/`, vote, {
      headers: { 'Idempotency-Key': crypto.randomUUID() },
    }),
}

export function useDecisionVote(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vote: VotePayload) => decisionsApi.vote(id, vote),
    onMutate: async (vote) => {
      await qc.cancelQueries({ queryKey: decisionsKeys.detail(id) })
      const previous = qc.getQueryData<Decision>(decisionsKeys.detail(id))
      qc.setQueryData(decisionsKeys.detail(id), (old: Decision) => applyVoteOptimistic(old, vote))
      return { previous }
    },
    onError: (_err, _vote, ctx) => {
      if (ctx?.previous) qc.setQueryData(decisionsKeys.detail(id), ctx.previous)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: decisionsKeys.detail(id) }),
  })
}
```

## 6. State client — Zustand

Réservé à l'état UI purement client : ouverture de panels, sidebar collapse, thème, filtres en cours, breadcrumbs. Aucune donnée serveur ne transite par Zustand — Tanstack Query est seul propriétaire du cache serveur.

```ts
// lib/store/ui.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      theme: 'system',
      meetingPanelOpen: true,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setTheme: (theme) => set({ theme }),
    }),
    { name: 'codir-ui' },
  ),
)
```

## 7. Temps réel — WebSocket manager

Une classe `WSManager` (singleton) maintient une connexion par "scope" (`/ws/notifications/`, `/ws/meetings/<id>/`, `/ws/dashboards/<id>/`). Elle reconnecte automatiquement avec backoff exponentiel, déduplique les messages (id), expose un `subscribe(channel, handler)` et bridge vers Tanstack Query pour invalider les caches.

```ts
// lib/ws/manager.ts
class WSManager {
  private sockets = new Map<string, WebSocket>()
  connect(scope: string, onMessage: (msg: WSMessage) => void) {
    if (this.sockets.has(scope)) return
    const url = `${WSS_BASE}${scope}?token=${getAccessToken()}`
    const ws = new WebSocket(url)
    ws.onmessage = (e) => onMessage(JSON.parse(e.data))
    ws.onclose = () => this.reconnect(scope, onMessage)
    this.sockets.set(scope, ws)
  }
  // …
}

// features/meetings/hooks.ts
export function useLiveMeeting(meetingId: string) {
  const qc = useQueryClient()
  useEffect(() => {
    wsManager.connect(`/ws/meetings/${meetingId}/`, (msg) => {
      if (msg.type === 'decision.created') qc.invalidateQueries({ queryKey: decisionsKeys.detail(msg.payload.id) })
      if (msg.type === 'transcript.chunk') updateTranscript(msg.payload)
      if (msg.type === 'vote.update') qc.invalidateQueries({ queryKey: meetingsKeys.detail(meetingId) })
    })
    return () => wsManager.disconnect(`/ws/meetings/${meetingId}/`)
  }, [meetingId])
}
```

## 8. Design System

CODIR ne s'invente pas un design system : il bâtit sur **Shadcn/UI** (composants Radix + Tailwind), augmenté d'un set de **widgets exécutifs** propres (KPICard, DecisionCard, RiskHeatmap, MeetingTimeline, ExecutiveSparkline).

**Tokens de design** dans `styles/tokens.css` (CSS variables) :

```css
:root {
  /* Palette corporate */
  --color-primary: 220 90% 56%;        /* bleu exécutif */
  --color-primary-foreground: 0 0% 100%;
  --color-success: 142 76% 36%;
  --color-warning: 38 92% 50%;
  --color-danger: 0 84% 60%;
  --color-info: 200 95% 50%;

  /* Surfaces */
  --color-bg: 0 0% 100%;
  --color-bg-subtle: 220 20% 98%;
  --color-bg-elevated: 0 0% 100%;
  --color-border: 220 13% 91%;

  /* Texte */
  --color-fg: 222 47% 11%;
  --color-fg-muted: 215 16% 47%;

  /* Typographie */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* Rayons */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  /* Élévations */
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06);
  --shadow-md: 0 4px 6px -1px rgba(15, 23, 42, 0.10);
  --shadow-lg: 0 10px 15px -3px rgba(15, 23, 42, 0.10);
  --shadow-executive: 0 0 0 1px rgba(15, 23, 42, 0.04), 0 12px 24px -8px rgba(15, 23, 42, 0.20);
}

[data-theme='dark'] {
  --color-bg: 222 47% 7%;
  --color-bg-subtle: 222 47% 9%;
  --color-bg-elevated: 222 47% 11%;
  --color-border: 217 33% 17%;
  --color-fg: 210 40% 98%;
  --color-fg-muted: 215 20% 65%;
}
```

Trois niveaux d'élévation : *flat* (KPI cards de base), *raised* (cards interactives au hover), *executive* (dialogues, modaux, panneaux IA).

## 9. Animations — Framer Motion

Trois familles : **micro-interactions** (boutons, toggles : 120 ms ease-out), **transitions** (changement de route, ouverture de panel : 240 ms cubic-bezier), **storytelling** (réveler progressivement les KPI au chargement du dashboard, transition entre vue agrégée et drill-down). On évite les animations trop longues sur les vues exécutives — un DG perçoit > 300 ms comme une latence.

## 10. Accessibilité (a11y)

Conformité **WCAG 2.1 AA** minimum :

Contraste 4.5:1 sur le texte courant, 3:1 sur le texte large et les composants UI. Tous les composants interactifs accessibles au clavier (Shadcn/Radix gère 95 %). Focus visible toujours. Lecteurs d'écran : labels ARIA, `aria-live` pour les notifications temps réel, `role="status"` pour les chargements. Navigation par skip-link. Mode haut contraste accessible via le switcher de thème.

## 11. Internationalisation

`i18next` avec fichiers JSON par locale (`fr`, `en` en v1 ; `es`, `ar`, `pt` en v2). Détection automatique + override utilisateur persisté. Toutes les chaînes côté front sont externalisées. Les dates utilisent `date-fns` avec locale dynamique et fuseau horaire du tenant.

## 12. Performance — budget et stratégie

| Indicateur | Budget |
|---|---|
| First Contentful Paint | < 1,2 s |
| Largest Contentful Paint | < 2 s |
| Time to Interactive | < 2,5 s |
| Bundle initial JS gzippé | < 220 kB |
| Bundle par route lazy | < 80 kB |
| Lighthouse score | ≥ 92 |

Stratégies : code-splitting par route (lazy), import dynamique des charts lourds (ECharts ne charge que les modules utilisés), images en AVIF/WebP avec `<picture>`, polices Inter via `font-display: swap`, prefetch agressif des routes adjacentes via Tanstack Router.

## 13. Tests

**Unitaires** (Vitest + Testing Library) : composants, hooks, sélecteurs. Couverture > 75 %.
**Intégration** (Vitest + MSW) : pages complètes contre mocks API.
**E2E** (Playwright) : scénarios critiques (login + MFA, créer décision, voter, générer PV) sur 3 navigateurs.
**Visual regression** (Chromatic ou Percy) : snapshots des composants UI.

## 14. PWA et offline léger

Le web devient une PWA installable (manifest + service worker via Workbox). Mode dégradé offline : consultation du dashboard du jour, lecture des décisions et plans d'action mis en cache (limite 30 derniers documents), interdiction des écritures (qui se font côté Flutter en offline complet). Notifications push web via Push API (canal additionnel aux notifications mobile).

---

*Suite : [05 — Architecture mobile](05_architecture_mobile.md)*
