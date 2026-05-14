# 15 — Dashboards exécutifs

## 1. Philosophie

Un dashboard CODIR n'est pas un *rapport* — c'est un **espace de décision**. Trois principes :

**Réduction.** Le DG ne lit pas un dashboard, il le scanne. 7 ± 2 informations majeures au-dessus de la ligne de flottaison, hiérarchisées par criticité, jamais par ordre alphabétique.

**Drill-down.** Toute valeur agrégée doit être explorable en 3 clics maximum jusqu'à la donnée atomique (la décision, la dépense, l'incident).

**Action.** Là où c'est pertinent, le dashboard ne se contente pas d'afficher — il propose : *« 3 décisions en retard. Voir et relancer »*, *« KPI X dégradé. Voir cause IA »*.

## 2. Dashboards livrés par persona

### 2.1. Dashboard DG (Cockpit exécutif)

C'est le dashboard signature. Il combine tous les axes en une vue unique.

**Ligne 1 — Pulse organisationnel.** 6 KPI top : Revenu MTD, Marge, Trésorerie, Effectif total, Décisions ouvertes, Risques critiques. Chaque carte : valeur, variation vs M-1, sparkline 12 mois, couleur sémantique selon seuil.

**Ligne 2 — Carte de chaleur stratégique.** Heatmap *Direction × Performance* (vert/ambre/rouge), où chaque cellule est cliquable et ouvre le dashboard direction associé.

**Ligne 3 — Décisions exécutives en cours.** Liste des décisions critiques en cours, sorted by `priority desc, deadline asc`. Chaque ligne : référence, titre, responsable, échéance, statut, avancement (%). Action inline : "Relancer".

**Ligne 4 — Prochain CODIR.** Carte agenda : date, heure, ordre du jour (avec items les plus chauds), participants attendus. Action : préparer mon mot d'introduction (IA).

**Ligne 5 — Risques actifs.** Mini-heatmap impact × probabilité (5×5). Risques rouges listés à côté avec mitigation owner + statut.

**Ligne 6 — Briefing IA quotidien.** Bloc texte généré chaque matin par le copilote IA : *« Trois points d'attention ce matin : (1)… (2)… (3)… »* avec citations cliquables vers les sources.

**Bas de page — Activité récente.** Feed des dernières mutations critiques (décisions créées, signatures, alertes KPI). Discret mais accessible.

### 2.2. Dashboard DAF

**KPI top** : Chiffre d'affaires (MTD/YTD vs N-1 et budget), Marge brute, EBITDA, Cash position, BFR (jours), DSO, DPO.

**Vues clés** : Réalisé vs budget par direction (bar chart), évolution de la trésorerie 90 j (line chart + forecast), top 10 dépenses du mois, projections de fin d'année (3 scénarios), top engagements à valider.

**Sections** :
- Budget : vue consolidée, écarts > 5 %, drill par ligne.
- Cash : flux entrants/sortants, prévisions.
- Engagements : signatures en attente, factures à valider.
- KPI financiers personnalisés.

### 2.3. Dashboard DRH

**KPI top** : Effectif total, Variation vs M-1, Turnover, Absentéisme (taux et tendance), Coût salarial total, eNPS, Compétences critiques manquantes.

**Vues clés** : Pyramide des âges (radar), répartition H/F par direction (bar stacked), évolution des départs/embauches (sankey), heatmap engagement par équipe.

**Alertes** : départs imminents non remplacés, formations obligatoires à venir, postes vacants à pourvoir.

### 2.4. Dashboard DSI

**KPI top** : Disponibilité plateforme, MTTR, MTBF, Incidents en cours, Backlog projets, Sécurité (CVE à fixer), Coût SI.

**Vues clés** : Carte des SI critiques (status), incidents et MTTR par criticité, dépendance des projets stratégiques sur le SI, capacité projet vs charge.

### 2.5. Dashboard Directeur Technique / COO

**KPI top** : OEE, taux de service, qualité (PPM), HSE (incidents), avancement programmes industriels.

### 2.6. Dashboard Commercial / Directeur Commercial

**KPI top** : Pipe value, conversion rate, deals signés MTD, AOV, churn, NPS.

**Vues** : pipeline par stage (funnel), top deals à closer, top accounts à risque, prévision atterrissage trimestriel.

### 2.7. Dashboard PMO / Contrôle de gestion

C'est un dashboard *de pilotage*, plus dense, taillé pour un analyste.

**Sections** : tableau croisé de tous les projets stratégiques (avancement, budget, risques, livrables), suivi des engagements CODIR (taux exécution, retards), reporting consolidé par direction, génération de rapports planifiés.

## 3. Configuration d'un dashboard

Un `Dashboard` est composé de `DashboardWidget`. Chaque widget a :

