# 17 — Roadmap produit

## 1. Vision sur 24 mois

L'arc produit couvre trois grandes étapes : une **v1 MVP** commercialisable à 12 mois qui prouve la promesse "préparer-tenir-exécuter un CODIR", une **v2 Enterprise** à 24 mois qui ouvre le marché des grandes organisations (budgets, risques avancés, ERP, IA décisionnelle), et une **v3 Leadership** à 36 mois qui consolide le positionnement avec le module Conseil d'Administration, l'ESG reporting, et l'IA agentique.

```
2026 ─────────────── 2027 ─────────────── 2028 ─────────────── 2029
│   Foundation       │   Enterprise       │   Leadership       │
│                    │                    │                    │
├── v1.0 Décembre 26 ├── v2.0 Août 27     ├── v3.0 Juin 28     ├──
│   • CODIR core     │   • Budgets        │   • Conseil Admin  │
│   • IA PV          │   • Risques v2     │   • ESG            │
│   • Dashboards x4  │   • ERP            │   • IA agentique   │
│   • Mobile         │   • Signature      │   • Benchmark      │
│   • Beta 10 orgs   │   • IA prédictive  │   • Marketplace    │
```

## 2. v1.0 — MVP commercialisable (T-12)

**Objectif :** mettre dans les mains de 25 clients (dont 5 références) une plateforme qui fait gagner 60 % de temps sur la préparation et la tenue d'un CODIR, et qui produit des comptes rendus de qualité humaine. Cible : organisations 100 à 5 000 employés.

**Périmètre fonctionnel.** Authentification SSO + MFA. Multi-tenant. Organisations et organigramme. CODIR : sessions, convocations, présence, votes, agenda. Décisions et plans d'action. Workflows pré-définis (décision, tâche, PV). KPI et dashboards pour 4 personas (DG, DAF, DRH, DSI). Documents : upload, OCR, versionning. Recherche full-text + sémantique. Mobile Flutter : consultation, validation, vote, notifications. Notifications email + push + inapp. Reporting : PV et compte rendu CODIR (PDF, Word). IA : transcription Whisper, génération PV, copilote Q&A, extraction décisions. Intégrations : Microsoft 365 (Outlook calendrier, OneDrive), Google Workspace, Teams/Zoom (webhooks et liens).

**Non périmètre.** Pas de budgets avancés (juste KPI financiers consommés). Pas de cartographie des risques structurée (juste indicateurs et alertes). Pas de signature électronique externe. Pas de connecteurs ERP. Pas de WhatsApp Business. Pas de scénarios financiers.

**Métriques de succès v1.** 25 organisations clientes, 70 % des décisions tracées sur la plateforme exécutées dans les délais, NPS DG > 40, taux de validation du PV généré automatiquement (< 15 min de relecture humaine) > 90 %.

## 3. v1.x — Itérations post-MVP (T+3 à T+9)

**v1.1** (mois 13) : amélioration UX dashboards d'après retours pilotes, refinements IA (prompts retravaillés sur 50 PV réels), patches sécurité, internationalisation EN.

**v1.2** (mois 14) : WhatsApp Business (Twilio) en canal de notification, signature électronique interne (légalement valable en EU eIDAS niveau simple), API webhooks sortants.

**v1.3** (mois 15) : forecasting de KPI (Prophet), détection d'anomalies sur séries temporelles, exports PowerPoint des dashboards.

**v1.4** (mois 16) : marketplace de templates (catégories de décision, organigrammes types, structures CODIR sectoriels — banque, santé, public, industrie).

**v1.5** (mois 17) : améliorations mobile (mode réunion enrichi, transcription locale Whisper distillé sur device).

**v1.6** (mois 18) : finalisation préparation v2.

## 4. v2.0 — Enterprise (T-24)

**Objectif :** débloquer le segment des grandes organisations (5 000 à 50 000 employés) en couvrant les briques financières et risques avancées, et en s'intégrant avec leurs systèmes (SAP, Sage, Power BI, ADFS, Workday).

**Nouveautés majeures.**

**Budgets et scénarios financiers.** Création de budgets multi-entités, lignes budgétaires, validation hiérarchique, scénarios *what-if*, écarts vs réel, consolidation groupe.

**Cartographie des risques v2.** Risk matrix dynamique, plans de mitigation, lien systématique aux décisions et incidents, conformité (RGPD, ISO 27001, sectorielle), revues périodiques planifiées.

**Signature électronique externe.** Intégration Yousign et DocuSign, workflows multi-signataires ordonnés ou parallèles, horodatage qualifié eIDAS.

**Connecteurs ERP.** SAP S/4HANA (via OData + webhooks), Sage, Odoo, Oracle EBS, Workday. Connecteurs BI : Power BI (push datasets), Tableau, Qlik.

**IA décisionnelle prédictive.** Anticipation des risques (analyse cross-sources), recommandations stratégiques contextualisées, simulation d'impact de décisions, agents IA pour automatisation de workflows.

