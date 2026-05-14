# 27 — CODIR Atelier Theme (Premium Editorial)

## 1. Direction artistique

CODIR adopte le thème **Atelier** — esthétique « private banking digital ».
À mi-chemin entre **Sotheby's app**, **FT**, **Goldman Sachs One** et un **carnet de notaire**.
La plateforme ne crie pas : elle pose. Calme. Feutrée. Autoritaire.

Trois principes :

**Sobriété éditoriale.** Beaucoup d'air, peu d'informations en concurrence visuelle. Une typographie display en serif (Fraunces) pour les titres exécutifs, une sans (Inter Tight) parfaitement lisible pour le corps. La hiérarchie se fait par échelle et graisse, pas par couleur.

**Accent cuivre.** Le cuivre (`#B8693C`) remplace l'orange saturé. Plus mature, plus noble, jamais fluorescent. Apparaît sur les liens, les KPI vedettes, les indicateurs actifs. Or rare en accent (un peu comme un filet doré dans un livre Pléiade).

**Mouvement contenu.** Hover en 250 ms, transitions cubic-bezier(0.32, 0.72, 0.32, 1) qui rappellent un bon papier qui se feuillette. Pas de rotation, pas de glow, pas de scanline. Une animation `ink-slide` pour souligner les liens, un `soft-pulse` discret sur les dots.

## 2. Palette

### Brand cuivre

| Token | Valeur | Usage |
|---|---|---|
| `--copper-500` | `hsl(20 50% 47%)` ≈ `#B8693C` | Pivot brand, boutons primary, dot indicators |
| `--copper-600` | `hsl(18 56% 38%)` | Hover, gradients deeper |
| `--copper-400` | `hsl(22 40% 56%)` | Liens, accents texte |
| `--copper-300` | `hsl(24 32% 66%)` | Underlines, surlignages |
| `--gold`       | `hsl(38 50% 60%)` ≈ `#C9A56A` | Accent luxe rare |

### Surfaces (dark — défaut)

| Token | Valeur | Usage |
|---|---|---|
| `--bg-base` | `hsl(30 8% 7%)` ≈ `#131210` | Canvas encre profonde, ton chaud |
| `--bg-subtle` | `hsl(28 7% 10%)` ≈ `#1A1815` | Sidebar, sections |
| `--bg-elevated` | `hsl(30 6% 13%)` ≈ `#221F1B` | Cards |
| `--fg` | `hsl(36 30% 94%)` ≈ `#F4EFE6` | Ivoire chaud |
| `--fg-muted` | `hsl(32 12% 65%)` | Labels |
| `--fg-subtle` | `hsl(30 8% 45%)` | Captions, hints |
| `--border` | `hsl(30 8% 18%)` | Séparateurs standards |

### Surfaces (light — Atelier paper)

| Token | Valeur | Usage |
|---|---|---|
| `--bg-base` | `hsl(38 30% 96%)` ≈ `#F8F3E9` | Crème ivoire |
| `--bg-subtle` | `hsl(34 25% 92%)` | Sidebar |
| `--bg-elevated` | `hsl(36 35% 99%)` | Blanc chaud presque pur |
| `--fg` | `hsl(28 18% 14%)` ≈ `#2A2421` | Encre |
| `--fg-muted` | `hsl(28 10% 38%)` | Labels |
| `--border` | `hsl(30 18% 86%)` | Séparateurs feutrés |

### Sémantique (tons feutrés)

| État | Token | Note |
|---|---|---|
| Succès | `--success` `hsl(150 35% 55%)` | Sage refined, jamais vert électrique |
| Warning | `--warning` `hsl(38 60% 55%)` | Miel, en harmonie avec cuivre |
| Danger | `--danger` `hsl(4 55% 56%)` | Terracotta, pas rouge violent |
| Info | `--info` `hsl(210 35% 60%)` | Bleu ardoise feutré |

## 3. Typographie

**Fraunces (variable serif)** est la signature du thème. Utilisé pour :
- Titres de page (`text-display`, `text-editorial`, `text-h1`)
- KPI principaux en serif (chiffres avec présence)
- Headlines login, hero exécutif

**Inter Tight (variable sans)** pour le corps, l'UI, les labels, les boutons.

**JetBrains Mono** pour les références (DEC-2026-0042), monospace numbers en tabular.

