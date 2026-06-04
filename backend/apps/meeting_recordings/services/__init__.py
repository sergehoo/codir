"""Services métier meeting_recordings — pipeline audio → IA → modules cibles.

Chaque module est testable de façon isolée et n'importe pas Celery
(les tâches Celery sont de simples wrappers qui appellent ces services).
"""
from .recording import (  # noqa: F401
    create_recording, update_status, mark_uploaded, mark_failed,
)
from .audio_processing import (  # noqa: F401
    normalize_audio, extract_speaker_sample, get_audio_duration,
)
from .transcription import transcribe_recording  # noqa: F401
from .diarization import (  # noqa: F401
    aggregate_speakers_from_segments, suggest_participants_for_speakers,
)
from .speaker_mapping import (  # noqa: F401
    map_speaker_to_participant, confirm_all_mappings, generate_final_transcript,
)
from .ai_summary import (  # noqa: F401
    generate_summary, extract_decisions, extract_action_items, run_llm_with_fallback,
)
from .extraction import (  # noqa: F401
    push_decision_to_module, push_action_plan_to_module,
)
from .export import (  # noqa: F401
    generate_minutes_docx, generate_minutes_pdf,
)
