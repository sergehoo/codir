# 06 — Architecture IA

## 1. Philosophie : l'IA comme système, pas comme feature

CODIR ne se contente pas d'appeler un LLM çà et là. L'IA est conçue comme un **sous-système à part entière** (`apps/ai_engine`) avec ses propres interfaces, ses propres workers, ses propres datastores. Ce choix garantit la **portabilité** (OpenAI → Ollama → Claude → Mistral sans toucher le reste de l'application), la **traçabilité** (chaque inférence est journalisée avec inputs, outputs, modèle, coût, latence), et la **souveraineté** (les clients en édition Sovereign peuvent désactiver toute sortie vers un fournisseur externe).

## 2. Capacités IA exposées

Le moteur IA expose **12 capacités** à travers une interface unifiée, chacune avec un contrat clair :

| # | Capacité | Trigger | Modèle privilégié | Mode |
|---|---|---|---|---|
| 1 | Transcription audio réunion | live stream | Whisper large-v3 | Streaming |
| 2 | Résumé exécutif d'un texte | sur demande | GPT-4o / Llama 3.3 70B | Batch |
| 3 | Génération PV de réunion | fin de réunion | GPT-4o / Llama 3.3 70B | Batch (pipeline) |
| 4 | Extraction de décisions et actions | post-transcription | Custom prompt + LLM | Batch |
| 5 | Priorisation de l'ordre du jour | préparation CODIR | LLM + règles | Batch |
| 6 | Recherche sémantique documentaire (RAG) | requête utilisateur | Embeddings + LLM | Sync |
| 7 | Q&A exécutif (copilot) | conversation | LLM + RAG + tools | Sync streaming |
| 8 | Détection de risques émergents | quotidien | Pipeline analytique + LLM | Batch |
| 9 | Forecasting de KPI | hebdomadaire | Prophet / NeuralProphet | Batch |
| 10 | Détection d'anomalies | continu | Isolation Forest + LLM explain | Streaming |
| 11 | OCR intelligent (docs scannés) | upload | Tesseract + GPT-4o-vision | Async |
| 12 | Speech-to-text mobile (notes vocales) | sur device + serveur | Whisper distilled | Async |

## 3. Architecture du moteur IA

```
┌─────────────────────────────────────────────────────────────┐
│                    Couche métier (apps)                     │
│  meetings  decisions  documents  kpis  risks  search …      │
└─────────────────────────────┬───────────────────────────────┘
                              │ AIServiceClient (Python)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              apps/ai_engine — façade unifiée                │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Capability dispatcher                                   │ │
│  │  summarize · transcribe · extract · qa · forecast …     │ │
│  └─────────┬────────────────────┬────────────────────┬────┘ │
│            ▼                    ▼                    ▼      │
│   ┌───────────────┐   ┌─────────────────┐   ┌────────────┐  │
│   │ Prompt        │   │ RAG retrieval   │   │ Guardrails │  │
│   │ registry      │   │ (pgvector)      │   │ + safety   │  │
│   └───────┬───────┘   └────────┬────────┘   └─────┬──────┘  │
│           └────────────────────┼──────────────────┘         │
│                                ▼                            │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ Provider adapters (interchangeable)                 │   │
│   │  OpenAIAdapter · OllamaAdapter · AnthropicAdapter   │   │
│   │  WhisperLocalAdapter · GroqAdapter · MistralAdapter │   │
│   └────────────────┬────────────────────────────────────┘   │
└────────────────────┼────────────────────────────────────────┘
                     ▼
        ┌─────────────────────────┐
        │ Cache inference         │
        │ (Redis, 24h, par hash)  │
        └─────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────┐
   │ Datastores IA                        │
   │  PostgreSQL + pgvector (embeddings)  │
   │  S3/MinIO (audio, PDF OCR)           │
   │  Audit log (inferences)              │
   └──────────────────────────────────────┘
```

## 4. Interface unifiée — `AIServiceClient`

Toutes les apps métier consomment l'IA via un seul service :

```python
# apps/ai_engine/services.py
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class InferenceRequest:
    capability: Literal[
        "summarize", "transcribe", "extract_decisions",
        "qa", "rag_search", "forecast", "ocr", "risk_detect"
    ]
    organization_id: str
    user_id: Optional[str]
    inputs: dict
    options: dict = None        # temperature, max_tokens, language, model_hint
    context: dict = None        # meeting_id, decision_id… pour traçabilité

@dataclass
class InferenceResponse:
    output: dict
    model_used: str
    provider: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cached: bool
    confidence: Optional[float]
    citations: list[dict] = None  # pour RAG


class AIService:
    def infer(self, request: InferenceRequest) -> InferenceResponse:
        # 1. guardrails (PII, prompt injection, taille)
        self.guardrails.check_input(request)
        # 2. cache lookup
        cached = self.cache.get(request)
        if cached:
            return cached
        # 3. dispatch
        capability = self.registry.get(request.capability)
        response = capability.execute(request)
        # 4. guardrails sur la sortie
        self.guardrails.check_output(response)
        # 5. journalisation
        self.audit.log(request, response)
        # 6. cache
        self.cache.set(request, response, ttl=3600)
        return response
```

## 5. Provider adapters et routage

Chaque adaptateur implémente le contrat `ProviderAdapter` :

```python
class ProviderAdapter(Protocol):
    def supports(self, capability: str) -> bool: ...
    def estimate_cost(self, request: InferenceRequest) -> float: ...
    def execute(self, request: InferenceRequest) -> InferenceResponse: ...
```

Le **routeur** sélectionne le provider selon trois critères, dans l'ordre :

1. **Politique tenant** (Sovereign → Ollama exclusivement ; Enterprise → OpenAI par défaut)
2. **Capacité disponible** (un provider peut ne pas supporter une capability)
3. **Coût/latence** selon les options de la requête (`fast` → Groq Llama 3.3 ; `quality` → GPT-4o)

Configuration par tenant dans `administration.AIConfiguration` :

```python
{
  "default_provider": "openai",
  "providers": {
    "openai": {"api_key_ref": "vault://acme/openai", "models": ["gpt-4o", "gpt-4o-mini"]},
    "ollama": {"endpoint": "http://ollama.acme.internal:11434", "models": ["llama3.3:70b", "mistral:7b"]}
  },
  "capability_overrides": {
    "transcribe": "ollama",
    "qa": "openai"
  },
  "sovereign_mode": false,
  "max_monthly_spend_usd": 5000,
  "data_residency": "eu-west"
}
```

## 6. RAG — Retrieval Augmented Generation

Le RAG est le moteur du copilot exécutif et de la recherche sémantique.

**Indexation.** Tous les documents (uploads, PV générés, comptes rendus de réunion, décisions, notes) passent par un pipeline :

```
Document brut
    │
    ▼
Extraction texte (PyMuPDF, python-docx, OCR Tesseract)
    │
    ▼
Chunking (semantic chunking : 800 tokens, overlap 100)
    │
    ▼
Embedding (text-embedding-3-large 3072d OU multilingual-e5 1024d en Sovereign)
    │
    ▼
Stockage pgvector + métadonnées (organization_id, source_type, source_id, version, lang)
    │
    ▼
Index HNSW (m=16, ef_construction=64)
```

**Retrieval.** Recherche hybride : `pgvector` (sémantique) + `OpenSearch` (BM25 keyword). Fusion par RRF (Reciprocal Rank Fusion). Reranking optionnel par cross-encoder (`bge-reranker-v2-m3`) sur le top-50 → top-8.

**Génération.** Le LLM reçoit le contexte récupéré, le prompt système, et la requête utilisateur. Tous les passages utilisés sont **cités** dans la réponse (les apps front affichent les sources cliquables vers les documents originaux).

**Sécurité du RAG.** Le filtre `WHERE organization_id = current_tenant` est **non négociable** sur chaque requête vector. La fuite cross-tenant via RAG est l'un des risques les plus critiques et chaque appel passe par un guardrail dédié qui vérifie que chaque chunk renvoyé appartient bien au tenant courant.

## 7. Pipeline génération de PV — le scénario phare

C'est la fonctionnalité signature. Voici le pipeline complet :

```
1.  Audio réunion (multi-pistes par locuteur si possible)
        │
        ▼
2.  Diarization (pyannote.audio) → segmentation par locuteur
        │
        ▼
3.  Whisper large-v3 (ou Whisper.cpp en local) → transcription brute
        │
        ▼
4.  Post-traitement linguistique :
       • correction termes métiers (glossaire tenant)
       • ponctuation
       • résolution des références (pronoms → noms)
        │
        ▼
5.  Découpage par item d'ordre du jour (matching sur les sujets de Agenda)
        │
        ▼
6.  Pour chaque item :
       a. Résumé (LLM)
       b. Extraction décisions structurées (LLM JSON mode)
       c. Extraction actions / engagements (LLM JSON mode)
       d. Identification responsables et échéances
        │
        ▼
7.  Assemblage en PV structuré (template tenant) :
       • En-tête (date, présents, excusés, quorum)
       • Synthèse exécutive (≤ 200 mots)
       • Compte rendu par sujet
       • Décisions actées
       • Plans d'action
       • Annexes
        │
        ▼
8.  Rendu Word + PDF (apps/reports)
        │
        ▼
9.  Validation humaine (le secrétaire général approuve / corrige)
        │
        ▼
10. Signature électronique (Yousign, DocuSign, ou interne)
        │
        ▼
11. Diffusion (apps/notifications) + archivage (apps/documents)
```

Performance cible : **< 90 s pour un PV d'une réunion d'une heure**, hors validation humaine.

## 8. Mode réunion live — pipeline streaming

Pendant la réunion, le pipeline tourne en mode streaming WebSocket :

- Le client (mobile ou web de la salle) envoie l'audio par chunks de 5 secondes via WebRTC ou WebSocket.
- Un worker dédié reçoit, transcrit avec Whisper (latence cible : 2 s par chunk), pousse la transcription dans le canal Channels `meeting.<id>.transcript`.
- Un second worker observe la transcription en glissant et chaque minute exécute :
  - extraction de décisions émergentes (push sur canal `meeting.<id>.decisions`)
  - extraction d'actions (push sur canal `meeting.<id>.actions`)
  - mise à jour du résumé live (push sur canal `meeting.<id>.summary`)
- Les clients web et mobile reçoivent et affichent en temps réel.

## 9. Guardrails

Trois couches :

**Entrée :**
- détection de PII non souhaitée (option par tenant)
- détection de prompt injection (heuristiques + classifier dédié)
- limite de taille (rejet > 200k tokens)
- détection de contenu sensible (médical, juridique nominatif) → marquage et journalisation

**Sortie :**
- détection d'hallucinations sur le RAG (le LLM doit citer ; sans citation, on flag)
- vérification factuelle légère (dates, chiffres) par règles
- détection de fuite de prompt système
- filtrage des informations cross-tenant (paranoid mode)

**Politique tenant :**
- liste de termes interdits (configurable)
- politique de rétention des inputs/outputs (par défaut 90 j, configurable)
- politique de zéro-rétention possible (l'inférence ne laisse aucune trace au-delà du log d'usage)

## 10. Évaluation et qualité

Un module `ai_engine.evaluation` exécute en continu :

**Eval sets** propres à chaque capability : 100 à 500 cas annotés manuellement (transcription, génération PV, extraction de décisions). Mesurés sur : exactitude des décisions extraites, F1 sur les responsables, score ROUGE sur les résumés, WER sur la transcription.

**A/B testing** entre modèles : chaque tenant peut être assigné à un bucket pour comparer deux configurations (ex. GPT-4o vs Llama 3.3 70B sur la génération de PV). Les métriques de satisfaction utilisateur (édit distance entre PV généré et PV finalisé par l'humain) sont remontées.

**Boucle de feedback** : chaque PV finalisé devient un exemple d'entraînement. À volume suffisant (1 000+ exemples par tenant), une fine-tune custom peut être proposée (édition Premium).

## 11. Coûts et instrumentation

Chaque inférence est journalisée dans `ai_engine.InferenceLog` : tokens, coût, modèle, latence, capability, tenant, user, success/failure. Un dashboard d'observabilité IA (interne) suit :

- coût mensuel par tenant et par capability
- p50 / p99 de latence par capability
- taux d'échec
- taux de cache hit
- distribution de tokens

Alertes : dépassement budget tenant, dégradation de latence > 50 %, taux d'échec > 2 %.

## 12. Sécurité et conformité

**Aucune donnée tenant n'est jamais utilisée pour entraîner les modèles fournisseurs** (option contractualisée avec OpenAI/Anthropic/etc., et garantie native pour Ollama local).

Pour les éditions Sovereign :
- L'IA tourne 100 % en local (Ollama + Whisper.cpp)
- Aucune sortie réseau vers Internet n'est possible
- Les modèles sont distribués sous forme d'images Docker signées
- Le tenant peut auditer le code du module `ai_engine` (open source partielle)

Conformité **AI Act européen** (entrée en vigueur 2026) : classification des usages, transparence (l'utilisateur sait toujours que l'IA est sollicitée), supervision humaine sur les décisions à fort impact, registre des inférences à risque élevé.

## 13. Roadmap IA

| Trimestre | Capacité |
|---|---|
| T1 v1 | Transcription, résumé, extraction décisions, RAG, copilot Q&A |
| T2 v1 | OCR, forecasting basique KPI, détection anomalies |
| T1 v2 | Détection de risques émergents, recommandations stratégiques |
| T2 v2 | Voice assistant (commandes vocales), IA agentique cross-app |
| T1 v3 | Fine-tune par tenant, benchmarking anonymisé inter-organisations |

---

*Suite : [07 — Architecture temps réel](07_architecture_temps_reel.md)*
