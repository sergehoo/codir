import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'
import { AlertTriangle, ArrowRight, Clock, Eye, EyeOff, Lock, Mail, ShieldOff, WifiOff } from 'lucide-react'

import { PremiumButton } from '@/components/widgets/PremiumButton'
import { KaydanLogo } from '@/components/widgets/KaydanLogo'
import { authApi } from './api'
import { useAuthStore } from '@/stores/auth'

/** Tonalité visuelle du bandeau d'erreur selon le type. */
type ErrorTone = 'danger' | 'warning' | 'info'

interface LoginError {
  title: string
  message: string
  tone: ErrorTone
  icon: typeof AlertTriangle
}

/** Parse l'erreur axios et retourne un message utilisateur précis. */
function parseLoginError(err: any): LoginError {
  const status = err?.response?.status
  const data = err?.response?.data
  const code = data?.code
  const detail = (typeof data?.detail === 'string' ? data.detail : null)
    || (typeof data === 'string' ? data : null)

  // ── Codes applicatifs explicites du backend ─────────────────
  if (code === 'account_locked') {
    const wait = data?.wait_minutes ?? 15
    return {
      title: 'Compte verrouillé',
      message: detail || `Trop de tentatives. Réessayez dans ~${wait} min ou contactez votre administrateur pour débloquer immédiatement.`,
      tone: 'danger',
      icon: Lock,
    }
  }
  if (code === 'account_disabled') {
    return {
      title: 'Compte désactivé',
      message: detail || 'Votre compte a été désactivé. Contactez votre administrateur CODIR pour le réactiver.',
      tone: 'warning',
      icon: ShieldOff,
    }
  }
  if (code === 'invalid_credentials') {
    return {
      title: 'Identifiants incorrects',
      message: 'Email ou mot de passe incorrect. Vérifiez la saisie ou cliquez sur « Oublié ? » pour réinitialiser.',
      tone: 'danger',
      icon: AlertTriangle,
    }
  }
  if (code === 'missing_fields') {
    return {
      title: 'Champs requis',
      message: detail || 'Saisissez votre email et votre mot de passe.',
      tone: 'warning',
      icon: AlertTriangle,
    }
  }

  // ── Codes HTTP standards ─────────────────────────────────────
  if (status === 401) {
    return {
      title: 'Identifiants incorrects',
      message: detail || 'Email ou mot de passe incorrect.',
      tone: 'danger',
      icon: AlertTriangle,
    }
  }
  if (status === 403) {
    return {
      title: 'Accès refusé',
      message: detail || 'Votre accès a été restreint. Contactez votre administrateur.',
      tone: 'warning',
      icon: ShieldOff,
    }
  }
  if (status === 423) {
    return {
      title: 'Compte verrouillé',
      message: detail || 'Trop de tentatives. Réessayez plus tard.',
      tone: 'danger',
      icon: Lock,
    }
  }
  if (status === 429) {
    return {
      title: 'Trop de requêtes',
      message: 'Vous avez essayé de vous connecter trop souvent. Patientez quelques minutes.',
      tone: 'warning',
      icon: Clock,
    }
  }
  if (status === 502 || status === 503 || status === 504) {
    return {
      title: 'Service indisponible',
      message: 'Le serveur CODIR ne répond pas. Réessayez dans quelques instants.',
      tone: 'warning',
      icon: WifiOff,
    }
  }
  // ── Erreur réseau (sans réponse HTTP) ────────────────────────
  if (!err?.response) {
    return {
      title: 'Connexion impossible',
      message: 'Aucune réponse du serveur. Vérifiez votre connexion internet.',
      tone: 'warning',
      icon: WifiOff,
    }
  }
  // ── Fallback générique avec le detail backend si dispo ──────
  return {
    title: 'Erreur de connexion',
    message: detail || `Erreur inattendue (HTTP ${status ?? '?'}). Réessayez ou contactez le support.`,
    tone: 'danger',
    icon: AlertTriangle,
  }
}

