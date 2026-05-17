/**
 * LiveCodirPage — wrapper standalone du LiveCodirMode pour la route /live-codir.
 *
 * Quand l'utilisateur arrive ici directement (via clic sur un KPI ou bookmark),
 * on affiche le Live CODIR Mode en pleine page. Bouton X / Esc → retour au
 * dashboard.
 */
import { useNavigate } from '@tanstack/react-router'

import { LiveCodirMode } from './LiveCodirMode'

export function LiveCodirPage() {
  const navigate = useNavigate()
  return <LiveCodirMode onClose={() => navigate({ to: '/' })} />
}
