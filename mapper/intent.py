"""Intent classifier — map NL question to a canonical ShapeId.

This file is your responsibility. Read the 15 supported shapes in
`shapes.ShapeId` and `shapes.CANONICAL_CYPHER`, then implement
`detect_shape` so that each of the 15 canonical eval questions in
`data/eval_questions.jsonl` is classified to the gold shape, and
adversarial / off-template questions return None.

The deterministic mapper is the production-discipline arm of M9B; a
classifier that returns the wrong shape on a supported question is a
real bug, and a classifier that returns a confident answer on an
off-template question is the silent-failure mode the Reading warns
against. Prefer None over a false positive.
"""
import re
from .shapes import ShapeId

# KG vocabulary — canonical names exactly as stored in Neo4j
CUISINES = {
    "World", "Asian", "European", "Americas",
    "Chinese", "Japanese", "Indian", "Thai",
    "Sichuan", "Italian", "French", "Spanish",
    "Tuscan", "Sicilian", "Mexican", "NorthAmerican",
}

# Cuisines that use SUBCLASS_OF traversal (non-leaf / broad categories)
HIERARCHICAL_CUISINES = {"World", "Asian", "European", "Americas", "Chinese"}

INGREDIENTS = {
    "ginger", "garlic", "basil", "orange", "turkey", "sage", "salt",
    "pepper", "peppercorn", "szechuan peppercorn", "chili", "tomato",
    "onion", "scallion", "soy sauce", "rice", "rice noodles",
    "wheat noodles", "egg", "chicken", "beef", "pork", "tofu",
    "shrimp", "fish", "lemon", "lime", "cilantro", "parsley", "thyme",
    "rosemary", "oregano", "flour", "butter", "cheese", "cream",
    "milk", "olive oil", "sesame oil", "vinegar",
}

TECHNIQUES = {
    "wok", "braise", "saute", "roast", "grill", "steam",
    "fry", "bake", "boil", "simmer", "smoke", "poach",
}

def _find_cuisine(q: str) -> str | None:
    for c in CUISINES:
        if c.lower() in q:
            return c
    return None


def _find_ingredient(q: str) -> str | None:
    # Longer names first to avoid partial matches (e.g. "szechuan peppercorn" before "peppercorn")
    for ing in sorted(INGREDIENTS, key=len, reverse=True):
        if ing in q:
            return ing
    return None


def _has_ingredient_cue(q: str) -> bool:
    """Only match ingredient shapes when an explicit cue is present."""
    return bool(re.search(r'\b(use[sd]?|using|with)\b', q))
  

def detect_shape(question: str) -> ShapeId | None:
    """Classify the question into one of the 15 ShapeId values, or None.

    Suggested approach: a small set of keyword / regex rules over the
    question text that match the shape vocabulary used by the recipe
    KG. Look for cues such as:
      - "by author <name>", "by <Name>"   → author shapes
      - "<cuisine name>"                  → cuisine shapes
      - "use <ingredient>", "with <ingredient>" → ingredient shapes
      - "but not <ingredient>"            → q14 (negation)
      - "ranked by popularity" / "most popular" → q9
      - "under <N> minutes"               → q10
      - "ingredients used in"             → q11 (inverse)
      - "authors of"                      → q12
      - "or any subtype" / "or any kind"  → q13
      - "optionally tagged"               → q15
      - "require <technique>"             → q7

    For cuisines and ingredients, you can use the schema label vocabulary
    (Cuisine.name values, Ingredient.name values) to disambiguate which
    slot type the question is naming. A spaCy NER pass on PERSON entities
    helps for q2 / q8.

    Returns None when no rule fires — the orchestrator raises
    UnsupportedQueryError in that case, which is the correct behaviour
    for an out-of-scope question.
    """
    # TODO (intent classifier):
    # 1. Lowercase the question for pattern matching.
    # 2. Apply rules in priority order — more-specific shapes (q14
    #    "but not", q8 "by ... that use") before less-specific (q1, q3).
    # 3. Return the matching ShapeId, or None if nothing matches.
    q = question.lower()

    if "optionally tagged" in q:
        return ShapeId.Q15

    if re.search(r'\bbut not\b|\bwithout\b', q) and _has_ingredient_cue(q):
        return ShapeId.Q14

    if re.search(r'or any (subtype|kind)', q):
        return ShapeId.Q13

    if "ingredients used in" in q:
        return ShapeId.Q11

    if "authors of" in q:
        return ShapeId.Q12

    if re.search(r'under \d+ minutes', q):
        return ShapeId.Q10

    if re.search(r'ranked by popularity|most popular', q):
        return ShapeId.Q9

    if re.search(r'\bby (author )?\w', q) and _has_ingredient_cue(q):
        return ShapeId.Q8

    if re.search(r'\bby (author )?\w', q):
        return ShapeId.Q2

    if re.search(r'\brequire[sd]?\b', q):
        return ShapeId.Q7

    cuisine = _find_cuisine(q)
    has_ingredient = _has_ingredient_cue(q) and _find_ingredient(q) is not None

    if cuisine and cuisine in HIERARCHICAL_CUISINES and has_ingredient:
        return ShapeId.Q6

    if cuisine and has_ingredient:
        return ShapeId.Q5

    if cuisine and cuisine in HIERARCHICAL_CUISINES:
        return ShapeId.Q4

    if cuisine:
        return ShapeId.Q3

    if _has_ingredient_cue(q) and _find_ingredient(q) is not None:
        return ShapeId.Q1

    return None
