"""
Extracteur PDF — Relevé de Conclusions CODIR (Kaydan).

Lit un PDF de CR CODIR (format Kaydan KRE) avec ``pdfplumber`` et
retourne un dict canonique :

    {
        "reference":    "CODIR KRE-11-05-2026-SP",
        "date":         date(2026, 5, 11),
        "title":        "RELEVE DE CONCLUSIONS DU COMITE DE DIRECTION DE KAYDAN REAL ESTATE",
        "chair":        "Stéphane AFFRO",
        "rapporteur":   "Patrick SORHO",
        "agenda_items": ["Suivi des projets par Direction"],
        "participants": [
            {"name": "Stéphane AFFRO", "role": "Directeur Général", "entity": "KAYDAN RE", "status": "present"},
            ...
            {"name": "Constant KOUASSI", "role": "Directeur Technique", "entity": "KAYDAN RE", "status": "absent"},
        ],
        "actions": [
            {
                "direction": "Direction administrative et financière",
                "project":   "Business Reviews",
                "action":    "Préparer les business reviews de KRE & ses filiales.",
                "assignees": ["Ette KOUAKOU", "Marietou COULIBALY", "Christian YAO"],
                "deadline":  date(2026, 5, 18),
                "status":    "Non démarré",
                "comment":   "Les Business Review se tiendront du 18/05 au 22/05/2026",
            },
            ...
        ],
    }

Sans état Django ici : c'est pur parsing, testable.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pdfplumber

# ─── Mapping mois français → numéro ─────────────────────────────────────
_FR_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}

# ─── Pattern référence ──────────────────────────────────────────────────
_RE_REF = re.compile(r"(CODIR\s+[A-Z]{2,5}-\d{1,2}-\d{1,2}-\d{4}(?:-\w+)?)", re.I)

# ─── Pattern date format "11 mai 2026" ──────────────────────────────────
_RE_FR_DATE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(_FR_MONTHS.keys()) + r")\s+(\d{4})",
    re.I,
)

# ─── Pattern date format "18/05/2026" ───────────────────────────────────
_RE_SLASH_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

# ─── Pattern ligne participant ──────────────────────────────────────────
# Ex : "- Stéphane AFFRO / Directeur Général / KAYDAN RE"
_RE_PARTICIPANT = re.compile(
    r"^[-•]\s*(?P<name>[^/]+?)\s*/\s*(?P<role>[^/]+?)\s*/\s*(?P<entity>[^/]+?)\s*$"
)

# ─── Status PDF → label canonique (gardé tel quel — mapping CODIR ailleurs) ──
_STATUS_NORM = {
    "non démarré": "Non démarré",
    "non demarre": "Non démarré",
    "en cours": "En cours",
    "en attente": "En attente",
    "en retard": "En retard",
    "terminé": "Terminé",
    "termine": "Terminé",
    "fait": "Terminé",
}


def _flatten(cell: str | None) -> str:
    """Remplace `\\n` par espace + trim + collapse spaces.

    Cas particulier : `Pierre-\\nMichel` (mot coupé par tiret en fin de ligne) →
    `Pierre-Michel` (sans espace). Idem pour `Jean-\\nBernard`.
    """
    if not cell:
        return ""
    # 1. Recolle les coupes "mot-<EOL>mot" → "mot-mot"
    s = re.sub(r"-\s*\n\s*", "-", cell)
    # 2. Remplace les autres \n par espace
    s = s.replace("\n", " ")
    # 3. Collapse spaces
    return re.sub(r"\s+", " ", s).strip()


def _parse_fr_date(text: str) -> date | None:
    """11 mai 2026 → date(2026, 5, 11)."""
    if not text:
        return None
    m = _RE_FR_DATE.search(text)
    if m:
        d, mo, y = int(m.group(1)), _FR_MONTHS[m.group(2).lower()], int(m.group(3))
        return date(y, mo, d)
    return None


def _parse_slash_date(text: str) -> date | None:
    """18/05/2026 → date(2026, 5, 18). Tolère un slash en début (ex: "/05/2026")."""
    if not text:
        return None
    text = _flatten(text)
    # Cas d'erreur OCR/PDF : "/05/2026" → on suppose le mois courant manquant
    m = _RE_SLASH_DATE.search(text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _split_assignees(raw: str) -> list[str]:
    """'Ette\\nKOUAKOU, Marietou\\nCOULIBALY' → ['Ette KOUAKOU', 'Marietou COULIBALY']."""
    flat = _flatten(raw)
    if not flat:
        return []
    parts = re.split(r"[,;]|\s+et\s+", flat, flags=re.I)
    return [p.strip() for p in parts if p.strip()]


def _norm_status(raw: str) -> str:
    # Vire les caractères non-alphabétiques en fin (ex: "En cours24" → "En cours")
    cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\s]+$", "", _flatten(raw)).strip()
    flat = cleaned.lower()
    return _STATUS_NORM.get(flat, cleaned or "Non démarré")


# ─── Extraction header (page 1) ────────────────────────────────────────

def _extract_header(pdf_or_text) -> dict[str, Any]:
    """Accepte soit un texte (str) soit un objet pdfplumber.PDF pour pouvoir
    lire les bbox quand la mise en page est multi-colonnes.
    """
    # Référence + date marchent toujours sur le texte global
    if isinstance(pdf_or_text, str):
        text = pdf_or_text
        first_page = None
    else:
        first_page = pdf_or_text.pages[0]
        text = first_page.extract_text() or ""

    ref = None
    m = _RE_REF.search(text)
    if m:
        ref = m.group(1).strip()

    meeting_date = _parse_fr_date(text)

    # ── Présidence / Rapporteur ──
    # Stratégie : la colonne de droite est physiquement à droite (x > 0.7 * width)
    # de la page 1. On extrait les mots de cette zone et on reconstruit le texte.
    chair = rapporteur = None
    if first_page is not None:
        page_w = first_page.width
        right_words = [
            w for w in first_page.extract_words(use_text_flow=True)
            if w["x0"] > page_w * 0.55
        ]
        # Trier par ligne (top) puis x0
        right_words.sort(key=lambda w: (round(w["top"]), w["x0"]))
        # Grouper par ligne
        lines_right: list[list[dict]] = []
        for w in right_words:
            if lines_right and abs(w["top"] - lines_right[-1][-1]["top"]) < 3:
                lines_right[-1].append(w)
            else:
                lines_right.append([w])
        text_lines_right = [
            " ".join(w["text"] for w in line) for line in lines_right
        ]
        # Chercher "Présidence du CODIR :" → valeur = ligne suivante
        for i, line in enumerate(text_lines_right):
            low = line.lower()
            if "présidence du codir" in low or "presidence du codir" in low:
                after = line.split(":", 1)[-1].strip()
                chair = after or (text_lines_right[i + 1].strip()
                                  if i + 1 < len(text_lines_right) else None)
            elif "rapporteur" in low:
                after = line.split(":", 1)[-1].strip()
                rapporteur = after or (text_lines_right[i + 1].strip()
                                       if i + 1 < len(text_lines_right) else None)

    # Fallback texte si bbox n'a rien donné
    if not chair:
        m = re.search(r"Présidence du CODIR\s*:?\s*([A-ZÉÈÀÙa-zéèàù\-\s]+?)(?=\s*Rapporteur|\n)", text, re.I)
        if m:
            chair = m.group(1).strip()
    if not rapporteur:
        m = re.search(r"Rapporteur\s*:?\s*([A-ZÉÈÀÙa-zéèàù\-\s]+?)(?=\s*Nb pages|\n)", text, re.I)
        if m:
            rapporteur = m.group(1).strip()

    # Ordre du jour — capturer toutes les lignes commençant par "•" ou "-"
    # qui suivent "Ordre du jour :"
    agenda: list[str] = []
    in_agenda = False
    lines = [l.strip() for l in text.splitlines()]
    for line in lines:
        low = line.lower()
        if low.startswith("ordre du jour"):
            in_agenda = True
            continue
        if in_agenda:
            if not line:
                continue
            if line.startswith(("•", "-", "*")):
                item = line.lstrip("•-* ").strip()
                if item:
                    agenda.append(item)
            else:
                # On stoppe dès qu'on quitte la zone agenda
                if any(c.isalpha() for c in line) and line != line.upper():
                    break

    # Titre
    title = "Relevé de conclusions CODIR"
    m_title = re.search(r"RELEVE.*COMITE DE DIRECTION.*$", text, re.I | re.M)
    if m_title:
        title = m_title.group(0).strip().title()
        # Garder "CODIR" en majuscules
        title = re.sub(r"\bcodir\b", "CODIR", title, flags=re.I)

    return {
        "reference": ref,
        "date": meeting_date,
        "title": title,
        "chair": chair,
        "rapporteur": rapporteur,
        "agenda_items": agenda,
    }


_ENTITY_NOISE = re.compile(
    r"\s*(Présidence du CODIR|Rapporteur|Nb pages|Diffusion)\s*:?.*$",
    re.I,
)
# Pattern personne (Prénom NOM en majuscules) collée en fin de cellule
_TRAILING_NAME = re.compile(r"\s+[A-ZÉÈÀÙ][a-zéèàù\-]+\s+[A-ZÉÈÀÙ]{2,}.*$")


def _clean_entity(raw: str) -> str:
    """Retire les résidus de la colonne de droite collés à la cellule entité."""
    clean = _ENTITY_NOISE.sub("", raw).strip()
    clean = _TRAILING_NAME.sub("", clean).strip()
    return clean


def _extract_participants(text: str) -> list[dict]:
    """Parse les sections 'Présents :' et 'Absents :'."""
    out: list[dict] = []
    mode = None  # "present" | "absent"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        low = line.lower()
        if low.startswith("présents") or low.startswith("presents"):
            mode = "present"
            continue
        if low.startswith("absents"):
            mode = "absent"
            continue
        if low.startswith("ordre du jour"):
            mode = None
            continue
        if not mode or not line:
            continue
        # Tolère que la ligne soit collée à des infos de présidence
        m = _RE_PARTICIPANT.match(line)
        if m:
            out.append({
                "name": m.group("name").strip(),
                "role": m.group("role").strip(),
                "entity": _clean_entity(m.group("entity")),
                "status": mode,
            })
    return out


# ─── Extraction actions (pages 2..N) ───────────────────────────────────

# En-têtes attendus en première ligne du tableau (variantes possibles).
_HEADER_TOKENS = {"directions", "projet", "actions", "responsables", "deadline", "etat", "état", "commentaires"}


def _is_header_row(row: list[str | None]) -> bool:
    if not row:
        return False
    flat = " ".join((c or "").lower() for c in row)
    matches = sum(1 for tok in _HEADER_TOKENS if tok in flat)
    return matches >= 4


_NOISE_TOKENS = (
    "présents :", "presents :", "absents :", "ordre du jour",
    "relevé de conclusions", "releve de conclusions",
    "présidence du codir", "presidence du codir",
    "rapporteur", "nb pages", "diffusion",
    "tous les membres", "kaydan real estate",
)


def _is_noise_row(cells: list[str]) -> bool:
    """Détecte les lignes parasitées par le header (page 1)."""
    blob = " ".join(cells).lower()
    return any(tok in blob for tok in _NOISE_TOKENS)


def _extract_actions(pdf: pdfplumber.PDF) -> list[dict]:
    actions: list[dict] = []
    current_direction = ""
    # Skip page 1 (toujours du header) — actions à partir de la page 2
    for page in pdf.pages[1:]:
        for table in page.extract_tables() or []:
            for row in table:
                if not row or all(not (c or "").strip() for c in row):
                    continue
                if _is_header_row(row):
                    continue

                # Le tableau a 7 colonnes attendues. Si une colonne est splittée
                # par pdfplumber on prend les 7 premières et on flatten.
                cells = [_flatten(c) for c in row[:7]]
                while len(cells) < 7:
                    cells.append("")

                if _is_noise_row(cells):
                    continue

                direction, project, action, assignees, deadline, status, comment = cells

                if direction:
                    current_direction = direction
                if not project and not action:
                    continue
                # Une vraie action doit avoir une description
                if not action.strip():
                    continue

                # Détection ligne-continuation : project commence en minuscule
                # → fusionner dans la précédente
                if (
                    project
                    and project[0].islower()
                    and actions
                    and not deadline
                ):
                    prev = actions[-1]
                    prev["project"] = f"{prev['project']} {project}".strip()
                    if action:
                        prev["action"] = f"{prev['action']} {action}".strip()
                    continue

                actions.append({
                    "direction": current_direction,
                    "project": project,
                    "action": action,
                    "assignees": _split_assignees(assignees),
                    "deadline": _parse_slash_date(deadline),
                    "status": _norm_status(status),
                    "comment": comment,
                })
    return actions


# ─── API publique ───────────────────────────────────────────────────────

def extract_codir_pdf(pdf_path: str | Path) -> dict[str, Any]:
    """Lit un PDF CR CODIR et renvoie le dict canonique.

    Raises:
        FileNotFoundError: PDF inexistant.
        ValueError: structure inattendue (pas de référence trouvée).
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF introuvable: {pdf_path}")

    with pdfplumber.open(str(path)) as pdf:
        head_text = pdf.pages[0].extract_text() or ""
        header = _extract_header(pdf)
        participants = _extract_participants(head_text)
        actions = _extract_actions(pdf)

    if not header["reference"]:
        # Fallback dur : on construit une référence à partir de la date
        if header["date"]:
            header["reference"] = f"CODIR-{header['date']:%Y%m%d}"
        else:
            raise ValueError("Impossible d'extraire la référence du CODIR.")

    return {
        **header,
        "participants": participants,
        "actions": actions,
    }


# ─── Démo en CLI ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python codir_pdf_extractor.py <path.pdf>")
        sys.exit(1)

    data = extract_codir_pdf(sys.argv[1])
    print(json.dumps(data, default=str, ensure_ascii=False, indent=2))