```
text-hero       4.5rem    Fraunces 500   -0.035em
text-display    3rem      Fraunces 500   -0.025em
text-editorial  2.25rem   Fraunces 500   -0.02em
text-kpi-xl     3.5rem    Fraunces 500 tabular
text-kpi        2.5rem    Fraunces 500 tabular
text-kpi-sm     1.75rem   Fraunces 500 tabular
text-h1         1.625rem  Inter Tight 600
text-h2         1.25rem   Inter Tight 600
text-h3         1.0625rem Inter Tight 600
text-base       1rem      Inter Tight 400
text-sm         0.875rem  Inter Tight 400
text-2xs        0.6875rem Inter Tight 400 tracking +0.04em
```

Helpers : `.serif` (force Fraunces), `.tabular` (numerics alignés).

## 4. Élévations & rayons

**Ombres** layered, douces, jamais glow :

| Token | Usage |
|---|---|
| `shadow-whisper` | Hover discret |
| `shadow-soft` | Boutons secondaires |
| `shadow-card` | Cards standards |
| `shadow-raised` | Hover sur card |
| `shadow-floating` | Modaux, drawers |
| `shadow-copper` | Bouton brand (inset + drop subtle, **pas** glow) |

**Rayons** un peu plus serrés que le HUD : 0.5rem (cards 0.75rem). On veut un look de papier découpé, pas une bulle.

## 5. Composants signatures

| Composant | Description |
|---|---|
| `PremiumCard` | 3 variantes : `flat`, `elevated`, `paper` (papier avec border-left cuivre) |
| `PremiumButton` | 5 variantes : `primary` cuivre solide, `secondary` outline, `ghost`, `danger`, `link` |
| `KpiTile` | Card KPI avec chiffre Fraunces tabular + label small caps |
| `AtelierGauge` | Jauge circulaire sobre, arc cuivre, valeur Fraunces centrée |
| `MasterGauge` | Grand gauge majestueux avec dégradé cuivre + ticks discrets |
| `Spectrum` | Histogramme cuivre statique (remplace les bars dansantes HUD) |
| `StatusBadge`, `PriorityBadge` | Chips minimalistes, palette feutrée |

### Section title pattern

Chaque section porte un titre `label-section` avec petite barre cuivre :

```html
<div class="flex items-center gap-3 text-2xs uppercase tracking-widest text-fg-muted font-semibold">
  <span class="divider-accent" /> Performance Index
</div>
```

Le `.divider-accent` est une barre 24×1 px cuivre. C'est la signature visuelle de l'Atelier.

### Ink underline

Les liens éditoriaux portent une animation `ink-underline` : underline cuivre qui se déploie de gauche à droite au hover (300 ms ease-out).

### Dots indicators

Plutôt que badges colorés, on utilise des `dot` de 6 px (success / warning / danger / copper). Plus discret, plus magazine.

## 6. Patterns Atelier

**Editorial masthead** — chaque page principale s'ouvre par un en-tête type journal :
- Petite ligne supérieure : date écrite en lettres + section
- Titre principal en Fraunces avec une touche italique colorée cuivre
- Sous-titre en sans muted

```
─── Mercredi 13 mai 2026 · Executive Committee

Bonjour, Catherine.
                          ↑ italic copper
Voici la vue consolidée du comité de direction…
```

**Numbered lists** — les items dans les listes ouverts utilisent une numérotation `01 / 02 / 03` en monospace small. Hommage aux sommaires de magazine.

**Hairlines** — les séparations utilisent des lignes 1 px avec gradient transparent. Pas de border-bottom standard.

**Italic accents** — un seul mot en *italique cuivre* dans une phrase tire l'œil. Usage parcimonieux.

**Stats display** — les chiffres KPI sont en Fraunces serif tabular, 3-4xl. Pas de glow. Le label en small caps au-dessus, la delta en small caps en-dessous.

## 7. Pages — concepts visuels

**Dashboard (`/`)** — Masthead éditorial → KPI strip (master gauge + 4 stats) → 3 cards (next session / décisions / signaux) → indicateurs de pilotage (3 jauges).

**Login (`/login`)** — Split screen : storytelling éditorial à gauche (heading hero serif italique cuivre, 3 stats avec divider), formulaire ample à droite (inputs spacieux, italic accent "à l'atelier", SSO Microsoft button discret).

