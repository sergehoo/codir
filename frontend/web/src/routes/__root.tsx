import { createRootRoute, Outlet, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { useAuthStore } from '@/stores/auth'

export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  const navigate = useNavigate()
  const access = useAuthStore((s) => s.accessToken)
  const path = typeof window !== 'undefined' ? window.location.pathname : ''
  const isOnLogin = path.startsWith('/login')

  useEffect(() => {
    if (!access && !isOnLogin) {
      navigate({ to: '/login' })
    }
  }, [access, isOnLogin, navigate])

  // Pendant la transition (useEffect asynchrone), on évite tout rendu des
  // pages protégées pour ne pas montrer un état fantôme (placeholders type
  // "Bonjour, …", widgets stale, etc.).
  if (!access && !isOnLogin) {
    return (
      <div className="min-h-screen grid place-items-center bg-bg-base text-fg-muted">
        <div className="text-center">
          <div className="text-2xs uppercase tracking-widest mb-2 text-copper-500">
            Session expirée
          </div>
          <div className="text-sm">Redirection vers la connexion…</div>
        </div>
      </div>
    )
  }

  return <Outlet />
}
