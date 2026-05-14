import { useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { Mail, Save, Shield } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { apiClient } from '@/api/client'
import { PremiumButton } from '@/components/widgets/PremiumButton'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { useAuthStore } from '@/stores/auth'

export function ProfilePage() {
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const qc = useQueryClient()

  const [firstName, setFirstName] = useState(user?.first_name || '')
  const [lastName, setLastName] = useState(user?.last_name || '')
  const [phone, setPhone] = useState((user as any)?.phone_e164 || '')
  const [locale, setLocale] = useState((user as any)?.locale || 'fr-FR')
  const [timezone, setTimezone] = useState((user as any)?.timezone || 'Europe/Paris')

  const save = useMutation({
    mutationFn: async () => {
      const r = await apiClient.patch('/auth/me/', {
        first_name: firstName,
        last_name: lastName,
        phone_e164: phone,
        locale,
        timezone,
      })
      return r.data
    },
    onSuccess: (data) => {
      setUser(data as any)
      qc.invalidateQueries({ queryKey: ['users'] })
      toast.success('Profil mis à jour')
    },
    onError: () => toast.error('Échec de la sauvegarde'),
  })

  if (!user) return <div className="p-10 text-fg-subtle">Chargement…</div>

  const initials = `${(user.first_name?.[0] || user.email[0] || '').toUpperCase()}${(user.last_name?.[0] || '').toUpperCase()}`

  return (
    <div className="min-h-full bg-bg-base">
      <SectionHeader
        eyebrow="Compte"
        title="Mon profil"
        description="Préférences personnelles et informations de contact."
      />

      <section className="px-10 py-10 max-w-3xl space-y-8">

        {/* Identité */}
        <div className="card p-6 flex items-center gap-5">
          <div className="w-16 h-16 rounded-full bg-copper-gradient grid place-items-center text-white serif text-h1 font-medium shadow-copper">
            {initials}
          </div>
          <div className="flex-1">
            <div className="serif text-h2 font-medium">{user.full_name || user.email}</div>
            <div className="text-fg-muted text-sm mt-1 inline-flex items-center gap-2">
              <Mail size={13} /> {user.email}
            </div>
            <div className="flex gap-2 mt-3">
              {user.is_executive && (
                <span className="chip-copper">
                  <Shield size={11} /> Executive
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Form édition */}
        <form
          onSubmit={(e) => { e.preventDefault(); save.mutate() }}
          className="card p-6 space-y-5"
        >
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold flex items-center gap-3">
            <span className="divider-accent" /> Informations
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Prénom</label>
              <input className="input" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
            </div>
            <div>
              <label className="label">Nom</label>
              <input className="input" value={lastName} onChange={(e) => setLastName(e.target.value)} />
            </div>
          </div>

          <div>
            <label className="label">Email</label>
            <input className="input opacity-60" value={user.email} readOnly />
            <p className="text-2xs text-fg-subtle mt-1">L'email ne peut pas être modifié.</p>
          </div>

          <div>
            <label className="label">Téléphone (format E.164)</label>
            <input className="input" value={phone} onChange={(e) => setPhone(e.target.value)}
                   placeholder="+33 6 12 34 56 78" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Langue</label>
              <select className="input" value={locale} onChange={(e) => setLocale(e.target.value)}>
                <option value="fr-FR">Français</option>
                <option value="en-US">English (US)</option>
                <option value="en-GB">English (UK)</option>
              </select>
            </div>
            <div>
              <label className="label">Fuseau horaire</label>
              <select className="input" value={timezone} onChange={(e) => setTimezone(e.target.value)}>
                <option value="Europe/Paris">Europe/Paris</option>
                <option value="Europe/London">Europe/London</option>
                <option value="America/New_York">America/New_York</option>
                <option value="Africa/Abidjan">Africa/Abidjan</option>
                <option value="Africa/Casablanca">Africa/Casablanca</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end pt-4 border-t border-border">
            <PremiumButton type="submit" loading={save.isPending} iconLeft={<Save size={14} />}>
              Enregistrer
            </PremiumButton>
          </div>
        </form>

        {/* Métadonnées */}
        <div className="card p-6 space-y-3">
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold flex items-center gap-3">
            <span className="divider-accent" /> Activité
          </div>
          <div className="grid grid-cols-2 gap-6 text-sm">
            <div>
              <div className="text-2xs uppercase tracking-wider text-fg-subtle font-semibold">Inscrit le</div>
              <div className="mt-1">
                {(user as any).date_joined
                  ? format(new Date((user as any).date_joined), "d MMM yyyy", { locale: fr })
                  : '—'}
              </div>
            </div>
            <div>
              <div className="text-2xs uppercase tracking-wider text-fg-subtle font-semibold">Dernière connexion</div>
              <div className="mt-1">
                {(user as any).last_login
                  ? format(new Date((user as any).last_login), "d MMM yyyy 'à' HH:mm", { locale: fr })
                  : '—'}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