export function LoginPage() {
  const navigate = useNavigate()
  const setTokens = useAuthStore((s) => s.setTokens)
  const setUser = useAuthStore((s) => s.setUser)
  const [email, setEmail] = useState('')
  const [pwd, setPwd] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [expiredNotice, setExpiredNotice] = useState(false)
  const [loginError, setLoginError] = useState<LoginError | null>(null)

  // Affiche un bandeau si on a été redirigé suite à une session expirée
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search)
    if (sp.get('reason') === 'expired') {
      setExpiredNotice(true)
      // Nettoie l'URL pour ne pas réafficher au reload
      const cleanUrl = window.location.pathname
      window.history.replaceState({}, '', cleanUrl)
    }
  }, [])

  // ─── État MFA (étape 2) ───
  const [mfaRequired, setMfaRequired] = useState(false)
  const [challengeToken, setChallengeToken] = useState('')
  const [mfaCode, setMfaCode] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setLoginError(null)
    try {
      const r: any = await authApi.login(email, pwd)
      // Si le backend demande un code MFA
      if (r.mfa_required && r.challenge_token) {
        setChallengeToken(r.challenge_token)
        setMfaRequired(true)
        setLoading(false)
        return
      }
      // Flow normal (pas de MFA)
      setTokens(r.access, r.refresh)
      const me = await authApi.me()
      setUser(me)
      navigate({ to: '/' })
    } catch (err: any) {
      const parsed = parseLoginError(err)
      setLoginError(parsed)
      // Toast en backup pour les users qui ne voient pas le bandeau (mobile etc.)
      toast.error(parsed.title, {
        description: parsed.message.slice(0, 200),
        duration: 8000,
      })
    } finally { setLoading(false) }
  }

  async function submitMfa(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setLoginError(null)
    try {
      const r: any = await authApi.verifyMfa(challengeToken, mfaCode)
      setTokens(r.access, r.refresh)
      const me = await authApi.me()
      setUser(me)
      navigate({ to: '/' })
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      const msg = detail || 'Code à 6 chiffres invalide. Vérifiez l\'heure de votre téléphone (synchro NTP).'
      setLoginError({
        title: 'Code MFA invalide',
        message: msg,
        tone: 'danger',
        icon: AlertTriangle,
      })
      toast.error('Code MFA invalide', { description: msg.slice(0, 200) })
      setMfaCode('')
    } finally { setLoading(false) }
  }

  function cancelMfa() {
    setMfaRequired(false)
    setChallengeToken('')
    setMfaCode('')
    setPwd('')
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
            <div className="serif text-h2 font-semibold leading-none">CODIR</div>
            <div className="text-2xs uppercase tracking-widest text-fg-subtle mt-1">Executive Platform</div>
          </div>
        </div>

        <div className="space-y-10 animate-fade-in-up">


          <h1 className="serif text-hero leading-[1.02] text-fg">
            Where leaders<br />
            decide <span className="italic text-copper-400">with clarity.</span>
          </h1>

          <p className="text-fg-muted text-lg leading-relaxed max-w-md font-light">
            Cette Platerfome orchestre vos comités de direction, archive chaque décision,
            et pilote l'exécution des tâches.
          </p>


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
              <span className="divider-accent" />Se connecter
            </div>
            <h2 className="serif text-editorial leading-tight">
              Bon retour <span className="italic">!</span>
            </h2>
            <p className="text-fg-muted text-base mt-3">
              Connectez-vous à votre cockpit exécutif.
            </p>
          </div>

          {expiredNotice && !loginError && (
            <div className="flex items-start gap-3 rounded-md border border-copper-500/30 bg-copper-500/5 px-4 py-3 text-sm">
              <Clock size={16} className="text-copper-500 mt-0.5 shrink-0" />
              <div>
                <div className="font-semibold text-copper-500">Session expirée</div>
                <div className="text-fg-muted text-xs mt-0.5">
                  Pour des raisons de sécurité, votre session a été fermée.
                  Reconnectez-vous pour continuer.
                </div>
              </div>
            </div>
          )}

          {/* ─── Bandeau erreur login précis ──────────────────── */}
          {loginError && (() => {
            const Icon = loginError.icon
            const colors = loginError.tone === 'danger'
              ? 'border-red-500/30 bg-red-500/5 text-red-300'
              : loginError.tone === 'warning'
                ? 'border-amber-500/30 bg-amber-500/5 text-amber-200'
                : 'border-blue-500/30 bg-blue-500/5 text-blue-200'
            const iconColor = loginError.tone === 'danger'
              ? 'text-red-400'
              : loginError.tone === 'warning'
                ? 'text-amber-400'
                : 'text-blue-400'
            return (
              <div
                role="alert"
                aria-live="assertive"
                className={`flex items-start gap-3 rounded-md border px-4 py-3 mb-4 text-sm ${colors}`}
              >
                <Icon size={16} className={`${iconColor} mt-0.5 shrink-0`} />
                <div className="flex-1 min-w-0">
                  <div className="font-semibold">{loginError.title}</div>
                  <div className="text-xs mt-0.5 opacity-90 leading-relaxed">
                    {loginError.message}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setLoginError(null)}
                  className="text-2xs uppercase tracking-wider opacity-60 hover:opacity-100 shrink-0"
                  aria-label="Fermer l'alerte"
                >
                  ✕
                </button>
              </div>
            )
          })()}

          {mfaRequired ? (
            /* ─── Étape 2 : Saisie code MFA ─── */
            <form onSubmit={submitMfa} className="space-y-6">
              <div className="rounded-lg border border-copper-500/30 bg-copper-500/5 p-4">
                <div className="flex items-start gap-3">
                  <Lock size={16} className="text-copper-500 mt-0.5" />
                  <div>
                    <div className="font-semibold text-sm">Vérification en 2 étapes</div>
                    <div className="text-fg-muted text-xs mt-1">
                      Ouvrez votre application d'authentification (Google Authenticator,
                      Authy, 1Password…) et entrez le code à 6 chiffres pour
                      <span className="font-medium text-fg"> {email}</span>.
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <label className="label">Code à 6 chiffres</label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="\d{6}"
                  maxLength={6}
                  autoComplete="one-time-code"
                  autoFocus
                  className="input text-center text-2xl font-mono tracking-[0.5em]"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="••••••"
                />
              </div>

              <PremiumButton
                type="submit" size="lg" loading={loading} className="w-full"
                iconRight={<ArrowRight size={16} />}
                disabled={mfaCode.length !== 6}
              >
                {loading ? 'Vérification…' : 'Valider le code'}
              </PremiumButton>

              <button
                type="button"
                onClick={cancelMfa}
                className="block mx-auto text-2xs text-fg-muted hover:text-copper-400 uppercase tracking-wider font-semibold"
              >
                ← Recommencer la connexion
              </button>
            </form>
          ) : (
            /* ─── Étape 1 : Email + Password ─── */
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
          )}


        </div>
      </div>
    </div>
  )
}
