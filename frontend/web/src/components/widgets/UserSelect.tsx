import { useQuery } from '@tanstack/react-query'

import { accountsApi, unwrapList, usersKeys } from '@/features/accounts/api'

/** Select des utilisateurs du tenant courant. */
export function UserSelect({
  value, onChange, placeholder = 'Sélectionner…', allowEmpty = true, className,
}: {
  value: string | null | undefined
  onChange: (id: string | null) => void
  placeholder?: string
  allowEmpty?: boolean
  className?: string
}) {
  const { data } = useQuery({
    queryKey: usersKeys.all,
    queryFn: () => accountsApi.listUsers(),
    staleTime: 60_000,
  })
  const users = unwrapList(data ?? [])
  return (
    <select
      className={`input ${className ?? ''}`}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || null)}
    >
      {allowEmpty && <option value="">{placeholder}</option>}
      {users.map((u) => (
        <option key={u.id} value={u.id}>
          {u.full_name || u.email}
        </option>
      ))}
    </select>
  )
}