```json
{
  "id": "w_42",
  "type": "kpi_card",                       // kpi_card | line | bar | pie | heatmap | radar | table | text | feed
  "title": "Trésorerie",
  "data_source": {
    "type": "kpi",                           // kpi | query | manual | integration
    "kpi_id": "kpi_treasury",
    "period": "last_90_days",
    "granularity": "day",
    "filters": {"entity": "group"},
    "comparison": "prev_period"
  },
  "format": {
    "value_unit": "M€",
    "decimals": 2,
    "trend": true,
    "sparkline": true
  },
  "thresholds": {
    "warning": "< 5",
    "critical": "< 2"
  },
  "position": {"x": 0, "y": 0, "w": 3, "h": 2},
  "drilldown": {
    "type": "navigate",
    "target": "/finance/treasury"
  },
  "actions": [
    {"label": "Voir détail", "icon": "external-link", "target": "/finance/treasury"}
  ]
}
```

Les widgets sont placés via un layout **gridstack** (12 colonnes, hauteur libre). Le DG peut customiser le layout, dupliquer un dashboard standard, créer ses propres widgets.

## 4. Sources de données

Quatre sources :

**KPI managé** (`apps/kpis`). Le widget consomme `KPISnapshot` selon la période. C'est la source la plus courante.

**Query** (DSL). Permet d'agréger ad-hoc : *« nombre de décisions par direction sur les 30 derniers jours »*. Le DSL est traduit en ORM Django, exécuté avec timeout, résultat caché 60 s.

**Manual**. Valeurs saisies périodiquement (utile pour des KPI sans source automatisée — satisfaction enquête trimestrielle).

**Integration**. Pulled depuis un connecteur (Power BI dataset, SAP report, custom API). Cache 5 min par défaut.

## 5. Calcul des KPI

```python
# apps/kpis/services.py
class KPICalculator:
    def calculate(self, kpi: KPI, period_start, period_end) -> KPISnapshot:
        if kpi.source_integration:
            value = self._from_integration(kpi, period_start, period_end)
        elif kpi.formula:
            value = self._from_formula(kpi, period_start, period_end)
        else:
            raise ValueError("No source configured")
        snapshot = KPISnapshot.objects.create(
            kpi=kpi, value=value, period_start=period_start, period_end=period_end,
            breakdown_json=self._compute_breakdown(kpi, period_start, period_end),
        )
        self._check_thresholds(kpi, snapshot)
        return snapshot

    def _from_formula(self, kpi, ps, pe):
        # DSL: aggregate('sum', source='budgets.BudgetSpend', filter={'period': [ps,pe]}, field='amount')
        ast = parse_formula(kpi.formula)
        return execute(ast, organization=current_organization.get(), ps=ps, pe=pe)
```

Le DSL formule supporte les agrégats SUM/AVG/COUNT/MIN/MAX, filtres, ratios, et combinaisons.

```
kpi: "trésorerie nette"
formula: "aggregate(sum, 'cashflow.Inflow', period) - aggregate(sum, 'cashflow.Outflow', period)"

kpi: "taux d'exécution des décisions"
formula: "count('decisions.Decision', status='completed', period) / count('decisions.Decision', status__in=['approved','in_progress','completed'], period) * 100"
```

## 6. Forecasting

Pour les KPI à fréquence quotidienne ou plus rapide, un forecast 3-mois est calculé via Prophet (Facebook) ou NeuralProphet pour les séries riches. Le forecast est stocké dans `Forecast` et affichable en surimpression dans le widget. Précision (MAPE) affichée à côté de la projection.

## 7. Alertes et seuils

Chaque KPI peut définir `warning_threshold` et `critical_threshold`. Quand un snapshot franchit le seuil, un `KPIAlert` est créé et :

- pushé en WebSocket aux dashboards consommateurs
- notifié par email/push aux destinataires configurés
- analysé par l'IA pour proposer une cause probable (regard sur les autres KPI, les décisions récentes, les événements externes connus)

## 8. Performance des dashboards

Cibles : un dashboard se charge en **< 1,5 s** complet (TTI), même sur un DG avec 30+ widgets. Stratégie :

- **Pré-calcul** : chaque KPI à fréquence > horaire calcule son snapshot en background ; le widget ne fait que lire.
- **Streaming WS** : les widgets temps réel reçoivent des deltas, pas des refetches.
- **Sparse loading** : les widgets hors viewport ne se chargent qu'au scroll.
- **Cache CDN** pour les composants visuels lourds (templates).

## 9. Sécurité des dashboards

Les widgets honorent strictement le RBAC + ABAC. Un widget *« Décisions ouvertes »* filtre selon la direction de l'utilisateur. Un widget *« Trésorerie »* exige `kpis:financial:view`. Le service de rendu refuse les widgets dont la source de données n'est pas autorisée — pas seulement les UI cachées.

## 10. Export et reporting

Tout dashboard est exportable en **PDF** (snapshot graphique + tableau de bord) et **PowerPoint** (slide par section). L'export est asynchrone (`apps/reports`), le résultat est un document signé avec horodatage et expéditeur.

Les rapports planifiés (CFO weekly, RH monthly, audit trimestriel) sont configurés par les utilisateurs et délivrés automatiquement.

## 11. Mockup HTML

Voir les maquettes interactives dans :
- [`frontend/mockups/dashboard_dg.html`](../frontend/mockups/dashboard_dg.html) — cockpit DG
- [`frontend/mockups/dashboard_daf.html`](../frontend/mockups/dashboard_daf.html) — cockpit DAF

---

*Suite : [16 — UX / UI](16_ux_ui.md)*
