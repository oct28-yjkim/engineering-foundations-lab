"""Deterministic teaching models, NOT OpenSearch/Lucene execution or a benchmark.

Python 3.10+; standard library only; no file writes, network, subprocess or keys.
Visibility is modeled independently of durability. Scores and ranked lists are
explicit fixtures, not a reproduction of Lucene statistics or ANN retrieval.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
import re
from typing import Mapping, Sequence


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def positive_int(value: int, name: str) -> None:
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"{name} must be a positive integer")


def finite_number(value: float, name: str) -> None:
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            f"{name} must be numeric")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    require(finite, f"{name} must be finite and float-representable")


def identifier(value: str, name: str = "id") -> None:
    require(isinstance(value, str) and bool(value), f"{name} must be nonempty text")


def tokenize(text: str) -> tuple[str, ...]:
    """Lowercase then ASCII [a-z0-9]+; no stemming, stopwords or synonyms."""
    require(isinstance(text, str), "text must be a string")
    return tuple(re.findall(r"[a-z0-9]+", text.lower()))


def positions(text: str) -> dict[str, tuple[int, ...]]:
    result: dict[str, list[int]] = {}
    for offset, token in enumerate(tokenize(text)):
        result.setdefault(token, []).append(offset)
    return {token: tuple(offsets) for token, offsets in result.items()}


def tokenized_corpus(corpus: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    require(isinstance(corpus, Mapping), "corpus must be a mapping")
    result = {}
    for doc_id, text in corpus.items():
        identifier(doc_id)
        result[doc_id] = tokenize(text)
    return result


def document_frequency(corpus: Mapping[str, str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for tokens in tokenized_corpus(corpus).values():
        counts.update(set(tokens))
    return dict(sorted(counts.items()))


def bm25(corpus: Mapping[str, str], query: str, k1: float = 1.2,
         b: float = 0.75) -> list[tuple[str, float]]:
    """Illustrative BM25; distinct query terms; omit zero-score documents.

    idf=ln(1+(N-df+0.5)/(df+0.5)); each contribution is
    idf * tf*(k1+1)/(tf+k1*(1-b+b*dl/avgdl)). IDs break score ties.
    Empty documents count in N and average length. This is our explicit corpus
    convention, not a claim about Lucene's per-field docCount or encoded norms.
    """
    finite_number(k1, "k1")
    finite_number(b, "b")
    require(k1 > 0, "k1 must be positive")
    require(0 <= b <= 1, "b must be in [0, 1]")
    docs = tokenized_corpus(corpus)
    terms = sorted(set(tokenize(query)))
    total_tokens = sum(len(tokens) for tokens in docs.values())
    if not docs or not total_tokens or not terms:
        return []
    mean_length = total_tokens / len(docs)
    df = Counter(token for tokens in docs.values() for token in set(tokens))
    scores = []
    for doc_id, tokens in docs.items():
        counts = Counter(tokens)
        contributions = []
        for term in terms:
            frequency = counts[term]
            if not frequency:
                continue
            idf = math.log1p((len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            norm = 1 - b + b * len(tokens) / mean_length
            # Equivalent forms avoid reciprocal overflow for tiny k1 and
            # unnecessary tf*(k1+1) overflow for huge but finite k1.
            if k1 <= 1:
                factor = (1 + k1) / (1 + k1 * (norm / frequency))
            else:
                factor = (1 + 1 / k1) / (1 / k1 + norm / frequency)
            contribution = idf * factor
            require(math.isfinite(contribution), "BM25 arithmetic overflowed")
            contributions.append(contribution)
        score = math.fsum(contributions)
        require(math.isfinite(score), "BM25 score overflowed")
        if score > 0:
            scores.append((doc_id, score))
    return sorted(scores, key=lambda row: (-row[1], row[0]))


@dataclass(frozen=True)
class VisibilityState:
    """Pure visibility snapshots; sequence is a model counter, NOT _seq_no.

    No acknowledgement, translog, fsync, flush, replicas, crash or recovery is
    represented. A refresh does not establish a durability guarantee here.
    """
    realtime: tuple[tuple[str, str], ...] = ()
    searchable: tuple[tuple[str, str], ...] = ()
    write_sequence: int = 0
    search_sequence: int = 0


def validate_state(state: VisibilityState) -> None:
    require(isinstance(state, VisibilityState), "expected VisibilityState")
    for name, rows in (("realtime", state.realtime), ("searchable", state.searchable)):
        require(isinstance(rows, tuple), f"{name} snapshot must be a tuple")
        seen = set()
        for row in rows:
            require(isinstance(row, tuple) and len(row) == 2, "invalid snapshot row")
            doc_id, text = row
            identifier(doc_id)
            require(isinstance(text, str), "document text must be a string")
            require(doc_id not in seen, "duplicate snapshot id")
            seen.add(doc_id)
    for sequence in (state.write_sequence, state.search_sequence):
        require(isinstance(sequence, int) and not isinstance(sequence, bool) and sequence >= 0,
                "sequence must be a nonnegative integer")
    require(state.search_sequence <= state.write_sequence, "search cannot precede a future write")


def put(state: VisibilityState, doc_id: str, text: str) -> VisibilityState:
    validate_state(state)
    identifier(doc_id)
    require(isinstance(text, str), "document text must be a string")
    current = dict(state.realtime)
    current[doc_id] = text
    return VisibilityState(tuple(sorted(current.items())), state.searchable,
                           state.write_sequence + 1, state.search_sequence)


def delete(state: VisibilityState, doc_id: str) -> VisibilityState:
    validate_state(state)
    identifier(doc_id)
    current = dict(state.realtime)
    current.pop(doc_id, None)
    return VisibilityState(tuple(sorted(current.items())), state.searchable,
                           state.write_sequence + 1, state.search_sequence)


def refresh(state: VisibilityState) -> VisibilityState:
    validate_state(state)
    return VisibilityState(state.realtime, state.realtime,
                           state.write_sequence, state.write_sequence)


def realtime_get(state: VisibilityState, doc_id: str) -> str | None:
    validate_state(state)
    identifier(doc_id)
    return dict(state.realtime).get(doc_id)


def search_snapshot(state: VisibilityState, query: str) -> list[str]:
    """Our AND-of-distinct-token query, not OpenSearch match query defaults."""
    validate_state(state)
    terms = set(tokenize(query))
    if not terms:
        return []
    return sorted(doc_id for doc_id, text in state.searchable
                  if terms <= set(tokenize(text)))


@dataclass(frozen=True)
class ScoredDoc:
    doc_id: str
    score: float


def validate_docs(docs: Sequence[ScoredDoc]) -> list[ScoredDoc]:
    require(isinstance(docs, (tuple, list)), "documents must be a list or tuple")
    seen = set()
    for doc in docs:
        require(isinstance(doc, ScoredDoc), "expected ScoredDoc")
        identifier(doc.doc_id)
        finite_number(doc.score, "score")
        require(doc.doc_id not in seen, "duplicate document id")
        seen.add(doc.doc_id)
    return list(docs)


def topk(docs: Sequence[ScoredDoc], k: int) -> list[ScoredDoc]:
    positive_int(k, "k")
    return sorted(validate_docs(docs), key=lambda doc: (-doc.score, doc.doc_id))[:k]


def distributed_topk(shards: Sequence[Sequence[ScoredDoc]], k: int,
                     candidate_budget: int) -> list[ScoredDoc]:
    """All scores already share one global comparator, unlike shard-local IDF."""
    positive_int(k, "k")
    positive_int(candidate_budget, "candidate_budget")
    require(isinstance(shards, (tuple, list)), "shards must be a list or tuple")
    flattened = []
    for shard in shards:
        flattened.extend(validate_docs(shard))
    validate_docs(flattened)  # Reject repeated IDs across shards, not just within one.
    candidates = [doc for shard in shards for doc in topk(shard, candidate_budget)]
    return topk(candidates, k)


def terms_topk(shards: Sequence[Mapping[str, int]], k: int,
               candidate_budget: int | None = None) -> list[tuple[str, int]]:
    """Sum local counts, optionally after per-shard truncation: our approximation."""
    positive_int(k, "k")
    if candidate_budget is not None:
        positive_int(candidate_budget, "candidate_budget")
    require(isinstance(shards, (tuple, list)), "shards must be a list or tuple")
    merged: Counter[str] = Counter()
    for shard in shards:
        require(isinstance(shard, Mapping), "terms shard must be a mapping")
        for term, count in shard.items():
            identifier(term, "term")
            positive_int(count, "term count")
        rows = sorted(shard.items(), key=lambda row: (-row[1], row[0]))
        merged.update(dict(rows if candidate_budget is None else rows[:candidate_budget]))
    return sorted(merged.items(), key=lambda row: (-row[1], row[0]))[:k]


def ranked_ids(ranking: Sequence[str]) -> list[str]:
    require(isinstance(ranking, (tuple, list)), "ranking must be a list or tuple")
    seen = set()
    for doc_id in ranking:
        identifier(doc_id)
        require(doc_id not in seen, "a ranking cannot contain duplicate ids")
        seen.add(doc_id)
    return list(ranking)


def rrf(rankings: Sequence[Sequence[str]], rank_constant: float = 60) -> list[tuple[str, float]]:
    """Sum 1/(c+rank), 1-based; missing=0. Model c>=0, NOT API validation."""
    finite_number(rank_constant, "rank_constant")
    require(rank_constant >= 0, "rank_constant must be nonnegative")
    require(isinstance(rankings, (tuple, list)), "rankings must be a list or tuple")
    scores: dict[str, list[float]] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranked_ids(ranking), start=1):
            scores.setdefault(doc_id, []).append(1 / (rank_constant + rank))
    return sorted(((doc_id, math.fsum(parts)) for doc_id, parts in scores.items()),
                  key=lambda row: (-row[1], row[0]))


def tenant_candidates(ranking: Sequence[str], tenants: Mapping[str, str], tenant: str,
                      budget: int, prefilter: bool) -> list[str]:
    """Candidate selection policy only; NOT authentication or authorization."""
    ids = ranked_ids(ranking)
    positive_int(budget, "budget")
    identifier(tenant, "tenant")
    require(isinstance(prefilter, bool), "prefilter must be boolean")
    require(isinstance(tenants, Mapping), "tenants must be a mapping")
    for doc_id, owner in tenants.items():
        identifier(doc_id)
        identifier(owner, "tenant")
    require(set(ids) <= tenants.keys(), "every ranked id needs a tenant")
    if prefilter:
        return [doc_id for doc_id in ids if tenants[doc_id] == tenant][:budget]
    return [doc_id for doc_id in ids[:budget] if tenants[doc_id] == tenant]


def recall_at_k(ranking: Sequence[str], relevant: set[str] | frozenset[str], k: int) -> float:
    ids = ranked_ids(ranking)
    positive_int(k, "k")
    require(isinstance(relevant, (set, frozenset)) and bool(relevant),
            "relevant must be a nonempty set; empty relevance has no recall here")
    for doc_id in relevant:
        identifier(doc_id)
    return len(set(ids[:k]) & relevant) / len(relevant)


def bm25_lab() -> dict:
    corpus = {"a": "cat cat dog", "b": "cat", "c": "dog mouse"}
    actual = dict(bm25(corpus, "cat", k1=1, b=1))
    # N=3, df(cat)=2, avgdl=2: a has tf=2,dl=3; b has tf=1,dl=1.
    require(document_frequency(corpus) == {"cat": 2, "dog": 2, "mouse": 1}, "df oracle failed")
    require(math.isclose(actual["a"], math.log(1.6) * 8 / 7), "a score oracle failed")
    require(math.isclose(actual["b"], math.log(1.6) * 4 / 3), "b score oracle failed")
    require([doc for doc, _ in bm25(corpus, "cat", 1, 1)] == ["b", "a"], "length normalization failed")
    equal_length = {"once": "cat dog dog dog", "twice": "cat cat dog dog",
                    "four": "cat cat cat cat"}
    saturated = dict(bm25(equal_length, "cat", 1, 0))
    require(saturated["once"] < saturated["twice"] < saturated["four"] < 2 * saturated["once"],
            "term-frequency saturation failed")
    return {"scope": "explicit ASCII tokenizer and illustrative BM25; NOT Lucene score parity",
            "positions": positions(corpus["a"]), "df": document_frequency(corpus),
            "scores": bm25(corpus, "cat", 1, 1), "average_length": 2,
            "equal_length_saturation_scores": saturated, "repeated_query_terms": "deduplicated"}


def refresh_lab() -> dict:
    initial = VisibilityState()
    indexed = put(initial, "a", "old cat")
    require(realtime_get(indexed, "a") == "old cat" and search_snapshot(indexed, "cat") == [],
            "pre-refresh visibility oracle failed")
    visible = refresh(indexed)
    updated = put(visible, "a", "new dog")
    require(realtime_get(updated, "a") == "new dog" and search_snapshot(updated, "cat") == ["a"]
            and search_snapshot(updated, "dog") == [], "update snapshot oracle failed")
    updated_visible = refresh(updated)
    deleted = delete(updated_visible, "a")
    require(realtime_get(deleted, "a") is None and search_snapshot(deleted, "dog") == ["a"],
            "delete snapshot oracle failed")
    gone = refresh(deleted)
    require(search_snapshot(gone, "dog") == [] and initial == VisibilityState(), "final oracle failed")
    trace = [{"operation": name, "write_sequence": state.write_sequence,
              "search_sequence": state.search_sequence, "realtime": dict(state.realtime),
              "searchable": dict(state.searchable)} for name, state in
             [("put", indexed), ("refresh", visible), ("update", updated),
              ("refresh", updated_visible), ("delete", deleted), ("refresh", gone)]]
    return {"scope": "visibility-only immutable model; NOT translog, fsync, flush or crash recovery",
            "trace": trace, "refresh_implies_durability": "not modeled; cannot infer"}


def distributed_topk_lab() -> dict:
    shards = [[ScoredDoc("a", 100), ScoredDoc("b", 99), ScoredDoc("c", 98)],
              [ScoredDoc("d", 97), ScoredDoc("e", 96)]]
    reference = topk([doc for shard in shards for doc in shard], 3)
    sufficient = distributed_topk(shards, 3, 3)
    insufficient = distributed_topk(shards, 3, 1)
    require([doc.doc_id for doc in reference] == ["a", "b", "c"] and sufficient == reference,
            "exact top-k oracle failed")
    require([doc.doc_id for doc in insufficient] == ["a", "d"], "candidate-loss oracle failed")
    buckets = [{"shared": 9, "a": 10}, {"shared": 9, "b": 10}]
    exact, truncated = terms_topk(buckets, 1), terms_topk(buckets, 1, 1)
    require(exact == [("shared", 18)] and truncated == [("a", 10)], "terms counterexample failed")
    return {"scope": "globally comparable fixed document scores; NOT shard-local BM25/ANN",
            "global_doc_top3": [doc.doc_id for doc in reference],
            "local3_doc_top3": [doc.doc_id for doc in sufficient],
            "local1_doc_top3": [doc.doc_id for doc in insufficient],
            "terms_global_top1": exact, "terms_local1_top1": truncated,
            "distinction": "document ranking and distributed bucket aggregation have different guarantees"}


def hybrid_filter_lab() -> dict:
    tenants = {"a1": "A", "a2": "A", "b1": "B", "b2": "B"}
    rankings = [["b1", "b2", "a1", "a2"], ["b2", "b1", "a2", "a1"]]
    before = [tenant_candidates(ranking, tenants, "A", 2, True) for ranking in rankings]
    after = [tenant_candidates(ranking, tenants, "A", 2, False) for ranking in rankings]
    fused_before, fused_after = rrf(before), rrf(after)
    require(before == [["a1", "a2"], ["a2", "a1"]] and after == [[], []], "candidate oracle failed")
    require([doc for doc, _ in fused_before] == ["a1", "a2"] and not fused_after, "RRF tie oracle failed")
    require(all(math.isclose(score, 123 / 3782) for _, score in fused_before), "1-based RRF oracle failed")
    good = recall_at_k([doc for doc, _ in fused_before], {"a1", "a2"}, 2)
    bad = recall_at_k([doc for doc, _ in fused_after], {"a1", "a2"}, 2)
    require(good == 1 and bad == 0, "recall oracle failed")
    return {"scope": "fixed lexical/vector ranked lists, NOT ANN execution; candidate filter is NOT authZ",
            "prefilter_candidates": before, "truncate_then_filter_candidates": after,
            "prefilter_rrf": fused_before, "truncate_then_filter_rrf": fused_after,
            "prefilter_recall_at_2": good, "truncate_then_filter_recall_at_2": bad,
            "rrf_definition": "sum 1/(60+rank), 1-based ranks; missing=0; tie=id ascending"}


LABS = {"bm25": bm25_lab, "refresh": refresh_lab,
        "distributed-topk": distributed_topk_lab, "hybrid-filter": hybrid_filter_lab}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab", choices=[*LABS, "all"], default="all")
    args = parser.parse_args(argv)
    names = list(LABS) if args.lab == "all" else [args.lab]
    results = {name: LABS[name]() for name in names}
    print(json.dumps({"status": "PASS", "runtime": "Python standard library only", "labs": results},
                     indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
