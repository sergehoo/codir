import { createRootRoute, Outlet, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { useAuthStore } from '@/stores/auth'

export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  const navigate = useNavigate()
  const access = useAuthStore((s) => s.accessToken)
  useEffect(() => {
    const path = window.location.pathname
    if (!access && !path.startsWith('/login')) navigate({ to: '/login' })
  }, [access, navigate])
  return <Outlet />
}
