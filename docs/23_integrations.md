# 23 — Intégrations

## 1. Stratégie d'intégration

CODIR ne remplace pas les systèmes existants des grandes organisations — il s'intègre. Trois catégories d'intégration :

**Productivité** (calendrier, mail, fichiers, visio) — incontournable dès v1.
**Données métier** (ERP financier, RH, BI) — débloque la valeur en v2.
**Communication** (chat, messagerie) — additionnel mais attendu.

L'architecture est conçue pour rendre chaque intégration **un module isolé** (`apps/integrations/<provider>/`) qui implémente un contrat unique. Activable / désactivable par tenant.

## 2. Cartographie des intégrations v1/v2

### v1 — Productivity layer

| Intégration | Direction | Cas d'usage |
|---|---|---|
| Microsoft 365 (Outlook, Teams, OneDrive) | bi | Sync calendrier CODIR, lancement Teams, ingestion documents |
| Google Workspace (Calendar, Meet, Drive) | bi | Idem côté Google |
| Zoom | uni (out) | Création réunions + lien |
| SharePoint Online | uni (in) | Ingestion documents board pack |
| Email SMTP / SES / SendGrid | out | Notifications |
| SMS Twilio / Vonage | out | Notifications critiques |
| Push FCM + APNs | out | Notifications mobile |
| Calendar ICS feeds | out | Export pour outils tiers |

### v2 — Enterprise systems

| Intégration | Direction | Cas d'usage |
|---|---|---|
| SAP S/4HANA | bi | KPI financiers, budgets, dépenses |
| Oracle EBS | bi | Idem |
| Sage X3 | bi | PME / mid-market |
| Odoo | bi | Open source / Afrique |
| Workday | bi | KPI RH |
| BambooHR / Personio | in | Idem PME |
| Power BI | bi | Push datasets / pull reports |
| Tableau | in | Embed dashboards |
| Qlik Sense | in | Embed dashboards |
| Yousign | bi | Signature électronique |
| DocuSign | bi | Idem |
| WhatsApp Business (Twilio) | out | Notifications critiques |
| Slack | bi | Notifications + commandes slash |
| ServiceNow | bi | Incidents + risques |
| Jira / Linear | uni (out) | Création tickets actions |

### v3 — Specialized

| Intégration | Cas d'usage |
|---|---|
| MSCI / Refinitiv ESG | Datafeeds ESG |
| Bloomberg Terminal | KPI marché |
| ADFS / SAML legacy | SSO entreprise legacy |
| Keycloak | SSO open source |
| Active Directory LDAP | Sync utilisateurs on-prem |

## 3. Architecture d'une intégration

Chaque intégration est un module dans `apps/integrations/<provider>/` :

```
apps/integrations/
├── __init__.py
├── base.py                      ← contrat abstrait
├── registry.py                  ← découverte
├── models.py                    ← Integration, Credentials, SyncRun
├── views.py                     ← endpoints OAuth, configuration
├── tasks.py                     ← Celery sync tasks
├── m365/
│   ├── connector.py             ← implémentation
│   ├── auth.py                  ← OAuth flow
│   ├── tasks.py                 ← jobs spécifiques
│   ├── mappers.py               ← transformations
│   └── tests/
├── google/
├── sap/
├── sage/
├── yousign/
├── powerbi/
├── slack/
├── whatsapp/
└── webhooks/                    ← gestion webhooks entrants
```

Contrat abstrait :

```python
# apps/integrations/base.py
from abc import ABC, abstractmethod

class Connector(ABC):
    code: str               # "m365", "sap", etc.
    name: str
    capabilities: set[str]  # {"calendar.sync", "files.ingest", "users.sync"}

    @abstractmethod
    def authenticate(self, organization, request) -> dict: ...

    @abstractmethod
    def test_connection(self, integration: "Integration") -> bool: ...

    @abstractmethod
    def sync(self, integration: "Integration", scope: str | None = None) -> "SyncRun": ...

    @abstractmethod
    def handle_webhook(self, event: dict) -> None: ...
```

