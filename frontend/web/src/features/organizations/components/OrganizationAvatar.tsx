/**
 * OrganizationAvatar — affiche le logo d'une organisation OU une initiale
 * dans un cercle coloré (utilise primary_color de l'org).
 */
import type { OrgMembership } from '@/stores/auth'

interface Props {
  membership: OrgMembership
  size?: number  // px
  className?: string
}

export function OrganizationAvatar({ membership, size = 32, className = '' }: Props) {
  const initial = (membership.organization_name || '?').trim().charAt(0).toUpperCase()
  const bg = membership.primary_color || '#2563eb'

  if (membership.logo) {
    return (
      <img
        src={membership.logo}
        alt={membership.organization_name}
        width={size}
        height={size}
        className={`rounded object-cover shrink-0 ${className}`}
        onError={(e) => {
          // Fallback initial si le logo ne charge pas
          ;(e.currentTarget as HTMLImageElement).style.display = 'none'
        }}
      />
    )
  }

  return (
    <div
      className={`rounded grid place-items-center shrink-0 text-white font-semibold ${className}`}
      style={{
        width: size,
        height: size,
        backgroundColor: bg,
        fontSize: `${Math.max(10, size * 0.45)}px`,
      }}
      title={membership.organization_name}
    >
      {initial}
    </div>
  )
}
