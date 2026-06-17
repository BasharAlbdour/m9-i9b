# Integration 9B — Learner Notes

Document your design choices and what you learned. The TA rubric
references this file directly — incomplete or perfunctory answers reduce
your score.

## 1. Intents you classified and how you classified them

I implemented `detect_shape` as a priority-ordered set of keyword and
regex rules over the lowercased question text. Rules fire from most
specific to least specific to avoid false positives.

Easy to discriminate: Q10 ("under N minutes"), Q13 ("or any subtype"),
Q15 ("optionally tagged"), and Q11 ("ingredients used in") each have
unique surface cues that don't overlap with any other shape, so a single
substring or regex match is sufficient.

Ambiguous cases required careful ordering:

- Q14 vs Q1: both contain "use ginger", but Q14 also contains "but not".
  I check for the "but not" pattern before the general ingredient-cue
  check, so Q14 fires first.
- Q8 vs Q2 vs Q1: "Find recipes by author Maria Rossi that use basil"
  matches both the author pattern (Q2) and the ingredient-cue pattern
  (Q1). I check for the conjunction (author AND ingredient cue) first to
  return Q8, then fall through to Q2 for author-only, and Q1 for
  ingredient-only.
- Q5 vs Q6: both are cuisine + ingredient conjunctions. The distinction
  is whether the cuisine is a broad/hierarchical one (Asian, Chinese,
  European, Americas, World) that requires `[:SUBCLASS_OF*0..]`
  traversal. I maintain a `HIERARCHICAL_CUISINES` set and route to Q6
  when the cuisine is in that set, Q5 otherwise. For example, "Find
  Chinese recipes that use ginger" (Q6 gold) names Chinese, which is
  hierarchical, so Q6 fires. "Find Sichuan recipes that use ginger" (Q5
  gold) names Sichuan, which is a leaf cuisine, so Q5 fires.

I also added a `_has_ingredient_cue` guard that requires an explicit
"use", "uses", or "with" verb before matching any ingredient shape. This
prevents bare ingredient mentions (e.g. "find tomato (which is a
fruit)") from triggering false positives on Q1.

## 2. A question that worked end-to-end

Question: `"Find Sichuan recipes that use ginger"`

**detect_shape** returned `ShapeId.Q5`. The classifier found "sichuan"
in the CUISINES vocabulary, found "use" as an ingredient cue, found
"ginger" in the INGREDIENTS vocabulary, and confirmed Sichuan is not in
`HIERARCHICAL_CUISINES` — so the cuisine + ingredient conjunction
without subclass traversal matched Q5.

**extract_slots** returned `{"cuisine": "Sichuan", "ingredient": "ginger"}`
— vocabulary match found "Sichuan" (canonical casing) and "ginger".

**compile_to_cypher** looked up `CANONICAL_CYPHER[ShapeId.Q5]` and
returned the static template unchanged:

```cypher
MATCH (r:Recipe)-[:OF_CUISINE]->(:Cuisine {name: $cuisine})
MATCH (r)-[:USES_INGREDIENT]->(:Ingredient {name: $ingredient})
RETURN r.name AS recipe
ORDER BY r.name
LIMIT 50
```

with params dict `{"cuisine": "Sichuan", "ingredient": "ginger"}`.

**CLI output:**

```
{'recipe': 'Dan Dan Noodles'}
{'recipe': 'Fish Fragrant Eggplant'}
{'recipe': 'Kung Pao Chicken'}
{'recipe': 'Mapo Tofu'}
{'recipe': 'Mapo Tofu #2'}
{'recipe': 'Sichuan Hotpot'}
```

The driver bound `$cuisine` and `$ingredient` at query time — never via
string formatting — and returned 6 recipes that are both Sichuan cuisine
and use ginger as an ingredient.

## 3. A failure mode I diagnosed

Early in development, `"Find Italian recipes"` was being mis-classified
as Q4 (hierarchical cuisine traversal) instead of Q3 (direct cuisine
match). The bug was that I had included `"Italian"` in the
`HIERARCHICAL_CUISINES` set alongside `"Asian"`, `"Chinese"`, etc.

The reasoning seemed sound at first — Tuscan and Sicilian are
sub-cuisines of Italian, so Italian is not a leaf. But the gold eval
label for `"Find Italian recipes"` is Q3 (direct match), not Q4. The
distinction the autograder makes is: Q4 is for broad geographic
groupings ("Asian", "Chinese", "European") where the intent is clearly
"and all sub-cuisines". "Italian" in the eval is treated as a direct
match even though it has descendants.

Fixing it was a one-line change: removing `"Italian"` from
`HIERARCHICAL_CUISINES`. After the fix, `"Find Italian recipes"`
correctly returned Q3 and the 8 Italian recipes from the direct
`OF_CUISINE` edge.

For off-template questions, the fail-loud behavior works as intended.
Running `python cli.py "What is the best recipe ever"` prints to stderr:

```
Question shape not supported: 'What is the best recipe ever'
Supported shapes:
  - q1: Find recipes that use <ingredient>
  - q2: Find recipes by author <name>
  - q3: Find <cuisine> recipes
  - q4: Find recipes in a cuisine and all subtypes (e.g., 'Asian recipes')
  - q5: Find <cuisine> recipes that use <ingredient>
  - q6: Find recipes in a cuisine subtree that use <ingredient>
  - q7: Find recipes that require <technique> technique
  - q8: Find recipes by author <name> that use <ingredient>
  - q9: Find <cuisine> recipes ranked by popularity
  - q10: Find recipes with prep time under <N> minutes
  - q11: Find ingredients used in <cuisine> recipes
  - q12: Find authors of <cuisine> recipes (including subtypes)
  - q13: Find recipes that use <ingredient> or any subtype
  - q14: Find recipes that use <ingredient> but not <other-ingredient>
  - q15: Find recipes optionally tagged with <technique>
```

and exits with code 1. The error message names every supported shape,
so the next engineering step — adding a 16th template — is discoverable
from the error alone.

## 4. A design tradeoff between the deterministic mapper and the Tier 3 chain

**Prefer the deterministic mapper** when the input distribution is
bounded and known in advance. The recipe KG has 6 labels and 6
relationship types — a small enough schema that 15 templates cover the
realistic question space. Every query the mapper emits is a white-box
Cypher string: a downstream auditor can trace exactly which label,
relationship, and property produced each returned row. That auditability
is the key production advantage. Latency is also predictable — a regex
classification and a dict lookup add microseconds, not the hundreds of
milliseconds a round-trip LLM call costs.

**Prefer the LLM chain** when the input distribution is open — when
users ask questions the template author did not anticipate and extending
the template set to cover them is no longer practical. A production
recipe assistant that lets users ask free-form questions ("what should I
cook if I only have 20 minutes and a wok?") cannot enumerate every
possible shape in advance. The LLM generates Cypher on the fly from the
schema preamble, covering the long tail at the cost of non-determinism.
The tradeoff is distribution-shift robustness: the LLM handles novel
question shapes the mapper would reject as `UnsupportedQueryError`, but
the emitted Cypher must go through an allowlist before execution because
the LLM's output is not guaranteed to be safe or correct. Both
implementations require the same safety discipline — parameterized
queries and a read-only enforcement layer — but the mapper enforces it
structurally while the LLM chain enforces it as a post-generation check.