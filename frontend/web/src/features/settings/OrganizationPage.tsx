/**
 * OrganizationPage — administration du branding de l'organisation courante.
 *
 * Réservé aux administrateurs (owner / executive / superuser).
 * Permet de modifier nom + URL logo + couleur primaire + couleur secondaire,
 * avec preview live (header dynamique) qui simule le rendu sur l'app, les
 * emails et les exports PDF/DOCX.
 *
 * Le backend renvoie 403 si le user n'est pas admin → on affiche un état
 * "lecture seule" plutôt qu'une page vide.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Palette, Save, Upload } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { PremiumButton } from '@/components/widgets/PremiumButton'
import { SectionHeader } from '@/components/widgets/SectionHeader'
import { useAuthStore, useCurrentMembership } from '@/stores/auth'

import {
  organizationsApi,
  organizationsKeys,
  type UpdateOrgPayload,
} from '../organizations/api'

const HEX_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

// Suggestions de palettes premium — un clic pour appliquer.
const PALETTE_PRESETS: { name: string; primary: string; secondary: string }[] = [
  { name: 'Kaydan',   primary: '#B8693C', secondary: '#0e0a07' },
  { name: 'Atelier',  primary: '#1F2937', secondary: '#D97706' },
  { name: 'Émeraude', primary: '#10B981', secondary: '#064E3B' },
  { name: 'Saphir',   primary: '#2563EB', secondary: '#1E3A8A' },
  { name: 'Rubis',    primary: '#DC2626', secondary: '#7F1D1D' },
  { name: 'Améthyste',primary: '#7C3AED', secondary: '#4C1D95' },
]

export function OrganizationPage() {
  const qc = useQueryClient()
  const membership = useCurrentMembership()
  // is_owner / is_executive ne sont pas dans le store memberships par défaut,
  // on dérive admin = role_label inclut "Admin" OU on fait un fallback côté UX.
  // Si pas admin, l'API renverra 403 et on bascule en mode "read only".
  const setMemberships = useAuthStore((s) => s.setMemberships)

  const { data: org, isLoading } = useQuery({
    queryKey: organizationsKeys.current(),
    queryFn: organizationsApi.getCurrent,
  })

  // ── Form state (controlled) ──
  const [name, setName] = useState('')
  const [logo, setLogo] = useState('')
  const [primary, setPrimary] = useState('#B8693C')
  const [secondary, setSecondary] = useState('#0e0a07')
  const [readOnly, setReadOnly] = useState(false)
  const [savedFlash, setSavedFlash] = useState(false)

  // Sync depuis API
  useEffect(() => {
    if (!org) return
    setName(org.name || '')
    setLogo(org.logo || '')
    setPrimary(org.primary_color || '#B8693C')
    setSecondary(org.secondary_color || '#0e0a07')
  }, [org])

  const update = useMutation({
    mutationFn: (payload: UpdateOrgPayload) => organizationsApi.updateCurrent(payload),
    onSuccess: (data) => {
      qc.setQueryData(organizationsKeys.current(), data)
      // Rafraîchit les memberships pour mettre à jour le logo/couleur partout
      organizationsApi.myMemberships().then(setMemberships).catch(() => {})
      // Petit flash visuel de confirmation (3s)
      setSavedFlash(true)
      window.setTimeout(() => setSavedFlash(false), 2400)
    },
    onError: (err: any) => {
      // 403 → on bascule en mode lecture seule (user pas admin)
      if (err?.response?.status === 403) {
        setReadOnly(true)
      }
    },
  })

  // ── Validation ──
  const nameOK = name.trim().length >= 2
  const primaryOK = HEX_RE.test(primary)
  const secondaryOK = HEX_RE.test(secondary)
  const logoOK = !logo || /^https?:\/\//.test(logo)
  const formOK = nameOK && primaryOK && secondaryOK && logoOK
  const isDirty = useMemo(() => {
    if (!org) return false
    return (
      name !== (org.name || '')
      || logo !== (org.logo || '')
      || primary !== (org.primary_color || '#B8693C')
      || secondary !== (org.secondary_color || '#0e0a07')
    )
  }, [org, name, logo, primary, secondary])

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formOK || !isDirty || readOnly) return
    update.mutate({
      name: name.trim(),
      logo: logo.trim(),
      primary_color: primary.trim(),
      secondary_color: secondary.trim(),
    })
  }

  // ── Loading / placeholders ──
  if (isLoading) {
    return (
      <div className="space-y-6">
        <SectionHeader
          eyebrow="Paramètres"
          title="Organisation"
          description="Branding et identité de l'organisation."
        />
        <div className="card p-8 animate-pulse">
          <div className="h-4 bg-fg/[0.06] rounded w-1/3 mb-4" />
          <div className="h-10 bg-fg/[0.06] rounded mb-3" />
          <div className="h-10 bg-fg/[0.06] rounded mb-3" />
          <div className="h-10 bg-fg/[0.06] rounded" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Paramètres"
        title="Organisation"
        description="Identité et branding — apparaît partout : application, emails, exports PDF/DOCX."
      />

      {readOnly && (
        <div className="card p-4 border-l-2 border-warning bg-warning/5 text-sm text-warning">
          Vous n'êtes pas administrateur de cette organisation — modification désactivée.
          Contactez un Owner ou un Executive pour mettre à jour le branding.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ── Formulaire ── */}
        <form onSubmit={onSubmit} className="lg:col-span-3 space-y-5">
          <div className="card p-6 space-y-5">
            <div className="flex items-center gap-2 mb-2">
              <Building2 size={16} className="text-fg-muted" />
              <h3 className="text-sm font-semibold text-fg">Identité</h3>
            </div>

            <div>
              <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
                Nom de l'organisation
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={readOnly || update.isPending}
                className="w-full px-3 py-2 bg-bg border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-copper-500/40 disabled:opacity-60"
                placeholder="Datarium"
              />
              {!nameOK && name && (
                <p className="text-xs text-danger mt-1">Minimum 2 caractères.</p>
              )}
            </div>

            <div>
              <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
                URL du logo
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={logo}
                  onChange={(e) => setLogo(e.target.value)}
                  disabled={readOnly || update.isPending}
                  className="flex-1 px-3 py-2 bg-bg border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-copper-500/40 disabled:opacity-60"
                  placeholder="https://cdn.exemple.com/logo.png"
                />
                <a
                  href="#"
                  onClick={(e) => { e.preventDefault(); setLogo('') }}
                  className="text-xs text-fg-muted hover:text-copper-400 self-center px-2"
                  title="Effacer"
                >
                  Effacer
                </a>
              </div>
              {!logoOK && (
                <p className="text-xs text-danger mt-1">L'URL doit commencer par http:// ou https://.</p>
              )}
              <p className="text-2xs text-fg-subtle mt-1.5">
                Astuce : hébergez votre logo sur un CDN (Cloudinary, Imgix...) ou utilisez une URL publique.
                Format recommandé : PNG ou SVG, fond transparent, max 256px de hauteur.
              </p>
            </div>
          </div>

          <div className="card p-6 space-y-5">
            <div className="flex items-center gap-2 mb-2">
              <Palette size={16} className="text-fg-muted" />
              <h3 className="text-sm font-semibold text-fg">Palette de couleurs</h3>
            </div>

            <ColorField
              label="Couleur primaire"
              hint="Accent principal — utilisée pour les liens, titres et bordures d'emails."
              value={primary}
              onChange={setPrimary}
              disabled={readOnly || update.isPending}
              valid={primaryOK}
            />
            <ColorField
              label="Couleur secondaire"
              hint="Accent secondaire — utilisée pour les arrière-plans foncés (headers emails)."
              value={secondary}
              onChange={setSecondary}
              disabled={readOnly || update.isPending}
              valid={secondaryOK}
            />

            <div>
              <div className="text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-2">
                Palettes prédéfinies
              </div>
              <div className="flex flex-wrap gap-2">
                {PALETTE_PRESETS.map((p) => (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => { setPrimary(p.primary); setSecondary(p.secondary) }}
                    disabled={readOnly || update.isPending}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded border border-border hover:border-copper-400/60 hover:bg-fg/[0.03] transition disabled:opacity-60"
                  >
                    <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: p.primary }} />
                    <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: p.secondary }} />
                    <span className="text-xs text-fg-muted">{p.name}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {update.isError && !readOnly && (
            <div className="card p-3 border-l-2 border-danger bg-danger/5 text-xs text-danger">
              Échec de l'enregistrement : {(update.error as any)?.response?.data?.detail || 'erreur réseau'}.
            </div>
          )}

          <div className="flex items-center gap-3">
            <PremiumButton
              type="submit"
              disabled={!formOK || !isDirty || update.isPending || readOnly}
              iconLeft={<Save size={14} />}
            >
              {update.isPending ? 'Enregistrement…' : 'Enregistrer le branding'}
            </PremiumButton>
            {savedFlash && (
              <span className="text-xs text-success font-medium">✓ Branding mis à jour</span>
            )}
            {isDirty && !update.isPending && !savedFlash && (
              <span className="text-2xs uppercase tracking-wider text-fg-muted">
                Modifications non enregistrées
              </span>
            )}
          </div>
        </form>

        {/* ── Preview live ── */}
        <div className="lg:col-span-2 space-y-4">
          <div className="text-2xs uppercase tracking-widest text-fg-muted font-semibold">
            Aperçu en direct
          </div>

          {/* Preview email header */}
          <div className="rounded-lg overflow-hidden border border-border">
            <div className="text-2xs uppercase tracking-wider text-fg-subtle px-3 py-1.5 bg-fg/[0.03]">
              Email — entête
            </div>
            <div
              className="p-5"
              style={{ background: secondary, borderBottom: `3px solid ${primary}` }}
            >
              {logo ? (
                <div className="flex items-center gap-3">
                  <img
                    src={logo}
                    alt={name}
                    className="h-9 max-w-[120px] object-contain bg-white/95 rounded px-2 py-1"
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                  />
                  <div>
                    <div className="text-white font-serif text-base leading-tight">
                      {name || 'CODIR'}
                    </div>
                    <div className="text-white/60 text-[10px] uppercase tracking-[0.2em] mt-0.5">
                      Executive Platform
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <div className="text-white font-serif text-xl tracking-wide">
                    {name || 'CODIR'} <span style={{ color: primary }}>|</span> CODIR
                  </div>
                  <div className="text-white/60 text-[10px] uppercase tracking-[0.2em] mt-1">
                    Executive Platform
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Preview switcher topbar */}
          <div className="rounded-lg overflow-hidden border border-border">
            <div className="text-2xs uppercase tracking-wider text-fg-subtle px-3 py-1.5 bg-fg/[0.03]">
              Application — barre supérieure
            </div>
            <div className="p-4 bg-bg-elevated flex items-center gap-3">
              {logo ? (
                <img
                  src={logo}
                  alt={name}
                  className="w-7 h-7 rounded object-cover"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                />
              ) : (
                <div
                  className="w-7 h-7 rounded grid place-items-center text-white font-semibold text-sm"
                  style={{ backgroundColor: primary }}
                >
                  {(name || 'C').trim().charAt(0).toUpperCase()}
                </div>
              )}
              <div className="text-sm font-medium text-fg">{name || 'Mon organisation'}</div>
              <div className="ml-auto text-2xs uppercase tracking-wider text-fg-muted">
                {membership?.role_label || '—'}
              </div>
            </div>
          </div>

          {/* Preview PDF export */}
          <div className="rounded-lg overflow-hidden border border-border">
            <div className="text-2xs uppercase tracking-wider text-fg-subtle px-3 py-1.5 bg-fg/[0.03]">
              Export PDF — entête du CR
            </div>
            <div className="p-4 bg-white text-center" style={{ borderBottom: `2px solid ${primary}` }}>
              {logo && (
                <img
                  src={logo}
                  alt={name}
                  className="mx-auto max-h-10 max-w-[140px] object-contain mb-2"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                />
              )}
              <div
                className="text-[10px] uppercase tracking-[0.3em] font-semibold mb-1"
                style={{ color: primary }}
              >
                {name || 'CODIR'} — CODIR Executive
              </div>
              <div className="text-base font-serif text-neutral-900">Compte rendu CODIR</div>
              <div className="text-xs text-neutral-500 mt-1">vendredi 19 juin 2026 — 10:00</div>
            </div>
          </div>

          <div className="rounded-md p-3 border border-border bg-fg/[0.02] text-2xs text-fg-muted flex items-start gap-2">
            <Upload size={12} className="mt-0.5 shrink-0" />
            <p>
              Le branding s'applique immédiatement à toutes les notifications par email, aux exports
              PDF et Word des comptes rendus de réunion, et à l'interface de l'application.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────
// Sous-composants
// ─────────────────────────────────────────────────────────────────

function ColorField({
  label, hint, value, onChange, disabled, valid,
}: {
  label: string
  hint?: string
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  valid: boolean
}) {
  return (
    <div>
      <label className="block text-2xs uppercase tracking-wider text-fg-muted font-semibold mb-1.5">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={HEX_RE.test(value) ? value : '#000000'}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="w-12 h-9 rounded border border-border cursor-pointer disabled:opacity-60"
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="flex-1 px-3 py-2 bg-bg border border-border rounded-md text-sm font-mono focus:outline-none focus:ring-2 focus:ring-copper-500/40 disabled:opacity-60"
          placeholder="#2563EB"
          maxLength={7}
        />
        <div
          className="w-10 h-9 rounded border border-border shrink-0"
          style={{ backgroundColor: valid ? value : 'transparent' }}
          title="Aperçu"
        />
      </div>
      {!valid && value && (
        <p className="text-xs text-danger mt-1">Format hexadécimal attendu (ex. #2563EB).</p>
      )}
      {hint && <p className="text-2xs text-fg-subtle mt-1.5">{hint}</p>}
    </div>
  )
}
