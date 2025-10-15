from dataclasses import dataclass
from typing import List, Dict
from rapidfuzz import fuzz

@dataclass
class Match:
    term: str
    definition: str
    score: float


def map_terms_to_drgs(terms: List[str], drg_definitions: List[str], min_score: int = 70) -> Dict[str, List[Match]]:
    mapping: Dict[str, List[Match]] = {}
    defs = [d for d in drg_definitions if d]
    defs_lower = [d.lower() for d in defs]
    for term in terms:
        term_lower = term.lower()
        candidates: List[Match] = []
        # 1) Direct substring boost
        for original, lower in zip(defs, defs_lower):
            if term_lower in lower:
                candidates.append(Match(term=term, definition=original, score=100.0))
        # 2) Fuzzy scoring across all definitions
        for original in defs:
            s1 = fuzz.WRatio(term, original)
            s2 = fuzz.partial_ratio(term, original)
            s3 = fuzz.token_set_ratio(term, original)
            score = max(s1, s2, s3)
            if score >= min_score:
                candidates.append(Match(term=term, definition=original, score=float(score)))
        # Deduplicate by keeping best score per definition
        best_by_def: Dict[str, float] = {}
        for m in candidates:
            if m.definition not in best_by_def or m.score > best_by_def[m.definition]:
                best_by_def[m.definition] = m.score
        deduped = [Match(term=term, definition=d, score=s) for d, s in best_by_def.items()]
        deduped.sort(key=lambda m: m.score, reverse=True)
        mapping[term] = deduped[:10]
    return mapping
