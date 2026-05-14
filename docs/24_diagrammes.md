# 24 — Diagrammes architecture, UML, séquence

> Tous les diagrammes utilisent la syntaxe **Mermaid**, rendue nativement par GitHub, GitLab, Notion, Obsidian et tout viewer Markdown moderne.

## 1. Vue d'ensemble — architecture C4 niveau Contexte

```mermaid
flowchart TB
    DG[👤 Directeur Général]
    DAF[👤 DAF / DRH / DSI]
    Sec[👤 Secrétaire général]
    Aud[👤 Auditeur / Compliance]

    CODIR[("CODIR — Executive OS<br/>SaaS multi-tenant")]

    SAP[(SAP / Sage / Odoo)]
    M365[(Microsoft 365<br/>Google Workspace)]
    Visio[(Teams / Zoom / Meet)]
    PBI[(Power BI / Tableau)]
    WA[(WhatsApp Business)]
    Sign[(Yousign / DocuSign)]
    AI[(OpenAI / Anthropic<br/>Ollama local)]

    DG --> CODIR
    DAF --> CODIR
    Sec --> CODIR
    Aud --> CODIR

    CODIR <--> SAP
    CODIR <--> M365
    CODIR <--> Visio
    CODIR <--> PBI
    CODIR --> WA
    CODIR <--> Sign
    CODIR <--> AI
```

## 2. Architecture C4 niveau Conteneurs

```mermaid
flowchart TB
    subgraph Clients
        Web[Web React/TS<br/>Vite + Tanstack]
        Mob[Mobile Flutter<br/>iOS + Android]
        ThirdParty[Partenaires<br/>API REST]
    end

    Edge[Traefik<br/>TLS, WAF, rate-limit]

    subgraph Backend Django
        API[Django HTTP API<br/>Gunicorn + DRF]
        ASGI[Django Channels<br/>Daphne ASGI]
        WHK[Webhook Gateway<br/>FastAPI]
    end

    subgraph Workers Celery
        CDef[Worker default]
        CAI[Worker AI<br/>GPU possible]
        CRep[Worker reports]
        CInt[Worker integrations]
        CBeat[Celery Beat<br/>scheduler]
    end

    subgraph Data
        PG[(PostgreSQL 16<br/>+ pgvector)]
        RD[(Redis 7<br/>cache + broker + channels)]
        OS[(OpenSearch)]
        S3[(MinIO / S3)]
    end

    subgraph IA
        Ollama[Ollama local<br/>Llama 3.3 / Whisper]
        OpenAI[OpenAI API]
    end

    Clients --> Edge
    Edge --> API
    Edge --> ASGI
    Edge --> WHK

    API --> PG
    API --> RD
    API --> OS
    API --> S3
    ASGI --> RD
    WHK --> API

    API --> CDef
    API --> CAI
    API --> CRep
    API --> CInt
    CBeat --> CDef
    CBeat --> CRep

    CAI --> Ollama
    CAI --> OpenAI
    CAI --> PG
    CRep --> S3
```

## 3. Modèle de données — vue partielle (Decision lifecycle)

```mermaid
erDiagram
    ORGANIZATION ||--o{ MEETING : has
    ORGANIZATION ||--o{ DIRECTION : has
    ORGANIZATION ||--o{ USER_MEMBERSHIP : grants
    USER ||--o{ USER_MEMBERSHIP : holds
    DIRECTION ||--o{ POSITION : groups
    POSITION }o--|| USER : held_by

    MEETING ||--|| AGENDA : has
    AGENDA ||--o{ AGENDA_ITEM : contains
    AGENDA_ITEM ||--o{ DECISION : produces
    MEETING ||--o{ PARTICIPATION : registers
    MEETING ||--o{ VOTE : casts
    MEETING ||--o{ TRANSCRIPT_CHUNK : transcribed_to

    DECISION }|--|| DIRECTION : responsible_of
    DECISION ||--o{ DECISION_VOTE : aggregated_from
    DECISION ||--o{ ACTION_PLAN : produces
    ACTION_PLAN ||--o{ ACTION_TASK : contains
    ACTION_TASK ||--o{ ACTION_EVIDENCE : proven_by
    DECISION }|..|{ RISK : linked_to
    DECISION }|..|{ KPI : impacts

    DECISION {
        uuid id PK
        string ref
        string title
        string status
        decimal budget_amount
        date deadline
    }

    ACTION_TASK {
        uuid id PK
        string title
        string status
        date due_date
        int progress_percent
    }
```