**Édition Sovereign GA.** Déploiement on-premise / cloud souverain avec IA 100 % locale (Ollama, Whisper.cpp), conformité SecNumCloud, HDS.

**Mobile v2.** Mode réunion ultra-avancé, signature mobile, prise de note vocale (STT local), widgets iOS / Android.

**Métriques cibles.** 120 organisations clientes, 9 M€ ARR, 35 000 WAU, 3 000 réunions/mois.

## 5. v3.0 — Leadership (T-36)

**Module Conseil d'Administration.** Spécifique aux conseils cotés et grandes organisations : convocations légales, secret professionnel, board pack, votes pondérés, comités spécialisés (audit, rémunération, nomination, risques, RSE).

**ESG reporting.** Conformité CSRD, indicateurs ESG suivis comme KPI, génération automatique des rapports de durabilité, intégration avec data providers (Refinitiv, MSCI).

**IA agentique cross-app.** Agents qui orchestrent plusieurs apps : *« Prépare le CODIR du 15 : convoque les 8 membres, rassemble le PV de la session précédente, prépare l'agenda à partir des décisions ouvertes, génère un brief de 2 pages, envoie 48h avant »*.

**Benchmarking inter-organisations.** Comparaison anonymisée de KPI sectoriels (avec consentement explicite) : taux d'exécution décisions, durée moyenne d'une décision, vélocité du CODIR.

**Marketplace plugins.** Plateforme pour que des partenaires (audit, conseil, ERP, sectoriels) développent des extensions.

**White-labeling premium.** Personnalisation visuelle profonde pour les cabinets de conseil (PwC, EY, McKinsey…) qui revendent la plateforme à leurs clients.

## 6. Mappage besoins → versions

| Persona / besoin | v1 | v2 | v3 |
|---|---|---|---|
| Préparer ordre du jour CODIR | ✅ | ✅ | ✅ |
| Tenir réunion hybride avec transcription | ✅ | ✅ | ✅ |
| Générer PV automatique | ✅ | ✅ | ✅ |
| Voter à distance / mobile | ✅ | ✅ | ✅ |
| Suivre décisions et exécution | ✅ | ✅ | ✅ |
| Dashboards exécutifs 4 personas | ✅ | ✅ | ✅ |
| Copilote IA Q&A | ✅ | ✅ | ✅ |
| Documents + OCR + recherche | ✅ | ✅ | ✅ |
| Budgets multi-entités | — | ✅ | ✅ |
| Scénarios financiers what-if | — | ✅ | ✅ |
| Cartographie risques avancée | — | ✅ | ✅ |
| Signature électronique externe | — | ✅ | ✅ |
| Connecteurs SAP / Sage / Oracle | — | ✅ | ✅ |
| Connecteurs Power BI / Tableau | — | ✅ | ✅ |
| IA prédictive (forecast, recommandations) | — | ✅ | ✅ |
| WhatsApp Business notifications | — | ✅ | ✅ |
| Conseil d'Administration | — | — | ✅ |
| ESG / CSRD reporting | — | — | ✅ |
| IA agentique cross-app | — | — | ✅ |
| Benchmark inter-organisations | — | — | ✅ |
| Marketplace plugins | — | — | ✅ |

## 7. Hypothèses produit à valider d'ici v1

| Hypothèse | Méthode | Verdict cible |
|---|---|---|
| Qualité PV IA suffisante (< 15 min de relecture) | Test sur 100 réunions réelles avec 10 clients pilotes | Validé à 85 % |
| DG accepte l'IA dans le processus de décision | Interview qualitative + analytique d'usage du copilote | 75 % d'usage hebdo |
| Intégration M365 résout 80 % des cas | Mesure d'adoption Outlook calendrier + Teams | 80 % des réunions sync |
| Mobile représente 30 %+ de l'usage exécutif | Telemetry sur sessions par device | ≥ 30 % |
| Multi-tenant logique tient la confiance enterprise | Audit pen test + tests croisés | 0 fuite, 0 violation |

## 8. Anti-roadmap (ce qu'on **ne fait pas**)

Pour rester focalisé, on documente explicitement ce qu'on refuse :

- Pas de remplacement de visioconférence (on intègre Teams/Zoom, on ne les concurrence pas).
- Pas de remplacement d'outils RH (Workday, BambooHR) — on consomme leurs données via intégration.
- Pas de comptabilité (SAP, Sage gardent leur rôle).
- Pas de GED généraliste (SharePoint, Box, Drive) — on indexe et consomme la leur.
- Pas de chat d'équipe (Slack, Teams) — pas de "Slack pour exécutifs".
- Pas de gestion de projet à la Jira / Asana — on gère les **plans d'action issus de décisions**, pas la roadmap engineering.

Cette discipline est ce qui permet à CODIR d'être *le* logiciel du CODIR et pas un produit générique.

---

*Suite : [18 — Roadmap technique](18_roadmap_technique.md)*
