# 16 — UX / UI

## 1. Vision UX

CODIR est conçu pour des **dirigeants pressés**. L'interface doit transmettre, en quelques secondes, l'état de l'organisation et permettre d'agir sans friction. Quatre invariants en découlent :

**Vitesse perçue maximale.** Pas d'écran de chargement bloquant. Skeletons, optimistic UI, navigation instantanée. Toute interaction donne un retour visuel en < 80 ms.

**Densité élégante.** Pas de minimalisme excessif (un DG veut voir 30 informations sur son écran, pas 6 cartes vides). Mais une hiérarchie typographique claire et un espacement régulier qui rendent la densité respirable.

**Sobriété corporate.** Couleurs primaires retenues, palette neutre dominante. Aucun élément décoratif gratuit. Le luxe est dans le détail (transitions millimétrées, typographie premium).

**Confiance par la transparence.** Toutes les actions sont annotées (qui, quand, état). L'IA est *transparente* : on voit toujours pourquoi elle propose quelque chose et on peut cliquer pour voir les sources.

## 2. Design tokens

```
─── Couleurs sémantiques ───────────────────────────────
Primary       hsl(220, 90%, 56%)    bleu exécutif
Primary-fg    hsl(0, 0%, 100%)
Success       hsl(142, 76%, 36%)    vert sobre
Warning       hsl(38, 92%, 50%)     ambre alerte
Danger        hsl(0, 84%, 60%)      rouge action
Info          hsl(200, 95%, 50%)    bleu info
Critical      hsl(335, 80%, 50%)    magenta urgence (rare)

─── Surfaces ───────────────────────────────────────────
Bg            hsl(0, 0%, 100%)
Bg-subtle     hsl(220, 20%, 98%)
Bg-elevated   hsl(0, 0%, 100%)
Border        hsl(220, 13%, 91%)
Border-strong hsl(220, 13%, 80%)

─── Texte ──────────────────────────────────────────────
Fg            hsl(222, 47%, 11%)
Fg-muted      hsl(215, 16%, 47%)
Fg-subtle     hsl(220, 14%, 70%)

─── Dark mode (inversions ciblées) ─────────────────────
Bg            hsl(222, 47%, 7%)
Bg-elevated   hsl(222, 47%, 11%)
Border        hsl(217, 33%, 17%)
Fg            hsl(210, 40%, 98%)
Fg-muted      hsl(215, 20%, 65%)

─── Typo ───────────────────────────────────────────────
Display       Inter, 600, 32-48px
H1            Inter, 600, 24px
H2            Inter, 600, 20px
H3            Inter, 600, 16px
Body          Inter, 400, 14px
Body-strong   Inter, 500, 14px
Caption       Inter, 400, 12px, fg-muted
Number        Inter, 600, tabular-nums

─── Rayons ─────────────────────────────────────────────
sm 4px   md 8px   lg 12px   xl 16px   full 9999px

─── Élévation ──────────────────────────────────────────
shadow-sm    0 1px 2px rgba(15,23,42,.06)
shadow-md    0 4px 6px -1px rgba(15,23,42,.10)
shadow-lg    0 10px 15px -3px rgba(15,23,42,.10)
shadow-exec  0 0 0 1px rgba(15,23,42,.04), 0 12px 24px -8px rgba(15,23,42,.20)

─── Spacing ────────────────────────────────────────────
4 / 8 / 12 / 16 / 24 / 32 / 48 / 64
```

## 3. Layout principal (web)

```
┌──────────────────────────────────────────────────────────────────────┐
│  ▣ CODIR        [Search…  ⌘K]              🔔  ✨ Copilot  👤 SD    │  ← Topbar 56 px
├────────────┬─────────────────────────────────────────────────────────┤
│            │                                                         │
│  Sidebar   │                                                         │
│  240 px    │                                                         │
│            │                Main content                              │
│  Logo      │                                                         │
│  Dashboard │                                                         │
│  Réunions  │                                                         │
│  Décisions │                                                         │
│  Actions   │                                                         │
│  Docs      │                                                         │
│  KPI       │                                                         │
│  Budgets   │                                                         │
│  Risques   │                                                         │
│  Rapports  │                                                         │
│  Audit     │                                                         │
│  Admin     │                                                         │
│            │                                                         │
│  [⏷ Collap]│                                                         │
└────────────┴─────────────────────────────────────────────────────────┘
```

Sidebar collapsible (60 px en mode collapsed avec icônes seules). Topbar fixe.
Au-dessus de 1440 px, un panneau contextuel droit (340 px) peut s'ouvrir pour le copilot IA, les notifications, ou un détail d'entité, sans quitter la page.

## 4. Composants UI signature

**KPI Card** — la brique la plus utilisée. Variantes par criticité.

```
┌─────────────────────────┐
│  Trésorerie             │  ← caption fg-muted
│  4,2 M€                 │  ← display, tabular-nums
│  ▼ -8% vs M-1           │  ← trend (rouge)
│  ╲ ╱ ╲ ╱╲___           │  ← sparkline 90 j
│  Voir détail →          │  ← link action
└─────────────────────────┘
```

**Decision Card** — utilisée dans les listes et les feeds.

```
┌───────────────────────────────────────────────┐
│  ●●●●○  CRITIQUE      DEC-2026-0042           │
│  Lancement projet Phoenix                     │
│  📌 DSI · Catherine Martin · 31/12/2026      │
│  ┃ Investissement de 4,2 M€ pour…             │
│  ▓▓▓▓▓▓▓░░░░░░  62% — en cours                │
│  [Détail]  [Plan d'action]  [Voter]           │
└───────────────────────────────────────────────┘
```