## 4. Séquence — Tenir une décision en réunion live

```mermaid
sequenceDiagram
    actor Chair as Chairman
    actor Mem as Membres CODIR
    participant Web
    participant API as Django API
    participant WS as Channels
    participant Svc as DecisionService
    participant DB as PostgreSQL
    participant AI

    Chair->>Web: Clic "Ouvrir vote"
    Web->>API: POST /decisions/{id}/transitions/open_vote
    API->>Svc: open_vote(decision, chairman)
    Svc->>DB: UPDATE decision SET status='open_for_vote'
    Svc->>WS: publish_event(meeting, "decision.vote_opened")
    WS-->>Mem: Push: vote ouvert (web + mobile)
    Mem->>Web: Vote OUI / NON / ABSTENTION
    Web->>WS: vote.cast
    WS->>Svc: cast_vote(decision, voter, choice)
    Svc->>DB: INSERT Vote
    Svc->>WS: decision.vote.tally (agrégé)
    WS-->>Mem: Tally en temps réel
    WS-->>Chair: Tally en temps réel
    Chair->>Web: Clic "Clôturer vote"
    Web->>API: POST /decisions/{id}/transitions/close_vote
    API->>Svc: close_vote()
    Svc->>DB: UPDATE decision SET status='vote_closed', vote_summary=...
    Svc->>AI: suggest_action_plan(decision)
    AI-->>Svc: ActionPlan draft
    Svc->>DB: CREATE ActionPlan + Tasks
    Svc->>WS: action_plan.drafted
    WS-->>Mem: "Plan d'action proposé"
```

## 5. Séquence — Génération automatique du PV par IA

```mermaid
sequenceDiagram
    participant Meet as Meeting end
    participant Q as Celery (queue ai)
    participant W1 as Whisper Worker
    participant W2 as LLM Worker
    participant DB
    participant S3 as MinIO
    participant Sec as Secrétaire général
    participant Mail as Notifications

    Meet->>Q: end_meeting(meeting_id) → trigger pv_pipeline
    Q->>S3: GET audio
    Q->>W1: diarize + transcribe
    W1-->>Q: transcript chunks (~20s/min audio)
    Q->>DB: persist transcript
    Q->>W2: enrich + summarize per agenda item
    W2-->>Q: summaries + decisions + actions structured
    Q->>DB: persist decisions / actions
    Q->>W2: render PV (template)
    W2-->>Q: docx + pdf
    Q->>S3: store outputs
    Q->>DB: minutes_doc + status=ready_for_review
    Q->>Mail: notify(Sec) "PV prêt à valider"
    Sec->>DB: review + corrections
    Sec->>Q: transition approve
    Q->>Mail: diffuser aux participants
```

## 6. Séquence — Authentification SSO + MFA

```mermaid
sequenceDiagram
    actor User
    participant Web
    participant API
    participant IdP as Microsoft Entra ID
    participant MFA as TOTP/WebAuthn

    User->>Web: Cliquer "SSO Microsoft"
    Web->>API: GET /auth/sso/microsoft/
    API->>IdP: Redirect OIDC authorize
    IdP-->>User: Login Microsoft
    User->>IdP: Auth Microsoft
    IdP-->>Web: Callback avec code
    Web->>API: GET /auth/sso/microsoft/callback?code=
    API->>IdP: Exchange code → tokens
    IdP-->>API: id_token + access_token
    API->>API: Match user.email, check tenant SSO config
    alt MFA requis (rôle exécutif)
        API-->>Web: 403 mfa_required + challenge
        Web->>User: Demande TOTP / WebAuthn
        User->>MFA: TOTP code / biométrie
        MFA-->>Web: response
        Web->>API: POST /auth/mfa/ {response}
    end
    API-->>Web: JWT access + refresh (cookie)
    Web->>API: GET /me/
    API-->>Web: User profile + perms
```

