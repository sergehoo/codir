import { useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { fr } from 'date-fns/locale'
import { Eye, EyeOff, KeyRound, Lock, Mail, Save, Shield } from 'lucide-react'
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

  // ── Changement de mot de passe ──
  const [currentPwd, setCurrentPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [showPwd, setShowPwd] = useState(false)

  const changePassword = useMutation({
    mutationFn: async () => {
      const r = await apiClient.post('/auth/me/change-password/', {
        current_password: currentPwd,
        new_password: newPwd,
      })
      return r.data
    },
    onSuccess: () => {
      setCurrentPwd(''); setNewPwd(''); setConfirmPwd('')
      toast.success('Mot de passe changé avec succès')
    },
    onError: (e: any) => {
      const msg = e?.response?.data?.detail || e?.response?.data?.current_password?.[0] || e?.response?.data?.new_password?.[0]
      toast.error(msg || 'Échec du changement de mot de passe')
    },
  })

  const handleChangePassword = (e: React.FormEvent) => {
    e.preventDefault()
    if (newPwd.length < 8) {
      toast.error('Le nouveau mot de passe doit faire au moins 8 caractères')
      return
    }
    if (newPwd !== confirmPwd) {
      toast.error('Les deux mots de passe ne correspondent pas')
      return
    }
    if (newPwd === currentPwd) {
      toast.error('Le nouveau mot de passe doit être différent de l\'ancien')
      return
    }
    changePassword.mutate()
  }

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

        {/* ─── Changement de mot de passe ─── */}
        <form onSubmit={handleChangePassword} className="card p-6 space-y-5">
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold flex items-center gap-3">
            <span className="divider-accent" /> Sécurité — Mot de passe
          </div>

          <div className="space-y-4">
            <div>
              <label className="label">Mot de passe actuel</label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle" />
                <input
                  type={showPwd ? 'text' : 'password'}
                  className="input pl-9 pr-10"
                  value={currentPwd}
                  onChange={(e) => setCurrentPwd(e.target.value)}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-fg-subtle hover:text-fg"
                  tabIndex={-1}
                >
                  {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Nouveau mot de passe</label>
                <input
                  type={showPwd ? 'text' : 'password'}
                  className="input"
                  value={newPwd}
                  onChange={(e) => setNewPwd(e.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </div>
              <div>
                <label className="label">Confirmer</label>
                <input
                  type={showPwd ? 'text' : 'password'}
                  className="input"
                  value={confirmPwd}
                  onChange={(e) => setConfirmPwd(e.target.value)}
                  autoComplete="new-password"
                  required
                />
              </div>
            </div>

            <ul className="text-2xs text-fg-subtle space-y-0.5 list-disc list-inside">
              <li>Minimum 8 caractères</li>
              <li>Différent de votre mot de passe actuel</li>
              <li>Recommandé : mix lettres, chiffres et symboles</li>
            </ul>
          </div>

          <div className="flex justify-end pt-4 border-t border-border">
            <PremiumButton
              type="submit"
              variant="secondary"
              loading={changePassword.isPending}
              iconLeft={<KeyRound size={14} />}
            >
              Changer le mot de passe
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
