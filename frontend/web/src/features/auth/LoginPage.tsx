import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'
import { ArrowRight, Eye, EyeOff, Lock, Mail } from 'lucide-react'

import { PremiumButton } from '@/components/widgets/PremiumButton'
import { KaydanLogo } from '@/components/widgets/KaydanLogo'
import { authApi } from './api'
import { useAuthStore } from '@/stores/auth'

export function LoginPage() {
  const navigate = useNavigate()
  const setTokens = useAuthStore((s) => s.setTokens)
  const setUser = useAuthStore((s) => s.setUser)
  const [email, setEmail] = useState('')
  const [pwd, setPwd] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const r = await authApi.login(email, pwd)
      setTokens(r.access, r.refresh)
      const me = await authApi.me()
      setUser(me)
      navigate({ to: '/' })
    } catch {
      toast.error('Identifiants invalides')
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-bg-base text-fg">

      {/* ─── Panneau gauche — storytelling éditorial ─── */}
      <div className="hidden lg:flex relative flex-col p-14 justify-between bg-bg-subtle border-r border-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-copper-gradient grid place-items-center text-white serif font-medium shadow-copper">
            C
          </div>
          <div>
            <div className="serif text-h2 font-semibold leading-none">Codir</div>
            <div className="text-2xs uppercase tracking-widest text-fg-subtle mt-1">Executive Platform</div>
          </div>
        </div>

        <div className="space-y-10 animate-fade-in-up">
          <div className="flex items-center gap-3 text-2xs uppercase tracking-widest text-fg-muted font-semibold">
            <span className="divider-accent" />
            <span>Tuesday · 13 May 2026</span>
          </div>

          <h1 className="serif text-hero leading-[1.02] text-fg">
            Where boards<br />
            decide <span className="italic text-copper-400">with clarity.</span>
          </h1>

          <p className="text-fg-muted text-lg leading-relaxed max-w-md font-light">
            CODIR orchestre vos comités de direction, archive chaque décision,
            et pilote l'exécution stratégique. Une plateforme conçue pour les
            organisations qui prennent leur gouvernance au sérieux.
          </p>

          <div className="grid grid-cols-3 gap-8 pt-6 border-t border-border">
            {[
              { kpi: '87%',  label: 'Décisions exécutées dans les délais' },
              { kpi: '−60%', label: 'Temps de préparation comité' },
              { kpi: '< 90s',label: 'Compte rendu généré' },
            ].map((s) => (
              <div key={s.label}>
                <div className="serif text-kpi-sm text-copper-400">{s.kpi}</div>
                <div className="text-2xs uppercase tracking-wider text-fg-subtle mt-2 leading-relaxed">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="text-2xs text-fg-subtle tracking-widest uppercase">
            Édité par
          </div>
          <KaydanLogo variant="full" className="h-16 w-auto text-fg" />
          <div className="text-2xs text-fg-subtle tracking-wider uppercase">
            © 2026 Codir Executive Platform · v1.0 Beta
          </div>
        </div>
      </div>

      {/* ─── Panneau droit — formulaire login ─── */}
      <div className="relative grid place-items-center p-8 lg:p-14">
        <div className="w-full max-w-md animate-rise">
          <div className="mb-10">
            <div className="text-2xs uppercase tracking-widest text-copper-400 font-semibold mb-3 flex items-center gap-2">
              <span className="divider-accent" /> Sign in
            </div>
            <h2 className="serif text-editorial leading-tight">
              Bon retour à <span className="italic">l'atelier.</span>
            </h2>
            <p className="text-fg-muted text-base mt-3">
              Connectez-vous à votre cockpit exécutif.
            </p>
          </div>

          <form onSubmit={submit} className="space-y-6">
            <div>
              <label className="label">Email professionnel</label>
              <div className="relative">
                <Mail size={15} strokeWidth={1.75} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-fg-subtle" />
                <input
                  type="email" required autoFocus
                  className="input pl-11"
                  value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="dg@acme.local"
                />
              </div>
            </div>
            <div>
              <div className="flex items-baseline justify-between mb-1.5">
                <label className="label !mb-0">Mot de passe</label>
                <a className="text-2xs text-copper-400 hover:underline cursor-pointer">Oublié&nbsp;?</a>
              </div>
              <div className="relative">
                <Lock size={15} strokeWidth={1.75} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-fg-subtle" />
                <input
                  type={showPwd ? 'text' : 'password'} required
                  className="input pl-11 pr-11"
                  value={pwd} onChange={(e) => setPwd(e.target.value)}
                  placeholder="••••••••••••"
                />
                <button
                  type="button" onClick={() => setShowPwd((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-fg-subtle hover:text-fg"
                >
                  {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <PremiumButton
              type="submit" size="lg" loading={loading} className="w-full mt-2"
              iconRight={<ArrowRight size={16} />}
            >
              {loading ? 'Connexion…' : 'Accéder au cockpit'}
            </PremiumButton>

            <div className="relative my-2">
              <div className="absolute inset-0 flex items-center"><div className="w-full divider" /></div>
              <div className="relative flex justify-center">
                <span className="px-4 bg-bg-base text-2xs uppercase tracking-widest text-fg-subtle">ou</span>
              </div>
            </div>

            <button type="button"
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-lg border border-border bg-bg-elevated hover:border-copper-500/30 text-sm font-medium transition">
              <span className="font-bold">M</span> SSO Microsoft Entra ID
            </button>
          </form>

          <div className="mt-10 pt-6 border-t border-border text-2xs text-fg-subtle uppercase tracking-wider">
            Identifiants démo : <span className="font-mono text-copper-400">dg@acme.local</span> /{' '}
            <span className="font-mono">Codir!2026</span>
          </div>
        </div>
      </div>
    </div>
  )
}
