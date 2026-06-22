"""Service d'embedding — sentence-transformers local (gratuit, multilingue).

Modèle : `paraphrase-multilingual-MiniLM-L12-v2`
  - 384 dimensions
  - Multilingue (50+ langues dont FR)
  - ~117 MB sur disque, ~400 MB en RAM
  - Inférence ~10ms par texte court (CPU)

Pourquoi local plutôt qu'OpenAI/Voyage :
  - Zéro frais récurrent (vs 0.02-0.06$ / M tokens chez les providers)
  - Données ne quittent jamais l'infra (RGPD/confidentialité)
  - Qualité ~80% d'ada-002 sur du français — largement suffisant pour
    une recherche dans des CR de comité, décisions, plans.
  - Latence prédictible, pas de quota ni rate limit.

Lazy loading :
  - Le modèle est chargé au PREMIER appel d'embedding (pas à l'import) pour
    ne pas pénaliser le boot de Django.
  - Une fois chargé, il reste en mémoire (singleton) pour toute la durée
    du process.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
MODEL_VERSION_TAG = "minilm-multi-v1"
EMBEDDING_DIM = 384

# Cache writable : par défaut sentence-transformers + huggingface_hub écrivent
# dans ~/.cache, mais en conteneur prod le home est read-only. On force un
# dossier writable (idéalement un volume Docker, sinon /tmp).
# `setdefault` : on respecte une valeur explicite via .env si l'opérateur la
# fournit, sinon fallback /tmp/.cache/huggingface.
_HF_CACHE = os.environ.setdefault(
    "HF_HOME", os.environ.get("HF_HOME") or "/tmp/.cache/huggingface",
)
os.environ.setdefault("TRANSFORMERS_CACHE", _HF_CACHE)
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", _HF_CACHE)
try:
    os.makedirs(_HF_CACHE, exist_ok=True)
except OSError:
    pass  # si même /tmp est ro, le load échouera proprement via _LOAD_FAILED

# Sentinel pour distinguer "pas encore tenté" (None) de "tenté et échoué".
# Un objet dédié plutôt que `False` pour éviter le piège du falsy test sur le
# singleton (un `False` matche `_model is not None` et était retourné comme
# modèle valide → AttributeError au .encode()).
_LOAD_FAILED = object()
_model = None  # type: ignore[assignment]
_model_lock = threading.Lock()


def _load_model():
    """Lazy load du modèle. Retourne None si sentence-transformers indispo ou
    si le chargement a échoué précédemment (mémorisé, pas de retry tight loop)."""
    global _model
    if _model is _LOAD_FAILED:
        return None
    if _model is not None:
        return _model
    with _model_lock:
        if _model is _LOAD_FAILED:
            return None
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(
                "Loading embedding model %s (one-time, may take 30-60s)… "
                "cache=%s", MODEL_NAME, _HF_CACHE,
            )
            _model = SentenceTransformer(MODEL_NAME, cache_folder=_HF_CACHE)
            logger.info("Embedding model loaded.")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers. "
                "Semantic search will be disabled."
            )
            _model = _LOAD_FAILED
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load embedding model: %s", exc)
            _model = _LOAD_FAILED
    return _model if _model is not _LOAD_FAILED else None


def reset_model_cache():
    """Réinitialise le singleton pour permettre un retry du load (debug/tests)."""
    global _model
    with _model_lock:
        _model = None


def embed_text(text: str) -> Optional[list[float]]:
    """Embed un texte en vecteur 384-dim. Retourne None si embedding indispo."""
    if not text or not text.strip():
        return None
    model = _load_model()
    if model is None:
        return None
    try:
        # normalize_embeddings=True → vecteurs unit-norm pour cosine direct
        vec = model.encode(text[:8000], normalize_embeddings=True, show_progress_bar=False)
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)
    except Exception as exc:  # noqa: BLE001
        logger.exception("embed_text failed: %s", exc)
        return None


def embed_texts(texts: list[str]) -> list[Optional[list[float]]]:
    """Embed en batch — beaucoup plus rapide que N appels individuels."""
    if not texts:
        return []
    model = _load_model()
    if model is None:
        return [None] * len(texts)
    try:
        truncated = [(t or "")[:8000] for t in texts]
        vecs = model.encode(truncated, normalize_embeddings=True,
                            batch_size=32, show_progress_bar=False)
        return [v.tolist() if hasattr(v, "tolist") else list(v) for v in vecs]
    except Exception as exc:  # noqa: BLE001
        logger.exception("embed_texts failed: %s", exc)
        return [None] * len(texts)


def text_hash(text: str) -> str:
    """Hash sha256 stable pour détecter les textes inchangés (skip ré-index)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity entre 2 vecteurs. Si déjà normalisés (cas ici), c'est
    juste le produit scalaire — très rapide."""
    if not a or not b or len(a) != len(b):
        return 0.0
    # Vecteurs normalisés (normalize_embeddings=True) → dot product = cosine
    return sum(x * y for x, y in zip(a, b))


def is_available() -> bool:
    """True si le service est utilisable (modèle disponible)."""
    return _load_model() is not None
