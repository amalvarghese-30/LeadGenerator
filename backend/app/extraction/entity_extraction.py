"""
Named Entity Recognition using spaCy with regex heuristic fallback.
Extracts Person names, Organizations, and Professional Designations.
Never invents entities — extracts strictly from provided text.
"""
import logging
import re
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# Heuristic patterns for designations
DESIGNATION_PATTERNS = [
    r'\b(?:Founder|Co-Founder|CEO|CTO|COO|CMO|Managing Director|Director|President|Partner|Consultant|Author|Lawyer|Advocate|Doctor|Physician|Surgeon|Coach|Executive Coach|Advisor|Speaker|Public Speaker)\b'
]

class EntityExtractor:
    def __init__(self):
        self.nlp = None
        self.available = False
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
            self.available = True
        except Exception:
            try:
                import spacy
                self.nlp = spacy.blank("en")
                self.available = True
            except Exception:
                logger.info("spaCy not available — using heuristic entity extraction fallback")

    def extract(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract entities.
        Returns: {persons: [], organizations: [], locations: [], designations: []}
        """
        if not text:
            return {"persons": [], "organizations": [], "locations": [], "designations": []}

        sample = text[:15000]

        if self.available and self.nlp:
            try:
                doc = self.nlp(sample)
                persons = []
                orgs = []
                locs = []
                seen_entities = set()

                for ent in doc.ents:
                    key = (ent.label_, ent.text.strip())
                    if key in seen_entities or len(ent.text.strip()) < 2:
                        continue
                    seen_entities.add(key)

                    item = {
                        "text": ent.text.strip(),
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                    }
                    if ent.label_ == "PERSON":
                        # Basic noise filter (numbers, common words)
                        if not any(c.isdigit() for c in ent.text) and " " in ent.text:
                            persons.append(item)
                    elif ent.label_ == "ORG":
                        orgs.append(item)
                    elif ent.label_ in ("GPE", "LOC"):
                        locs.append(item)

                designations = self._extract_designations(sample)

                return {
                    "persons": persons,
                    "organizations": orgs,
                    "locations": locs,
                    "designations": designations,
                }
            except Exception as e:
                logger.debug(f"spaCy execution failed, falling back to heuristics: {e}")

        # Heuristic fallback
        return self._heuristic_extract(sample)

    def _extract_designations(self, text: str) -> List[Dict[str, Any]]:
        found = []
        for pat in DESIGNATION_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                found.append({
                    "text": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                })
        return found

    def _heuristic_extract(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """Rule-based heuristic extraction when NLP model is not loaded."""
        # Find capitalized word pairs following titles or designations
        person_pattern = r'\b(?:Mr\.|Ms\.|Mrs\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
        persons = []
        for m in re.finditer(person_pattern, text):
            persons.append({
                "text": m.group(1),
                "label": "PERSON",
                "start": m.start(),
                "end": m.end(),
            })

        # Look for "Name, CEO of Company" or "Name is a Founder"
        rel_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+),\s+(?:the\s+)?(Founder|CEO|Director|Partner|Managing Director|Author|Lawyer)\b'
        for m in re.finditer(rel_pattern, text):
            name = m.group(1)
            if not any(p["text"] == name for p in persons):
                persons.append({
                    "text": name,
                    "label": "PERSON",
                    "start": m.start(),
                    "end": m.end(),
                })

        return {
            "persons": persons,
            "organizations": [],
            "locations": [],
            "designations": self._extract_designations(text),
        }
