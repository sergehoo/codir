# 22 — Stratégie IA

## 1. Positionnement

L'IA est **le facteur différenciant majeur** de CODIR. Trois convictions guident la stratégie :

**L'IA n'est pas une fonctionnalité, c'est une couche transversale.** Elle s'invite dans la préparation (ordre du jour suggéré, agrégation de contexte), pendant la réunion (transcription, extraction live), après (PV, plan d'action, suivi, alertes risques). Si on isolait l'IA dans une "tab IA", on serait un produit comme les autres.

**La confiance prime sur la performance.** Mieux vaut un PV à 92 % d'exactitude que l'utilisateur valide en 10 min, qu'un PV à 98 % généré par un système opaque. Toute sortie IA doit être inspectable, source citée, modifiable, et journalisée.

**La souveraineté est une fonctionnalité.** Pour 30-40 % du marché cible (banques, défense, santé publique, services régaliens), une plateforme qui ne tourne qu'avec OpenAI est inacceptable. CODIR maintient une parité de capacités IA entre OpenAI/Anthropic d'un côté, et Ollama local de l'autre.

## 2. Stack IA opérationnelle

| Capacité | Modèle préféré (Cloud) | Modèle souverain (local) | Fournisseur local |
|---|---|---|---|
| Transcription audio | Whisper large-v3 (OpenAI) | Whisper.cpp large-v3 | Local CPU/GPU |
| Diarization | pyannote.audio 3.x | pyannote.audio 3.x | Local |
| Résumé | GPT-4o, Claude 3.7 Sonnet | Llama 3.3 70B Instruct | Ollama |
| Extraction décisions | GPT-4o (JSON mode) | Llama 3.3 70B / Mistral Large | Ollama |
| Q&A copilot | GPT-4o / Claude | Llama 3.3 70B | Ollama |
| Embedding | text-embedding-3-large | multilingual-e5-large (1024d) | sentence-transformers |
| Reranker | bge-reranker-v2-m3 | idem | Local |
| OCR avancé | GPT-4o-vision | Florence-2 + Tesseract | Local |
| Forecasting | — | Prophet, NeuralProphet | Local |
| Anomaly detection | — | Isolation Forest, ARIMA | Local |

## 3. Architecture IA — résumé

Documenté en détail dans [`06_architecture_ia.md`](06_architecture_ia.md). Points clés :

- Façade unique `AIService` consommée par toutes les apps.
- Routeur de provider selon politique tenant.
- Guardrails entrée/sortie systématiques.
- Cache Redis par hash de requête.
- Journalisation immuable de chaque inférence.

## 4. Prompts — gestion industrielle

Les prompts sont des artefacts produit critiques. Gérés comme du code :

**Registre versionné** : tous les prompts dans `apps/ai_engine/prompts/`, versionnés en yaml :

```yaml
# apps/ai_engine/prompts/extract_decisions.yaml
code: extract_decisions
version: 5
description: Extrait les décisions actées d'une transcription
languages: [fr, en]
capabilities: [extract_decisions]
inputs:
  transcript: str
  agenda_items: list
  context: dict
system: |
  Tu es un secrétaire général expérimenté. Tu analyses la transcription
  d'une réunion CODIR pour identifier les décisions formellement actées.

  Une décision est :
  - une déclaration explicite d'action validée ("Nous lançons X", "Décidé que Y")
  - un vote formel approuvé
  - une orientation stratégique entérinée

  Une décision n'est PAS :
  - une discussion ouverte sans conclusion
  - une suggestion non actée
  - un constat factuel
user: |
  Transcription :
  {{ transcript }}

  Ordre du jour :
  {{ agenda_items | format_items }}

  Contexte tenant :
  - Glossaire : {{ context.glossary }}
  - Style de l'entreprise : {{ context.style_guide }}

  Réponds en JSON avec un objet `decisions` (array d'objets décisions structurées).
output_schema:
  $ref: schemas/decision_extracted.json
examples:
  - input: ...
    expected: ...
```

**Évaluation continue** : un eval set de 500 transcriptions annotées (validées par humain) est rejoué à chaque modification de prompt. Métriques : précision, rappel, F1 sur les décisions extraites.

**Promotion** : un prompt v(n+1) ne remplace v(n) que si l'eval améliore ou est neutre. Sinon, rollback. Tests automatiques en CI.

## 5. Pipeline génération PV — qualité

C'est la **fonctionnalité signature**. La qualité se mesure par :
- **Exactitude des décisions** (couverture × précision) > 92 %.
- **Distance d'édition** entre PV généré et PV finalisé par humain < 15 % des tokens.
- **Temps de relecture** par le secrétaire général < 15 min pour 1h de réunion.

Trois leviers de qualité :

**Diarization fiable** — qui a dit quoi est crucial. Pyannote 3.x donne ~92 % d'exactitude sur 4 locuteurs. On combine avec les flux audio séparés par participant quand disponibles (Teams/Zoom font ça nativement) pour atteindre 99 %+.

**Glossaire tenant** — chaque organisation a son jargon. Le glossaire (noms internes, sigles, projets, personnes) est injecté dans le prompt à chaque inférence. On rebrancht ce glossaire au fur et à mesure que les utilisateurs corrigent les PV (apprentissage léger sans fine-tune).

**Validation humaine structurée** — l'écran de revue facilite la correction : chaque décision extraite est cliquable, surligne le passage source de la transcription, propose de l'éditer en place. Les corrections nourrissent l'eval set.

## 6. Copilote conversationnel exécutif

Le copilote est accessible depuis toutes les pages via un drawer side panel. Il a :

**Contexte automatique** — la page courante (décision, dashboard, PV) est passée dans le contexte ; pas besoin d'expliquer.

**Tool use** — il peut appeler des "outils" : interroger les KPI (`get_kpi`), chercher des décisions (`search_decisions`), demander une analyse de risque (`analyze_risk`), résumer un document (`summarize_doc`). Implémentation OpenAI function calling / Llama tools.

**Mémoire de conversation** — historique 50 derniers messages, persistance pour reprendre plus tard.

**Citations systématiques** — chaque affirmation pointe vers une source cliquable (document, décision, KPI snapshot).

Exemples de questions typiques :

- *« Quelles décisions concernent la DSI ce trimestre ? »* → tool `search_decisions` filtré, réponse listée avec liens.
- *« Pourquoi le KPI trésorerie a-t-il chuté de 8 % en avril ? »* → tool `get_kpi` + `analyze_anomaly`, croisement avec décisions et incidents récents.
- *« Prépare-moi une note de 3 lignes pour ouvrir le CODIR de demain. »* → résumé contextuel des sujets à l'agenda + alertes du jour.
- *« Quelle est la position du groupe sur le projet Phoenix en 2 paragraphes ? »* → recherche sémantique multi-documents + synthèse.

## 7. Gouvernance et politique IA par tenant

L'admin tenant configure :

- Fournisseur(s) autorisé(s) : OpenAI, Anthropic, Ollama, Mistral…
- Capacités activées par défaut (transcription oui, copilote non, etc.).
- Budget mensuel max (alerte 80 %, blocage 100 %).
- Politique de rétention des prompts/réponses (0 / 30 / 90 / 365 jours).
- Mode "supervision humaine" obligatoire pour certaines capacités à fort impact (forecasting, recommandations stratégiques).
- Blocklist de termes interdits (compliance).
- Allowlist de modèles autorisés.

## 8. AI Act et conformité

L'AI Act européen classe certains usages d'IA. CODIR adopte par défaut le niveau de classification le plus exigeant pour les capacités à fort impact (recommandations stratégiques) :

- **Transparence** : l'utilisateur sait toujours quand une sortie est produite par IA (badge "IA" visible).
- **Supervision humaine** : aucune décision automatique ; l'IA propose, l'humain valide.
- **Robustesse** : redondance de providers, fallback en cas d'indisponibilité, dégradation gracieuse.
- **Traçabilité** : registre des inférences à risque (`AIInferenceLog` + champ `risk_class`).
- **Évaluation** : eval sets internes documentés et exécutables par les auditeurs.

## 9. Confidentialité

CODIR garantit contractuellement :
- Aucune donnée tenant utilisée pour entraîner les modèles fournisseurs (clauses OpenAI Enterprise, Anthropic Enterprise, etc.).
- Mode "zéro rétention" possible (l'inférence ne laisse aucune trace au-delà du log d'usage agrégé).
- Édition Sovereign : 0 sortie réseau Internet, modèles 100 % locaux.
- Pseudonymisation optionnelle avant envoi à un LLM externe.

## 10. Coûts IA — projection

Hypothèse moyenne par tenant Enterprise (1 réunion CODIR hebdo, 50 utilisateurs, usage copilote raisonnable) :

| Capacité | Volume mois | Coût unitaire | Coût mois |
|---|---|---|---|
| Transcription (Whisper) | 4 × 90 min = 360 min | $0.006/min | $2,16 |
| Génération PV (GPT-4o) | 4 PV × ~50k tokens | $5 / $15 / 1M tokens | $3,00 |
| Embeddings RAG | 5 000 chunks | $0.13 / 1M tokens | $0,50 |
| Copilote Q&A (GPT-4o) | 200 conv × ~3k tokens | $5 / $15 / 1M tokens | $5,00 |
| Forecasting / anomalies | local | — | $0 |
| **Total cloud** | | | **~ $11 / tenant / mois** |

C'est très accessible. Le coût Sovereign est uniquement infra (Ollama tourne sur le matériel client). On garde une **marge brute IA > 80 %** sur la pricing standard.

## 11. Évaluation continue

Quatre métriques observées en permanence :

**Qualité** — eval sets internes pour chaque capacité, score F1, ROUGE, exactitude. Run nightly.

**Coût** — par tenant, par capacité. Budget alerts.

**Latence** — p50, p95, p99 par capacité. SLOs définis (transcription chunk < 2s, copilote first token < 1s).

**Satisfaction** — thumbs up/down sur chaque sortie copilote, distance d'édition sur PV, NPS qualitatif IA semestriel.

## 12. Stratégie de fine-tuning

À volume suffisant (1 000+ PV finalisés par tenant), proposition d'un fine-tune custom (option premium) :
- Llama 3.3 70B LoRA fine-tune sur les corrections du tenant
- Hébergé sur l'infra Ollama du tenant ou un namespace dédié
- Évaluation comparée vs base model : gain attendu 5-10 % d'exactitude

Pas avant la v2 (recul nécessaire).

## 13. R&D — pistes explorées

- **Multimodal** : analyse de slides PowerPoint partagées en réunion, OCR de schémas, captation de tableau blanc.
- **Voice assistant** : commandes vocales depuis le mobile ("Quel est le KPI X ce mois ?").
- **Agents** : LangGraph pour orchestrer plusieurs IA et apps ("Prépare le CODIR du 15", "Suis le déploiement de la décision Y et alerte si retard").
- **Représentation graphique automatique** : à partir d'une discussion sur un sujet, générer le bon visuel (org chart, timeline, matrice) plutôt que du texte.
- **Mémoire long terme** : un copilote qui se souvient des préférences et formats d'un dirigeant à travers les sessions.

---

*Suite : [23 — Intégrations](23_integrations.md)*