## 4. Authentification — modes supportés

| Mode | Cas d'usage typique |
|---|---|
| OAuth2 (3-legged) | M365, Google, Slack, Zoom, Yousign, DocuSign — utilisateur consent |
| OAuth2 client credentials | Power BI service principal, Azure AD apps |
| API Key | Twilio, SendGrid, Tableau |
| Basic auth | Legacy ERP, Odoo |
| Certificat client | SAP via OData, gouvernement |
| SAML 2.0 | SSO Workday, ADFS |
| OIDC | SSO moderne |

Tous les credentials sont chiffrés en base (Vault transit) et accessibles uniquement via la classe `IntegrationCredential` qui déchiffre à la volée.

## 5. Synchronisations — patterns

### 5.1. Pull périodique (Celery beat)

La plupart des sync ERP/BI sont *pull* sur cron :

```python
@app.task(base=TenantTask, bind=True, max_retries=3, default_retry_delay=300)
def sync_sap_kpis(self, integration_id):
    integration = Integration.objects.get(id=integration_id)
    connector = registry.get("sap")
    with sync_run(integration) as run:
        for kpi_data in connector.fetch_kpis(integration):
            apply_kpi_snapshot(kpi_data, organization=integration.organization)
            run.records_in += 1
        run.complete()
```

### 5.2. Webhooks entrants

Beaucoup d'API modernes (M365, Slack, Yousign) poussent les changements. Un service FastAPI dédié `webhook-gateway` reçoit, valide (signature HMAC, IP allowlist), et dispatche vers Celery :

```python
# webhook-gateway/main.py
@app.post("/hooks/{provider}/{tenant_slug}")
async def webhook(provider: str, tenant_slug: str, request: Request):
    body = await request.body()
    verify_signature(provider, request.headers, body)
    payload = await request.json()
    enqueue_celery_task(f"apps.integrations.{provider}.tasks.handle_webhook", tenant_slug, payload)
    return {"ok": True}
```

### 5.3. Push sortants

Quand CODIR doit notifier un système externe (créer un ticket Jira, publier un message Slack, créer un événement Outlook), c'est un appel sortant Celery, avec idempotency key, retry, et journalisation dans `WebhookDelivery`.

### 5.4. Bulk import initial

Pour le go-live d'une intégration, un job spécial `initial_import` charge l'historique (organigramme, employés, budgets passés). Job long, idempotent, reprenant après crash.

## 6. Sync calendrier — Microsoft 365 / Google

Le cas le plus utilisé. Sync **bi-directionnel** :

- Création d'une réunion CODIR → événement Outlook/Google créé pour chaque participant (avec ICS, lien Teams/Meet)
- Modification CODIR → événements externes mis à jour
- Réponse RSVP côté Outlook → mise à jour `Participation` côté CODIR
- Suppression côté externe → tracé dans audit, alerte secrétaire général

Implémentation : OAuth utilisateur (chaque exécutif autorise sa propre calendrier Outlook). Microsoft Graph API et Google Calendar API. Webhooks pour les changements.

## 7. Ingestion documents — SharePoint / Drive

Plusieurs modes :

**Référentiel externe** — un document SharePoint reste dans SharePoint ; CODIR référence l'URL et indexe le contenu (texte, OCR) pour la recherche, sans dupliquer. Idéal pour les organisations qui veulent garder leur GED comme source unique.

**Import et copie** — le document est rapatrié dans MinIO interne. Garantit la disponibilité, mais doublonne.

**Synchro continue** — un dossier dédié SharePoint est synchronisé bidirectionnellement (nouvelle version SharePoint → nouvelle version CODIR ; édition CODIR → push SharePoint).

Le choix est par configuration tenant et par dossier.

## 8. SAP / Sage / Odoo — feed de KPI financiers

Cas d'usage central pour la v2 : le DAF veut voir son cash, son CA, sa marge sans saisie manuelle.

