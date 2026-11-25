# Frontend wireframes (WBS Day 1, §8)

Low-fidelity layouts for the five routes. The implemented screens are in `evidence/screenshots/`.

## `/` Recommendations

```text
┌ Navbar: K KuaiRec │ Recommendations Compare Metrics System │ ● API healthy │ ☾ ┐
│ H1 Explainable short-video recommendations                                     │
│ ┌ Controls ───────────────────────────────────────────────────────────────────┐ │
│ │ [Demo user ▼] [Any user ID ____][Load] [Model ▼] [Top-K ▼] [Sort ▼] [Refresh]│ │
│ │ ☐ Cold-start view   ☑ Exclude already-seen                                   │ │
│ └─────────────────────────────────────────────────────────────────────────────┘ │
│ ┌ State banner: Personalised / Unknown user / No positive history / Cold start ┐ │
│ model · split · fallback · results · latency · generated                         │
│ ┌ Card ─────┐ ┌ Card ─────┐ ┌ Card ─────┐   ┌ Hybrid explanation (α β γ bars) ┐ │
│ │Rank  score│ │           │ │           │   └─────────────────────────────────┘ │
│ │category   │ │           │ │           │   ┌ Evidence: user history ─────────┐ │
│ │title      │ │           │ │           │   │ seen / positive counts          │ │
│ │metadata   │ │           │ │           │   │ recent positive videos →        │ │
│ │breakdown  │ │           │ │           │   └─────────────────────────────────┘ │
│ │reasons+ev.│ │           │ │           │                                      │
│ │Play Click Skip Hide│    │           │                                      │
└──────────────────────────────────────────────────────────────────────────────────┘
States: skeleton cards (loading) · empty message · error with Retry (timeout / backend unavailable / HTTP)
Mobile: controls wrap; cards one column; side panels move below.
```

## `/videos/[videoId]`

```text
← Back │ ┌ category · caption ┐ ┌ Official metadata: ID, categories, tags, author, upload, type, duration, positive events ┐
       Similar items (Item-CF):  [card cosine →] [card] [card] [card]        Not-in-catalog state for unknown IDs
```

## `/compare`

```text
[User ▼] [Items per model ▼] [Refresh]
┌ Popularity ┐ ┌ Item-CF ┐ ┌ LightGCN (rejected) ┐ ┌ Hybrid (selected) ┐   same user, same candidate protocol
│ #1 title s │ │         │ │                     │ │                   │   top reason badge per item
└────────────┘ └─────────┘ └─────────────────────┘ └───────────────────┘   empty_reason when no signal
```

## `/metrics`

```text
Split summary (train/val/test, relevance, candidates, users, catalog, seed)
Validation table: Recall@10 NDCG@10 HR@10 P@10 | Recall@20 NDCG@20 Coverage
NDCG@10 bar chart        Controlled test (selected hybrid) + cold-start/seen checks
```

## `/system`

```text
API status (readiness checks, DB kind, telemetry) │ Dataset release │ Manifest (models, weights, serving, reason rules)
Reproducibility (commands, bundle + source SHA-256) │ Architecture diagram
```