## 7. Séquence — Détection KPI breach + analyse IA

```mermaid
sequenceDiagram
    participant Beat as Celery Beat
    participant Calc as KPICalculator
    participant DB
    participant Eng as ThresholdEngine
    participant AI
    participant WS
    participant Mail

    Beat->>Calc: recalculate_kpis_hourly
    Calc->>DB: aggregate data per kpi
    Calc->>DB: insert KPISnapshot
    Calc->>Eng: evaluate thresholds
    alt Threshold breached
        Eng->>DB: insert KPIAlert
        Eng->>AI: analyze_root_cause(kpi, snapshot, related)
        AI-->>Eng: explanation + recommendations
        Eng->>WS: publish kpi.alert
        WS-->>Web: dashboard live update
        Eng->>Mail: dispatch email + push to recipients
    end
```

## 8. Diagramme de classes — Workflow engine

```mermaid
classDiagram
    class WorkflowDefinition {
        +UUID id
        +str code
        +str name
        +int version
        +JSON spec
        +ContentType target_type
    }
    class WorkflowInstance {
        +UUID id
        +WorkflowDefinition definition
        +ContentType target_type
        +UUID target_id
        +str current_state
        +JSON context
    }
    class WorkflowTransition {
        +UUID id
        +WorkflowInstance instance
        +str from_state
        +str to_state
        +User actor
        +str comment
        +datetime occurred_at
    }
    class WorkflowService {
        +available_transitions(user)
        +transition(code, user, comment)
        -find_transition(code)
        -user_can(user, t)
        -condition_ok(t, user)
        -run_side_effect(name)
    }
    WorkflowInstance --> WorkflowDefinition
    WorkflowInstance --> WorkflowTransition
    WorkflowService ..> WorkflowInstance
```

## 9. Cycle de vie d'une décision (machine d'état)

```mermaid
stateDiagram-v2
    [*] --> proposed
    proposed --> open_for_vote: open_vote
    open_for_vote --> vote_closed: close_vote
    vote_closed --> approved: approve
    vote_closed --> rejected: reject
    approved --> in_progress: start
    in_progress --> blocked: block
    blocked --> in_progress: unblock
    in_progress --> completed: complete (preuve)
    proposed --> cancelled: cancel
    open_for_vote --> cancelled: cancel
    approved --> cancelled: cancel
    rejected --> [*]
    completed --> [*]
    cancelled --> [*]
```

## 10. Architecture WebSocket

```mermaid
flowchart LR
    subgraph Browsers
        B1[Browser A]
        B2[Browser B]
        B3[Mobile]
    end

    LB[Traefik<br/>WSS]

    subgraph ASGI Cluster
        A1[Daphne worker #1]
        A2[Daphne worker #2]
        A3[Daphne worker #3]
    end

    Redis[(Redis pub/sub<br/>+ groups buffer)]

    subgraph Producers
        Sig[Django signals]
        Cel[Celery workers]
        Svc[Services métier]
    end

    B1 --> LB
    B2 --> LB
    B3 --> LB
    LB --> A1
    LB --> A2
    LB --> A3
    A1 <--> Redis
    A2 <--> Redis
    A3 <--> Redis
    Sig --> Redis
    Cel --> Redis
    Svc --> Redis
```

## 11. Pipeline IA (RAG + Copilot)