**SAP S/4HANA** :
- OData services standard (`/sap/opu/odata/sap/`) pour les KPI agrégés.
- BAPI / RFC pour les volumes plus fins.
- Connexion via `pysap` ou via une couche middleware (SAP PI/PO / SAP Integration Suite).
- Authentification : certificat client ou OAuth selon S/4HANA Cloud vs on-prem.

**Sage** :
- API REST native pour Sage 100 Cloud.
- ODBC / SQL pour Sage on-prem (extracteur léger côté client).

**Odoo** :
- API XML-RPC et JSON-RPC standard, simple, complète.

Pattern unique : un *KPI mapping* configurable par tenant définit `kpi_codir_code ↔ provider_query`. L'admin peut ajouter / éditer des mappings sans code.

## 9. Power BI

Trois modes d'intégration :

- **Push datasets** : CODIR publie ses propres KPI dans Power BI (REST push API) pour que les analystes les exploitent dans leurs rapports.
- **Embed reports** : un dashboard CODIR peut embarquer un rapport Power BI dans un widget (`type: "powerbi_embed"`). Authentification via service principal Power BI Embedded.
- **Pull datasets** : CODIR ingère un dataset Power BI (DAX query) comme source de KPI.

## 10. Signature électronique — Yousign / DocuSign

Workflow standard :

1. Document à signer généré (PV, contrat, décision actée).
2. CODIR crée une `SignatureRequest` interne avec ordre des signataires.
3. Connector pousse vers Yousign/DocuSign avec callback URL.
4. Signataires reçoivent email externe + notification CODIR.
5. Webhook entrant à chaque signature → update CODIR.
6. À la fin, le PDF signé revient et est attaché au document original.

Conformité eIDAS niveau "Avancée" pour les usages standards, "Qualifiée" (avec certificat qualifié) sur option.

## 11. WhatsApp Business — notifications critiques

Pour les marchés où WhatsApp est le canal de communication exécutif (Afrique, MENA, Amérique latine), CODIR pousse les notifications critiques via Twilio WhatsApp Business :

- Templates de message approuvés par WhatsApp (obligatoire en B2C).
- Possibilité de réponse rapide (boutons "Voir" / "Approuver").
- Webhooks pour les réponses utilisateur.

## 12. Slack / Teams — notifications + commandes

Au-delà des notifications, slash commands :

```
/codir prochain          → infos prochain CODIR
/codir decisions @user   → décisions ouvertes assignées à user
/codir kpi treasury      → valeur actuelle + sparkline
```

Implémentation classique : app Slack/Teams configurée par tenant, OAuth pour installation, webhook backend pour les commandes.

## 13. Webhooks sortants (developers)

CODIR expose ses propres événements aux systèmes tiers :

```
decision.created
decision.approved
decision.completed
meeting.started
meeting.ended
meeting.minutes_ready
kpi.threshold.breached
risk.identified
action.due_soon
action.overdue
```

L'admin tenant configure des `Webhook` (target URL, secret HMAC, headers). À chaque event, livraison avec retry (5 tentatives, backoff exponentiel), audit dans `WebhookDelivery`. Conforme aux standards (signature HMAC SHA-256, timestamp anti-replay).

## 14. Gestion des erreurs

Une intégration en échec ne doit jamais bloquer le métier :

- Sync échouée → KPI affiché "non actualisé depuis X minutes" + retry programmé.
- Webhook livraison échouée → escalade après 5 échecs, mais l'event reste dans l'outbox 7 jours.
- API tierce en panne → circuit breaker (5 erreurs 1 min → ouvrir 5 min → demi-ouvert).
- Notifications critiques aux admins du tenant après 1 h sans sync.

## 15. Marketplace v3 — vision

L'objectif moyen terme est d'ouvrir une **marketplace d'intégrations** :
- Partenaires (cabinets de conseil, ESN, intégrateurs sectoriels) peuvent développer des connecteurs.
- SDK Python + OpenAPI pour faciliter le développement.
- Process de validation et certification CODIR avant publication.
- Partage de revenus sur les connecteurs payants.

---

*Suite : [25 — Features premium](25_features_premium.md)*
