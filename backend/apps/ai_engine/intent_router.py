"""IntentRouter — détecte quels context_loaders activer pour un message user.

Stratégie :
  - Matching keyword-based (rapide, déterministe, débuggable).
  - Le baseline_summary est TOUJOURS inclus pour donner les chiffres clés.
  - Chaque intent ajoute 1+ loaders supplémentaires.
  - Si rien ne matche, on garde juste le baseline + le scope page (ex: si on
    est sur une page meeting, on charge le contexte meeting).

Évolutions possibles (Phase 3) :
  - Embedding + similarity search au lieu de keywords
  - Classification LLM légère (Haiku) avant le call principal
  - Tools Anthropic natifs
"""
from __future__ import annotations

import re
from typing import Iterable


# Patterns regex insensibles à la casse. Ordre important : on évalue tous.
# Chaque match ajoute un ou plusieurs loaders.
INTENT_PATTERNS = [
    # ── Mes tâches personnelles ──
    (
        re.compile(
            r"\b(mes\s+t[âa]ches|mes\s+actions|ce\s+que\s+j[e']?\s*ai\s+[aà]\s+faire"
            r"|todo|to\s*do|mon\s+travail|mon\s+suivi)\b",
            re.IGNORECASE,
        ),
        ["my_tasks"],
    ),
    # ── Tâches en retard (toute l'org) ──
    (
        re.compile(
            r"\b(en\s+retard|overdue|retards?|d[ée]pass[ée]es?|p[ée]rim[ée]es?)\b",
            re.IGNORECASE,
        ),
        ["overdue_tasks", "my_tasks"],
    ),
    # ── Décisions à valider ──
    (
        re.compile(
            r"\b(d[ée]cisions?|[àa]\s+valider|en\s+attente"
            r"|proposed|proposit[io]ns?)\b",
            re.IGNORECASE,
        ),
        ["pending_decisions"],
    ),
    # ── Réunions ──
    (
        re.compile(
            r"\b(r[ée]unions?|meetings?|comit[ée]s?|s[ée]ances?|comex"
            r"|codir|prochaines?|[aà]\s+venir)\b",
            re.IGNORECASE,
        ),
        ["upcoming_meetings"],
    ),
    # ── Plans d'action / dossiers ──
    (
        re.compile(
            r"\b(plans?\s+d.action|dossiers?|projets?|chantiers?"
            r"|mes\s+projets?|mes\s+dossiers?)\b",
            re.IGNORECASE,
        ),
        ["my_action_plans"],
    ),
    # ── Briefing / synthèse / journée ──
    (
        re.compile(
            r"\b(briefing|synth[èe]se|r[ée]sum[ée]?|journ[ée]e|jour\b"
            r"|aujourd['\s]?hui|matin|status)\b",
            re.IGNORECASE,
        ),
        ["my_tasks", "overdue_tasks", "pending_decisions", "upcoming_meetings"],
    ),
    # ── Priorités / urgences ──
    (
        re.compile(
            r"\b(urgent[se]?|prioritaires?|critique[s]?|important[es]?"
            r"|focus|next|prochaines?\s+actions?)\b",
            re.IGNORECASE,
        ),
        ["overdue_tasks", "my_tasks", "pending_decisions"],
    ),
]


def route_message(message: str, *, page_scope: str = "") -> list[str]:
    """Retourne la liste ordonnée et dédupliquée des loaders à exécuter.

    `baseline` est toujours présent en premier (chiffres clés stables).
    Si le user est sur une page donnée (meeting, decision), on adapte.
    """
    chosen: list[str] = ["baseline"]

    # Match keyword
    for pattern, loaders in INTENT_PATTERNS:
        if pattern.search(message):
            for loader in loaders:
                if loader not in chosen:
                    chosen.append(loader)

    # Adaptation par scope page
    if page_scope == "dashboard":
        for loader in ["my_tasks", "upcoming_meetings", "pending_decisions"]:
            if loader not in chosen:
                chosen.append(loader)

    return chosen
