# 14 — Workflows métiers

## 1. Pourquoi un moteur de workflow ?

CODIR formalise plusieurs **processus métiers** où la même structure se répète : une entité change d'état, des conditions doivent être réunies pour passer d'un état à un autre, des actions automatiques s'enclenchent à chaque transition (notification, génération de tâche, audit log). Plutôt que de coder chaque processus en dur dans chaque app, CODIR utilise un **moteur de workflow générique** (`apps/workflows`) :

- définition déclarative (JSON) d'une machine d'état
- attachement à n'importe quelle entité (`GenericForeignKey`)
- hooks pre/post-transition (Python callables)
- conditions évaluées (DSL léger : expression Python sandboxée)
- traçabilité complète (qui, quand, depuis quel état, vers quel état, commentaire)

Le moteur est inspiré de `django-fsm` et de `viewflow.fsm`, mais simplifié et explicitement multi-tenant.

## 2. Workflows fournis nativement

### 2.1. Workflow d'une décision (`decision_lifecycle`)

```
       ┌──────────┐
       │ proposed │
       └────┬─────┘
            │ open_vote (auth: chairman OR secretary)
            ▼
       ┌──────────────────┐
       │ open_for_vote    │◄──┐ vote_cast (auth: voter)
       └────┬─────────────┘   │
            │ close_vote      │
            ▼                 │
     ┌─────────────────┐      │
     │ vote_closed     │──────┘
     └──┬─────────┬────┘
        │ approve  │ reject (auth: chairman)
        ▼          ▼
   ┌────────┐ ┌─────────┐
   │approved│ │rejected │
   └───┬────┘ └─────────┘
       │ start (auth: responsible)
       ▼
   ┌─────────────┐  block      ┌─────────┐
   │ in_progress │────────────►│ blocked │
   └───────┬─────┘ ◄────unblock└─────────┘
           │ complete (preuve requise)
           ▼
        ┌──────────┐
        │ completed│
        └──────────┘
```

### 2.2. Workflow d'une tâche de plan d'action (`task_lifecycle`)

```
todo → in_progress → review → done
                  ↘ blocked ↗
```

### 2.3. Workflow PV de réunion (`minutes_lifecycle`)

```
not_started → draft_generated (IA) → reviewed (humain) → approved (chairman) → signed → archived
                                  ↘ rejected → revising → ...
```

### 2.4. Workflow signature électronique (`signature_lifecycle`)

```
requested → sent_to_signer_1 → signed_1 → sent_to_signer_2 → signed_2 → ... → completed
                                                                       ↘ declined → cancelled
```

### 2.5. Workflow budget (`budget_validation`)

```
draft → controller_review → cfo_review → board_review → approved
                                                      ↘ rejected → revising → ...
```

### 2.6. Workflow risque (`risk_lifecycle`)

```
identified → assessed → mitigation_planned → mitigating → mitigated → closed
                                                       ↘ realized (became incident)
```

### 2.7. Workflow génération de PV (`pv_pipeline`)

Plus un *pipeline* qu'un *workflow* utilisateur — orchestré par Celery — mais journalisé identiquement :

```
audio_captured → diarized → transcribed → enriched → summarized → 
   structured (decisions/actions extracted) → rendered (docx/pdf) → 
   pending_review → ready_for_signature
```

## 3. Modèle Django du moteur de workflow

```python
# apps/workflows/models.py
class WorkflowDefinition(TenantAwareModel):
    code = models.SlugField()                          # decision_lifecycle, task_lifecycle…
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    spec = models.JSONField()                          # définition DAG
    target_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [("organization", "code", "version")]

class WorkflowInstance(TenantAwareModel):
    definition = models.ForeignKey(WorkflowDefinition, on_delete=models.PROTECT)
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.UUIDField()
    target = GenericForeignKey("target_content_type", "target_id")
    current_state = models.CharField(max_length=50)
    context = models.JSONField(default=dict)           # variables additionnelles

class WorkflowTransition(TenantAwareModel):
    instance = models.ForeignKey(WorkflowInstance, on_delete=models.CASCADE, related_name="transitions")
    from_state = models.CharField(max_length=50)
    to_state = models.CharField(max_length=50)
    actor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)
```

## 4. Format de définition (spec JSON)

```json
{
  "code": "decision_lifecycle",
  "initial_state": "proposed",
  "states": [
    {"code": "proposed", "label": "Proposée"},
    {"code": "open_for_vote", "label": "Ouverte au vote"},
    {"code": "vote_closed", "label": "Vote clos"},
    {"code": "approved", "label": "Approuvée"},
    {"code": "rejected", "label": "Rejetée", "terminal": true},
    {"code": "in_progress", "label": "En exécution"},
    {"code": "blocked", "label": "Bloquée"},
    {"code": "completed", "label": "Réalisée", "terminal": true},
    {"code": "cancelled", "label": "Annulée", "terminal": true}
  ],
  "transitions": [
    {
      "code": "open_vote",
      "from": ["proposed"],
      "to": "open_for_vote",
      "permissions": ["decisions:decision:open_vote"],
      "condition": "target.meeting.status == 'in_progress'",
      "side_effects": ["notify_voters", "publish_ws_event"]
    },
    {
      "code": "approve",
      "from": ["vote_closed"],
      "to": "approved",
      "permissions": ["decisions:decision:approve"],
      "condition": "target.vote_summary['yes'] > target.vote_summary['no']",
      "side_effects": ["create_action_plan_draft", "notify_responsible", "publish_ws_event"]
    },
    {
      "code": "complete",
      "from": ["in_progress"],
      "to": "completed",
      "permissions": ["decisions:decision:complete"],
      "condition": "target.evidence_set.exists()",
      "side_effects": ["update_kpi_execution_rate", "notify_stakeholders"]
    }
  ]
}
```