**Meeting Timeline** — fil chronologique d'une réunion live.

```
10:00 ━━ Ouverture (Catherine M.)
10:04 ┃  Sujet 1: Revue trimestrielle Finance (5 min écoulées)
10:09 ┃  Décision: DEC-2026-0041 votée (9 ✓ / 2 ✗ / 1 ↺)
10:12 ━━ Sujet 2: Lancement Phoenix ◀ courant
10:18 ┃  ✨ IA: "Le coût TCO sur 5 ans semble sous-estimé"
```

**Risk Heatmap** — matrice 5×5 impact × probabilité, cellules colorées, taille proportionnelle au nombre de risques.

**Workflow Stepper** — pour les processus à étapes (signature, budget validation).

**AI Suggestion Banner** — bandeau discret en haut de certaines pages : *« ✨ J'ai préparé un brouillon d'ordre du jour basé sur les sujets en attente — voir »* avec accept/dismiss.

## 5. Patterns d'interaction

**Command palette** (Cmd+K / Ctrl+K) ouvre une palette fuzzy-search à travers tout : décisions, documents, réunions, KPI, paramètres. Compléments IA proposés (*« Demander au copilot : X »*). Apparaît en < 100 ms.

**Quick actions** : sur les listes, chaque ligne survolée révèle 2-3 actions principales (sans menu déroulant si l'écran est large).

**Inline edit** : titres, descriptions, échéances éditables directement sans modal (Enter pour valider, Esc pour annuler).

**Confirmations contextuelles** : pour les actions destructrices, une confirmation *inline* (bouton secondaire qui se transforme en confirmation rouge pendant 5 s), pas un modal bloquant.

**Toaster discret** en bas-droite pour les confirmations légères, durée 3 s, avec undo si possible.

**Empty states soignés** : illustration sobre, phrase courte, CTA principal. Pas de "Vous n'avez rien".

**Skeletons** sur tout chargement > 200 ms.

## 6. Notifications dans l'UI

Trois niveaux de visibilité :

- **Cloche topbar** : indicateur de notifications non lues (compteur < 99, sinon 99+). Panneau déroulant 380 px.
- **Toaster** : pour les événements pendant la session courante (action complétée, erreur).
- **Banner haut de page** : pour les événements critiques persistants (KPI breach, risque rouge nouvellement identifié).

Les notifications inapp arrivent en temps réel via WS.

## 7. Mode sombre

Implémenté nativement (`dark:` Tailwind + tokens CSS). Choix utilisateur (clair/sombre/système) persisté. Évite les variations trop brutales : surface dark = `hsl(222, 47%, 7%)`, pas noir pur, pour la fatigue oculaire.

## 8. Accessibilité — détails

- Tous les composants Shadcn/Radix sont a11y par défaut (focus visible, ARIA, navigation clavier).
- Sur les charts, fallback table accessible (`<table>` caché visuellement mais exposé aux lecteurs d'écran).
- Lecteurs d'écran : annonces `aria-live="polite"` pour les notifications, `aria-live="assertive"` pour les alertes critiques.
- Mode haut contraste activable.
- Tailles de police ajustables (3 niveaux).

## 9. Internationalisation

Toutes les chaînes externalisées. Versions `fr-FR` et `en-US` v1. Versions `pt-PT`, `es-ES`, `ar-MA` planifiées v2 (RTL géré pour l'arabe via Tailwind `dir-rtl:`).

Les chiffres respectent les locales (espace insécable pour les milliers en `fr`, virgule décimale, codes monnaies).

## 10. Responsive

- **Desktop large** (≥ 1440 px) : layout complet 3 colonnes possible (sidebar + main + side panel).
- **Desktop standard** (1024–1439 px) : sidebar + main, side panel en overlay.
- **Tablette** (768–1023 px) : sidebar repliable, main pleine largeur, lecture optimisée.
- **Mobile** (< 768 px) : navigation par bottom bar, sidebar en drawer, UI grandement repensée — mais le mobile **est l'app Flutter**, pas le web responsive (le web reste utilisable sur mobile en lecture).

## 11. Animations

Trois familles :
- **Micro-interactions** : 100-150 ms ease-out (boutons, toggles, ripple discret).
- **Transitions de panneaux** : 200-250 ms cubic-bezier(0.16, 1, 0.3, 1).
- **Charts** : entrée 400 ms, mises à jour 300 ms (interpolation des valeurs).

Pas d'animation gratuite. Tout ce qui n'aide pas à comprendre une transformation est supprimé.

## 12. Storybook et design ops

Tous les composants UI réutilisables sont documentés dans un Storybook public interne (par produit). Chaque composant a : props documentées, états (default/hover/active/disabled), variants, exemples d'usage.

Le design ops est servi par Figma (lib partagée), branchée à GitHub via "Figma Tokens" pour synchroniser les design tokens directement vers le code.

## 13. Maquettes livrées

5 mockups HTML interactifs dans [`frontend/mockups/`](../frontend/mockups/) :

| Mockup | Description |
|---|---|
| `index.html` | Hub d'index des maquettes |
| `dashboard_dg.html` | Cockpit exécutif DG complet |
| `dashboard_daf.html` | Cockpit DAF avec budget et cash |
| `meeting_live.html` | Mode réunion live avec IA et votes |
| `ai_assistant.html` | Copilote IA conversationnel |
| `mobile_executive.html` | App mobile (rendu iPhone) |

---

*Suite : [17 — Roadmap produit](17_roadmap_produit.md)*
