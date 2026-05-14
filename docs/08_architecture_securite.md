# 08 — Architecture sécurité

## 1. Posture de sécurité

CODIR manipule des données extrêmement sensibles : stratégie d'entreprise, décisions financières, données RH, risques cyber, contenus confidentiels d'État pour les éditions Sovereign. La posture est **zéro confiance** : aucune requête, interne ou externe, n'est implicitement digne de confiance. Chaque appel s'authentifie, s'autorise, se journalise. Le périmètre réseau n'est pas une frontière de sécurité — la frontière est l'identité.

Trois objectifs structurants :

- **Confidentialité** : aucune donnée ne fuit, ni entre tenants, ni vers l'extérieur, ni vers les fournisseurs IA tiers sans consentement explicite.
- **Intégrité** : aucune décision, aucun vote, aucun PV ne peut être altéré sans laisser de trace.
- **Disponibilité** : la plateforme tient à 99,9 % pour les éditions Enterprise (8,7 h d'indisponibilité/an max), 99,95 % pour Sovereign.

## 2. Conformité visée

| Standard | Statut visé | Année |
|---|---|---|
| RGPD | Conformité native | v1 |
| ISO/IEC 27001 | Certification | An 2 |
| ISO/IEC 27701 (privacy) | Certification | An 2 |
| SOC 2 Type II | Rapport annuel | An 1 fin |
| HDS (santé France) | Hébergement HDS optionnel | An 2 |
| HIPAA | Compatible (déploiement dédié) | An 3 |
| LPM / SecNumCloud | Édition Sovereign | An 2 |
| Référentiel BCE (banques) | Audit-ready | An 2 |
| EU AI Act | Conformité native | v1 |

## 3. Authentification — couches superposées

**Couche 1 — Identité.** Mot de passe ou SSO (OAuth2/OIDC, SAML 2.0, LDAP). Politique de mot de passe stricte : Argon2id (250 ms calibrés), 12+ caractères, dictionnaires interdits, rotation 90 j pour rôles exécutifs, vérification HIBP optionnelle.

**Couche 2 — MFA.** Obligatoire pour tous les rôles avec accès aux décisions ou aux KPI exécutifs, configurable au tenant. Méthodes : TOTP (RFC 6238), WebAuthn / FIDO2 (recommandé pour les exécutifs), push-approval sur app mobile, codes de récupération à usage unique (10).

**Couche 3 — Session.** Tokens JWT RS256 signés par clé privée stockée en Vault (rotation tous les 90 j). Access 15 min, refresh 7 j en cookie HttpOnly Secure SameSite=Strict. Rotation à chaque refresh. Blacklist côté serveur. Sessions visibles côté utilisateur (`Settings > Sessions`), révocables individuellement.

**Couche 4 — Contexte.** Géolocalisation MaxMind, device fingerprint, anomaly score. Une connexion depuis un nouveau pays déclenche un re-MFA et une notification email. Les exfiltrations massives (> 100 reqs/min, > 500 docs ouverts en 5 min) sont stoppées et un agent risque est alerté.

**Couche 5 — Anti brute-force.** `django-axes` + Redis lock : 5 échecs → blocage IP 15 min, 10 échecs → blocage compte (déblocage admin), captcha progressif après 3 échecs.

## 4. Autorisation — RBAC + ABAC

Le détail est dans [`13_rbac.md`](13_rbac.md). En résumé :

**RBAC** : `User` ↔ `Role` (par `Organization`) ↔ `Permission` (par convention `app:resource:action`). Permissions standard (`decisions:decision:view`, `decisions:decision:vote`) et permissions composées (`codir:executive_dashboard`).

**ABAC** : par-dessus, des **policies** filtrent les querysets par attributs : direction, statut, sensibilité, période. Implémentées comme classes Python testables.

**Permissions explicites par défaut** : aucun accès implicite. Si une permission n'est pas explicitement accordée, elle est refusée. L'écran d'administration affiche un diff des permissions modifiées et exige une justification au-delà de seuils sensibles.

## 5. Chiffrement

**En transit.** TLS 1.3 partout, configurations Mozilla *Modern*. HSTS (`max-age=31536000; includeSubDomains; preload`). Certificate pinning côté mobile (release builds). mTLS pour les communications entre workers Celery et le broker.

**Au repos.**
- Base PostgreSQL : volumes chiffrés au niveau OS (LUKS / dm-crypt) + champs sensibles (PII, contenus de PV, données financières atomiques) chiffrés au niveau ligne par `pgcrypto` avec clés gérées par Vault.
- Stockage objet MinIO/S3 : SSE-KMS, clés tenant-scopées rotatives.
- Redis : `requirepass` fort + chiffrement TLS, données non sensibles uniquement (cache, queues, ws).
- Backups : chiffrement avant transit (age + GPG), stockés en région différente, clés gérées dans un HSM séparé du cluster opérationnel.

**Gestion des secrets.** HashiCorp Vault (ou AWS Secrets Manager / Azure Key Vault selon le cloud). Aucun secret en clair dans le code, dans `.env`, ou dans les images Docker. Rotation automatique des secrets dynamiques (DB credentials, JWT keys) sous 90 j.

## 6. Audit trail

Voir [`03_architecture_backend.md`](03_architecture_backend.md) §8. Quelques principes clés :

- Une table `audit_logs.AuditEntry` recevoir chaque action significative.
- Chaque entrée est **signée** (HMAC-SHA-256) avec une clé tenant-scoped pour détecter toute altération.
- Les entrées sont **chained** (champ `previous_hash`) pour former une chaîne d'intégrité type blockchain interne ; la rupture d'une chaîne est un signal de compromission.
- L'export d'audit est disponible aux auditeurs (RBAC `audit_logs:export`) au format CSV signé + PDF horodaté RFC 3161 (TSA externe).
- Rétention : 5 ans par défaut (configurable), archivage à froid après 1 an.

## 7. Protection OWASP Top 10

| Risque OWASP | Contre-mesure |
|---|---|
| A01 Broken Access Control | RBAC + ABAC, default-deny, tests automatiques cross-tenant |
| A02 Cryptographic Failures | TLS 1.3, Argon2id, pgcrypto, KMS |
| A03 Injection | ORM Django, paramètres préparés, validation DRF schemas |
| A04 Insecure Design | Threat modeling formel par feature, revues sécurité |
| A05 Security Misconfiguration | Hardening images Docker, scans Trivy, CIS benchmarks |
| A06 Vulnerable Components | Dependabot, snyk, mise à jour automatique critiques |
| A07 Identification & Auth Failures | MFA, lockout, anomaly detection, password policy |
| A08 Software & Data Integrity | Signature images, SBOM, CodeQL, signed audit log |
| A09 Security Logging Failures | Logs JSON structurés, Loki, SIEM-ready, SOC alerting |
| A10 SSRF | Whitelist domaines sortants, network policies K8s |

## 8. Sécurité des dépendances et chaîne logiciel

**SBOM** (Software Bill of Materials) généré à chaque build au format CycloneDX. Stocké et versionné. Permet de répondre en < 4 h à une vulnérabilité divulguée (type Log4Shell).

**Signature** des images Docker avec Cosign (Sigstore), vérifiée à l'admission Kubernetes via Kyverno. Aucune image non signée ne s'exécute en production.

**Scans**:
- SAST: Semgrep + Bandit (Python) en pre-commit et CI.
- DAST: OWASP ZAP en CI nightly contre l'env staging.
- Container scan: Trivy en CI + à l'admission registry.
- Secret scan: gitleaks, repo-wide, pre-receive hook.

## 9. Protection des données (RGPD)

CODIR est un sous-traitant (au sens RGPD) de ses clients (responsables de traitement). La DPA (Data Processing Agreement) standard contient :

**Bases légales** identifiées pour chaque catégorie de donnée. Les utilisateurs disposent de leurs droits (accès, rectification, effacement, portabilité, opposition) directement depuis leur compte (`Settings > Privacy`).

**Minimisation** : les exports IA ne contiennent que le strict nécessaire ; les options de zéro-rétention IA sont possibles par tenant.

**Pseudonymisation** automatique des données dans les environnements non-prod (faker scripts au moment de copier un snapshot pour debug).

**Localisation des données** : choix par tenant (UE par défaut, US sur demande, hébergement HDS pour santé en France, on-prem pour Sovereign).

**Sous-traitants** (OpenAI, Anthropic, Whisper API, Sentry, AWS) listés dans la DPA et activables/désactivables par tenant.

## 10. SOC et détection

Un SOC interne (managé ou externalisé) consomme :

- Logs Loki (auth, audit, applicatifs)
- Métriques Prometheus
- Alertes Sentry (erreurs anormales)
- Logs réseau Traefik
- Trace tempo (OTel)

Règles de corrélation : tentatives de login depuis 5+ IPs en 10 min, exfiltration > seuil, accès admin hors heures ouvrées, mutation massive cross-resource. Outil de référence : Wazuh ou ELK SIEM. Astreinte sécurité 24/7 (Enterprise/Sovereign).

## 11. Réponse à incident

Procédure formalisée :

**Phase 1 — Détection** : alerte SIEM ou signalement utilisateur, ticket sécurité ouvert avec délai d'engagement.

**Phase 2 — Confinement** : isolation du compte / tenant compromis, révocation des tokens, blocage IP. Outil de coupe-circuit accessible à l'astreinte sans nécessiter de déploiement.

**Phase 3 — Éradication & forensic** : analyse audit log signé, snapshot des disques, restauration à un état sain à partir des backups testés.

**Phase 4 — Notification** : si fuite avérée concernant des données personnelles, notification CNIL en < 72 h, notification des personnes concernées si risque élevé. Communication client tenant avec timeline détaillée.

**Phase 5 — Post-mortem** sans blâme, partagé en interne et résumé client publié.

Exercices de simulation (Game day) tous les 6 mois.

## 12. Backups et continuité

**Backups DB** : full quotidien + WAL archivé (PITR à la minute, RPO < 5 min). Cible 1 an, archivage à froid au-delà.
**Backups objets** : versionning MinIO + réplication cross-region.
**Restauration testée** mensuellement (RTO cible : 2 h pour Enterprise, 1 h pour Sovereign).

DRP (Disaster Recovery Plan) documenté, exécutable, avec runbooks. Bascule possible vers une région secondaire (en v2 multi-région).

## 13. Sécurité IA spécifique

Voir [`06_architecture_ia.md`](06_architecture_ia.md) §12 et §9. En complément :

- **Prompt injection** : guardrails systématiques sur entrées utilisateurs avant injection dans le LLM.
- **Data leakage cross-tenant** : audit automatisé du RAG (chaque chunk renvoyé vérifié par middleware).
- **Hallucinations sur RAG** : impossible de citer une source qui n'existe pas (le frontend vérifie la cohérence) ; les passages cités sont vérifiables d'un clic.
- **Pas d'entraînement** sur les données tenant (contractuel + technique).

## 14. Pen tests et bug bounty

**Pen test** annuel par cabinet externe accrédité (CVE, CISA), portant sur web, mobile, API, et infrastructure.
**Bug bounty** privé via YesWeHack ou HackerOne dès la fin de la v1, élargi à un programme public la 2e année. Récompenses jusqu'à 25 000 € pour les vulnérabilités critiques sur le tenant.

## 15. Garde-fous fonctionnels

Quelques choix produit servent aussi de garde-fous sécurité :

- **Confirmation explicite** pour les actions destructrices (suppression de décision, export massif, révocation d'accès), avec saisie d'un mot ("CONFIRMER") au-delà d'un seuil.
- **Cool-down** sur les actions sensibles : un admin ne peut pas révoquer plus de 10 utilisateurs en 5 min sans validation à 4 yeux.
- **Validation à 4 yeux** configurable pour certaines opérations (modification du SSO, désactivation de la MFA tenant-wide, changement de fournisseur IA en édition Sovereign).
- **Mode lecture seule global** activable par l'admin en cas de doute (incident, audit) sans déconnecter les utilisateurs.

---

*Suite : [09 — Architecture multi-tenant](09_architecture_multi_tenant.md)*