**Meeting list** — Cards avec masthead date, titre en serif, métadonnées en small caps, chip de statut. Hover : translateY -1 + shadow.

**Decision detail** — Header avec ref mono + status chip + numéro éditorial. Titre serif italique. Body en card-paper (border-left cuivre 2px). Historique chronologique avec dots colorés.

**Action plan** — Table sobre, progress bars 2 px épaisses cuivre, dot indicators dans la première colonne, valeurs en mono tabular.

**Notifications** — Liste type Linear/Things : dot couleur sémantique gauche, body éditorial, timestamp small caps droite.

## 8. Animations

Toutes en CSS, durations < 600 ms :

| Classe | Usage |
|---|---|
| `animate-fade-in` | Modaux, toasts |
| `animate-fade-in-up` | Cards à l'arrivée page |
| `animate-rise` | Heroes, login (520 ms) |
| `animate-soft-pulse` | Dots non-lus, indicateurs subtils |
| `animate-ink-slide` | Underlines éditoriaux |

Easing standard : `cubic-bezier(0.32, 0.72, 0.32, 1)` (alias `ease-editorial`). Sensation de respiration confortable, pas de rebond.

## 9. Accessibilité

- Contraste AA respecté : cuivre `#B8693C` sur `#131210` = 4.62:1 (titre), ivoire `#F4EFE6` sur `#131210` = 14:1.
- Focus rings cuivre subtils (`ring-copper-500/40` + offset 2px).
- Aucune animation > 600ms (pas de risque trigger vestibular).
- Hierarchy ARIA via `<header>`, `<section>`, `<aside>`, `<main>` partout.
- Tous les boutons icon-only ont `title` / `aria-label`.

## 10. Stack technique

```
React 18 + TypeScript + Vite
TailwindCSS 3 — config étendue Atelier
Lucide-react (stroke-width 1.75 pour finesse)
Tanstack Query + Router
Fraunces (Google Fonts variable serif)
Inter Tight (Google Fonts)
JetBrains Mono (Google Fonts)
```

Toutes les couleurs sont des tokens HSL exposés en CSS vars. Dark/light bascule via `data-theme` sur `<html>`. Persistance localStorage (`codir-theme`).

## 11. Preview

**Mockup HTML standalone** : [`frontend/mockups/atelier_theme.html`](../frontend/mockups/atelier_theme.html). Ouvre directement, montre le dashboard complet sans avoir besoin du frontend en route.

**Live dans l'app** :

```bash
cd frontend/web
pnpm dev
# → /login : Catherine arrive sur l'éditorial
# → après login : cockpit Atelier
```

## 12. Inspirations explicites

- **Sotheby's app** — sobriété luxueuse, italic editorial
- **Bloomberg Markets magazine** — typographie display Fraunces-like + tabular numerics
- **Goldman Sachs Marquee** — palette charcoal/copper, calme institutionnel
- **Hermès Finance** — accent cuivre/or, espacements généreux
- **Linear** — densité confortable, hierarchy claire
- **Notion** — structure éditoriale, ink underlines
- **Apple Notes** — papier, sérénité, espacements

## 13. À ne pas faire

- ❌ Glow néon (déjà refusé)
- ❌ Gradients agressifs orange saturé
- ❌ Anneaux rotatifs / scanlines
- ❌ Bordures cuivre épaisses (>2 px) → trop ostentatoire
- ❌ Boutons avec shadow-glow → on garde inset subtil
- ❌ Animations > 600 ms ou rebondissantes
- ❌ Empilage de chips colorés → max 1 chip par item de liste
- ❌ Mélanger italic et bold sur la même ligne

## 14. Prochaines itérations

- **Light mode polishing** : finaliser la palette papier crème, ombres encore plus douces.
- **Charts (Recharts/ECharts)** — preset Atelier avec couleurs cuivre/sage/honey/terracotta.
- **AI Copilot drawer** — panneau droit 380 px, fond papier crème (mode dark = élevation +1), pas de glow.
- **Réduction motion** : respecter `prefers-reduced-motion`.
- **Branding per tenant** : chaque organisation peut surcharger `--copper-500/600/400` depuis l'admin (luxury white-label).
- **Email templates** — appliquer la même direction (Fraunces hero + ivoire) aux PV générés et notifications.

---

*Theme Atelier v1.0 — direction artistique validée.*