## 5. Service `WorkflowService`

```python
# apps/workflows/services.py
class WorkflowService:
    def __init__(self, instance: WorkflowInstance):
        self.instance = instance
        self.spec = instance.definition.spec

    def available_transitions(self, user) -> list[dict]:
        return [
            t for t in self.spec["transitions"]
            if self.instance.current_state in t["from"]
            and self._user_can(user, t)
            and self._condition_ok(t, user)
        ]

    @transaction.atomic
    def transition(self, code: str, user, comment: str = "", metadata: dict = None):
        t = self._find_transition(code)
        if self.instance.current_state not in t["from"]:
            raise WorkflowError("invalid_state")
        if not self._user_can(user, t):
            raise PermissionDenied(f"missing_permission:{t['permissions'][0]}")
        if not self._condition_ok(t, user):
            raise WorkflowError("condition_failed")
        from_state = self.instance.current_state
        self.instance.current_state = t["to"]
        self.instance.save(update_fields=["current_state", "updated_at"])
        log = WorkflowTransition.objects.create(
            instance=self.instance, from_state=from_state, to_state=t["to"],
            actor=user, comment=comment, metadata=metadata or {},
        )
        for side_effect in t.get("side_effects", []):
            self._run_side_effect(side_effect, user)
        audit.log("workflow.transition", target=self.instance, after={"state": t["to"]})
        return log
```

Les `side_effects` sont des **callables enregistrés** dans un registre global (`workflows.registry`). Ils reçoivent l'instance et le user, et exécutent des actions : créer un brouillon de plan d'action, publier un événement WS, notifier, etc.

## 6. Exemple complet : flux décisionnel CODIR

Voici la séquence concrète, qui implique 6 apps :

```
T0  Réunion en cours, sujet "Lancement Phoenix" affiché.
    Le DG demande un vote.

T1  Le chairman clique "Ouvrir vote"
    → API: POST /decisions/d_98/transitions/open_vote
    → WorkflowService.transition("open_vote", user=chairman)
    → Décision passe à open_for_vote
    → side_effect "notify_voters": tous les membres présents reçoivent une notif WS
    → side_effect "publish_ws_event": le canal meeting.<id> reçoit "decision.vote_opened"
    → Les mobiles vibrent, l'écran affiche "voter maintenant"

T2  Les 11 membres votent (web ou mobile)
    → WS receive: vote.cast par participant
    → Service cast_vote(...) → DB write
    → publish_ws_event decision.vote.cast pour chaque vote
    → publish_ws_event decision.vote.tally agrégé toutes les 500ms

T3  Le chairman clique "Clôturer vote"
    → POST /decisions/d_98/transitions/close_vote
    → vote_summary computed (7 yes, 2 no, 2 abstain)
    → décision passe à vote_closed

T4  Approve (auto si majorité, sinon explicite)
    → side_effect "create_action_plan_draft" 
        → IA propose un plan basé sur la décision + historique similaire
        → Crée ActionPlan + ActionTask[] en statut "todo"
    → side_effect "notify_responsible"
        → Email + push + inapp au responsable de la décision
    → side_effect "update_kpi_pending_decisions"
        → Recalcul du KPI "nombre de décisions ouvertes"

T5  Plus tard : le responsable accepte le plan → workflow task_lifecycle s'enclenche.
```

## 7. Intégration côté API REST

```
GET    /api/v1/decisions/{id}/workflow/         # état + transitions disponibles
POST   /api/v1/decisions/{id}/transitions/{code}/   # déclencher transition
GET    /api/v1/decisions/{id}/transitions/      # historique
```

Idem pour toutes les entités sous workflow (`/tasks/`, `/budgets/`, `/risks/`, `/minutes/`, `/signatures/`).

## 8. Frontend : composant unifié `<WorkflowActions>`

Côté React :

```tsx
function WorkflowActions({ entity, entityType }) {
  const { data } = useQuery({ queryKey: ['workflow', entityType, entity.id], queryFn: ... })
  return (
    <div className="flex gap-2">
      {data.available_transitions.map((t) => (
        <Button
          key={t.code}
          variant={t.style ?? 'default'}
          onClick={() => mutate.mutate({ code: t.code, comment })}
        >
          {t.label}
        </Button>
      ))}
    </div>
  )
}
```

Composant identique réutilisé pour décisions, tâches, budgets, risques.

## 9. Diagramme de séquence (Mermaid)

Voir [`24_diagrammes.md`](24_diagrammes.md) pour la version Mermaid complète des flux décisionnel, génération de PV, signature, et budget.

## 10. Limites assumées

Le moteur n'est pas un BPMN complet. Pas de tâches parallèles automatiques, pas de timers natifs (mais Celery beat peut déclencher des transitions). Pour la v1, c'est suffisant. En v2, on évaluera l'extension vers un sous-ensemble BPMN si les clients enterprise le demandent (workflows multi-acteurs en parallèle, sub-process, etc.).

---

*Suite : [15 — Dashboards](15_dashboards.md)*
