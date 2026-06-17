"""Slot extraction — fill the named slots a shape's Cypher template needs.

Each shape in `shapes.CANONICAL_CYPHER` carries `$param` placeholders.
Your `extract_slots(question, shape)` returns a dict whose keys are the
parameter names the template expects, e.g.:

  ShapeId.Q1 → {"ingredient": "ginger"}
  ShapeId.Q5 → {"cuisine": "Sichuan", "ingredient": "ginger"}
  ShapeId.Q9 → {"cuisine": "Italian"}
  ShapeId.Q10 → {"max_minutes": 30}
  ShapeId.Q14 → {"ingredient": "ginger", "exclude_ingredient": "garlic"}

See `data/eval_questions.jsonl` for the gold (question_text, shape, slots)
triples used by the autograder.
"""

from .shapes import ShapeId
import re
import spacy

_nlp = None
def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp

CUISINES = [
    "NorthAmerican", "Sichuan", "Sicilian", "Tuscan",
    "Chinese", "Japanese", "Italian", "French", "Spanish",
    "Indian", "Mexican", "Asian", "European", "Americas",
    "Thai", "World",
]

INGREDIENTS = [
    "szechuan peppercorn", "rice noodles", "wheat noodles",
    "olive oil", "sesame oil", "soy sauce",
    "peppercorn", "scallion", "cilantro", "parsley",
    "rosemary", "oregano", "chicken", "shrimp",
    "ginger", "garlic", "basil", "orange", "turkey", "sage",
    "salt", "pepper", "chili", "tomato", "onion",
    "egg", "beef", "pork", "tofu", "fish",
    "lemon", "lime", "thyme", "flour", "butter",
    "cheese", "cream", "milk", "vinegar", "rice",
]

TECHNIQUES = [
    "wok", "braise", "saute", "roast", "grill", "steam",
    "fry", "bake", "boil", "simmer", "smoke", "poach",
]


def _match_cuisine(q: str) -> str | None:
    ql = q.lower()
    # Longer names first to avoid partial matches
    for c in sorted(CUISINES, key=len, reverse=True):
        if c.lower() in ql:
            return c
    return None


def _match_ingredient(q: str) -> str | None:
    ql = q.lower()
    for ing in sorted(INGREDIENTS, key=len, reverse=True):
        if ing in ql:
            return ing
    return None


def _match_technique(q: str) -> str | None:
    ql = q.lower()
    for t in TECHNIQUES:
        if t in ql:
            return t
    return None


def _extract_author(q: str) -> str | None:
    nlp = _get_nlp()
    doc = nlp(q)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    return None

def extract_slots(question: str, shape: ShapeId) -> dict:
    """Extract slot values for the given shape from the question text.

    Suggested approach:
      - spaCy NER for PERSON entities (q2, q8 author slot).
      - A short hand-authored vocabulary list of the cuisines and
        ingredients in the recipe KG — string-match the question against
        it case-insensitively. The lists are small (16 cuisines, 40
        ingredients) so a literal-match approach is fine.
      - For q10: a regex like `under (\\d+)\\s*minutes` to pull the
        integer threshold.
      - For q14: split the question on "but not" / "without" to get the
        positive and negative ingredient slots.

    Return a dict whose keys EXACTLY match the `$param` names in
    shapes.CANONICAL_CYPHER[shape]. Returning a slot dict missing a
    required parameter will surface as a Neo4j ParameterMissing error
    at query time — that is fail-loud and desired.

    Values must be the canonical form the KG uses (e.g., 'Italian' not
    'italian'; 'ginger' not 'Ginger'). Match against the schema vocabulary
    rather than echoing the surface form of the question.
    """
    # TODO (slot extraction):
    # 1. For the given shape, list the parameter names you need to fill.
    # 2. For each parameter, use a vocabulary list or a regex over the
    #    question text to extract the value in canonical form.
    # 3. Return the dict.
    q = question

    if shape == ShapeId.Q1:
        return {"ingredient": _match_ingredient(q)}

    if shape == ShapeId.Q2:
        return {"author": _extract_author(q)}

    if shape == ShapeId.Q3:
        return {"cuisine": _match_cuisine(q)}

    if shape == ShapeId.Q4:
        return {"cuisine": _match_cuisine(q)}

    if shape == ShapeId.Q5:
        return {"cuisine": _match_cuisine(q), "ingredient": _match_ingredient(q)}

    if shape == ShapeId.Q6:
        return {"cuisine": _match_cuisine(q), "ingredient": _match_ingredient(q)}

    if shape == ShapeId.Q7:
        return {"technique": _match_technique(q)}

    if shape == ShapeId.Q8:
        return {"author": _extract_author(q), "ingredient": _match_ingredient(q)}

    if shape == ShapeId.Q9:
        return {"cuisine": _match_cuisine(q)}

    if shape == ShapeId.Q10:
        m = re.search(r'under (\d+)\s*minutes', q, re.IGNORECASE)
        return {"max_minutes": int(m.group(1)) if m else None}

    if shape == ShapeId.Q11:
        return {"cuisine": _match_cuisine(q)}

    if shape == ShapeId.Q12:
        return {"cuisine": _match_cuisine(q)}

    if shape == ShapeId.Q13:
        return {"ingredient": _match_ingredient(q)}

    if shape == ShapeId.Q14:
        # Split on "but not" or "without"
        parts = re.split(r'\bbut not\b|\bwithout\b', q.lower(), maxsplit=1)
        positive = _match_ingredient(parts[0]) if len(parts) > 0 else None
        negative = _match_ingredient(parts[1]) if len(parts) > 1 else None
        return {"ingredient": positive, "exclude_ingredient": negative}

    if shape == ShapeId.Q15:
        return {"technique": _match_technique(q)}

    return {}