```mermaid
flowchart LR
    Q[Question utilisateur] --> Pre[Pré-traitement<br/>+ contexte tenant]
    Pre --> Emb[Embedding requête]
    Emb --> VS[Recherche vectorielle<br/>pgvector HNSW]
    Pre --> KW[Recherche keyword<br/>OpenSearch BM25]
    VS --> RRF[Fusion RRF]
    KW --> RRF
    RRF --> Rer[Reranker<br/>bge-reranker]
    Rer --> Top[Top-K passages]
    Top --> Build[Build prompt<br/>+ glossaire tenant]
    Build --> Guard[Guardrails entrée]
    Guard --> LLM[LLM<br/>OpenAI / Ollama]
    LLM --> Stream[SSE streaming]
    Stream --> Out[Sortie + citations]
    Out --> GuardOut[Guardrails sortie]
    GuardOut --> Audit[Log inference]
    GuardOut --> User[Réponse utilisateur]
```

## 12. Topologie de déploiement Kubernetes

```mermaid
flowchart TB
    subgraph Edge
        T[Traefik IngressController]
    end

    subgraph Namespace codir-app
        H1[django-api x N pods]
        H2[django-ws x N pods]
        H3[webhook-gateway x M]
    end

    subgraph Namespace codir-workers
        W1[celery-default]
        W2[celery-ai GPU]
        W3[celery-reports]
        W4[celery-integrations]
        W5[celery-beat]
    end

    subgraph Namespace codir-data
        PG1[(Postgres primary)]
        PG2[(Postgres replica)]
        R1[(Redis cluster)]
        OS1[(OpenSearch cluster)]
    end

    subgraph Namespace codir-storage
        S3[(MinIO)]
    end

    subgraph Namespace codir-obs
        Pro[Prometheus]
        Grf[Grafana]
        Lok[Loki]
        Sen[Sentry]
    end

    T --> H1
    T --> H2
    T --> H3
    H1 --> PG1
    H1 --> R1
    H1 --> OS1
    H1 --> S3
    H2 --> R1
    W1 --> PG1
    W2 --> PG1
    W2 --> S3
    W3 --> S3
    W4 --> PG1
    Pro --> H1
    Pro --> H2
    Pro --> W1
    Pro --> W2
    Lok --> H1
    Lok --> H2
```

## 13. Gantt — Roadmap haut niveau

```mermaid
gantt
    title Roadmap CODIR — 24 mois
    dateFormat YYYY-MM-DD
    axisFormat %b-%Y

    section Foundation
    Setup infra & DevOps           :done,  inf, 2026-01-01, 30d
    Auth + Multi-tenant + RBAC     :done,  auth, 2026-01-15, 45d
    Audit trail + Sécurité         :active, sec, 2026-02-15, 30d

    section v1 MVP
    Réunions + Agendas             :v1a, 2026-03-01, 60d
    Décisions + Plans d'action     :v1b, after v1a, 60d
    IA Transcription + PV          :v1c, 2026-04-01, 90d
    KPI + Dashboards (4 personas)  :v1d, 2026-04-15, 75d
    Documents + Search             :v1e, 2026-05-01, 60d
    Mobile Flutter (consultation)  :v1f, 2026-05-15, 75d
    Notifications multicanal       :v1g, 2026-06-01, 45d
    Beta clients pilotes           :milestone, 2026-09-01, 0d
    Release v1.0                   :milestone, 2026-12-01, 0d

    section v2 Premium
    Budgets + Scénarios            :v2a, 2026-12-01, 90d
    Risques avancés + ESG          :v2b, 2027-02-01, 90d
    Signatures électroniques       :v2c, 2027-03-01, 60d
    Connecteurs ERP / BI           :v2d, 2027-01-15, 120d
    IA décisionnelle prédictive    :v2e, 2027-03-01, 120d
    Release v2.0                   :milestone, 2027-08-01, 0d
```

---

*Suite : [25 — Features premium](25_features_premium.md)*
