# Lunarbit

## Evidence-Verifiable Personal Commerce GraphRAG

### Reconstructing trustworthy answers from messy commerce evidence

Lunarbit is designed as a public, privacy-safe, six-year personal-commerce intelligence system built from Zomato and Swiggy records.

Lunarbit turns a multi-year archive of Zomato and Swiggy emails, order summaries, merchant invoices, platform-fee invoices, and delivery documents into a provenance-first personal-commerce intelligence system. It is designed to answer questions about orders, merchants, fees, discounts, taxes, payments, delivery evidence, and spending patterns while preserving the chain from every answer back to source evidence.

The hard problem is not generating a fluent summary. It is preserving document scope, layout, source precision, uncertainty, and financial truth while turning fragmented evidence into a graph that can be queried and audited. Lunarbit addresses that problem with deterministic contracts, guarded agentic enrichment, reversible decisions, and explicit proof gates.

> **Project thesis:** trustworthy GraphRAG is not just retrieval plus an LLM. It separates source claims, normalized facts, deterministic calculations, identity decisions, unresolved uncertainty, and analytical findings—and makes each layer auditable.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-112%20passing-2ea44f)](tests/)
[![Type checks](https://img.shields.io/badge/mypy-strict-2ea44f)](https://mypy.readthedocs.io/)
[![Lint](https://img.shields.io/badge/ruff-clean-2ea44f)](https://docs.astral.sh/ruff/)
[![Privacy](https://img.shields.io/badge/source%20data-private%20by%20design-6f42c1)](#privacy-and-data-boundaries)

## The engineering problem

Most personal-finance prototypes flatten documents into rows and ask a model to summarize them. That approach loses layout, source precision, document scope, contradictions, and the distinction between an invoice assertion and a confirmed payment.

Lunarbit treats the archive as an evidence reconstruction problem:

- one order may be distributed across an email, an order summary, a merchant invoice, a platform-fee invoice, and a delivery invoice;
- an email without a PDF is still a complete order-evidence unit rather than a discarded message;
- tables, page coordinates, reading order, source spans, and document roles are preserved;
- money is represented with source precision and reconciled deterministically, never by an LLM or floating-point arithmetic;
- model output is candidate enrichment only and cannot write canonical identities, financial truth, or graph state directly;
- public output is a reviewed projection with aliases and redacted evidence, never a view over the raw private archive.

## Engineering highlights

| Area | Demonstrated engineering signal |
| --- | --- |
| Document intelligence | Native PDF extraction, layout and table preservation, page coordinates, quality profiles, email parsing, and document-role classification |
| Data contracts | Strict Pydantic contracts, content-addressed IDs, deterministic manifests, source hashes, provenance spans, and atomic validation boundaries |
| Agentic AI | Provider-adapted structured generation, bounded semantic regions, exact source and money coverage, typed validation, deterministic repair, and resumable quarantine |
| Financial correctness | Exact source amounts, scoped money components, deterministic reconciliation, residual visibility, and no model arithmetic |
| Knowledge graph | 48,784 typed nodes and 70,010 closed-reference relationships across evidence, commerce, identity, product, financial, reconciliation, and provenance layers |
| Retrieval systems | Neo4j HNSW, Lucene/BM25, Cohere Embed v4, RRF, bounded graph expansion, Cohere Rerank v4, source authority, and citation-level abstention |
| Production judgment | Rate-governed resumable jobs, hard context budgets, no private data in Git, `0600` artifacts, visible red/green TDD, and measured gates before claims |

### Adaptive retrieval and vector systems

Lunarbit treats retrieval as a systems-design problem, not a generic vector-store integration:

- **MRL — adaptive representation resolution:** all 24,675 evidence nodes have a native 1,536-dimensional Cohere Embed v4 reference vector plus explicitly labelled 256/512/1024 normalized Matryoshka-prefix ablation indexes.
- **HNSW — navigable dense retrieval graph:** Neo4j HNSW indexes use cosine similarity, scalar quantization, `M=16`, and construction effort `100`; every index passed exact corpus-coverage and online-state checks.
- **RaBitQ — portable compression extension:** the retrieval boundary is designed to admit a native RaBitQ backend such as Milvus/Zilliz without changing graph truth or evidence contracts. Neo4j scalar quantization is used today and is not mislabelled as RaBitQ.

The retrieval path combines these capabilities with exact identifiers, Lucene/BM25, graph traversal, metadata filters, and evidence verification. Index parameters, embedding dimensions, quantization settings, recall, grounding, latency, and storage are benchmarked and versioned in the retrieval plan.

### Current verified corpus and quality metrics

These are measurements from the local private corpus and deterministic pipeline. The source archive and generated private artifacts are intentionally excluded from GitHub.

- 456 relevant source emails and 763 PDFs across 857 PDF pages;
- 454 current reconstructed order records under the documented counting policy;
- 24,675 deterministic evidence chunks across 456 order-evidence bundles;
- 13,597 final deterministic agentic regions with exact coverage of all 24,675 chunks and 5,199 money components;
- 48,784 canonical graph nodes and 70,010 relationships, with byte-stable private archives and idempotent Neo4j replay;
- 24,675/24,675 native Cohere Embed v4 vectors at 1,536 dimensions, generated in 258 resumable calls;
- complete 256/512/1024 MRL-prefix and 1,536 native HNSW indexes, while retaining the earlier 1,024-dimensional Mistral embedding baseline for ablation;
- a live hybrid smoke path of 30 dense + 30 lexical candidates, RRF, graph expansion, Cohere reranking, 10/10 citations, and verified evidence status;
- an authenticated FastAPI-to-Neo4j/Cohere runtime that returns bounded verification metadata without exposing private evidence text;
- 112 automated tests passing, plus Ruff and strict MyPy across 21 source modules.

The corrected balanced relevance-set MRL benchmark reports 97.5% Hit@1/5/10 and 0.975 MRR at every tested dimension. The 256-dimensional prefix reduced median local HNSW latency from 10.99 ms to 6.75 ms, making it the provisional candidate-search index; the native 1,536-dimensional index remains the serving reference until the real user-query golden set confirms the switch. The superseded exact-chunk artifact remains published as a diagnostic example of how duplicate evidence can invalidate a naive metric.

### What is already proven

- Deterministic ingestion handles both PDF-backed orders and mail-only orders.
- Layout-aware extraction preserves page geometry, reading order, tables, and source spans.
- Rich chunks carry facts, entities, money candidates, graph candidates, confidence, completeness, and privacy metadata.
- Deterministic resolution preserves duplicate evidence, provisional identities, merchant-scoped products, and explicit uncertainty instead of forcing unsafe merges.
- All 5,199 source amounts are Decimal-backed and reconciled only within valid document and commercial scopes.
- The canonical graph rebuild is closed-reference and idempotent; vector properties are versioned so experiments never overwrite the serving or baseline representation.
- The online path performs read-only parameterized retrieval, exact/Lucene/dense fusion, bounded graph expansion, reranking, source-authority scoring, evidence verification, and explicit degradation.
- The private API requires server-side bearer configuration; credentials and raw source evidence never enter its response contract.

The remaining backend work is explicit: complete the corrected relevance-set and user-query golden evaluations, then add evidence-bound answer synthesis. Frontend implementation remains intentionally paused until its visual and interaction direction is agreed.

## What the finished system will demonstrate

The public product described in the plan is designed around evidence-heavy questions rather than a generic chat interface:

1. **Cross-document financial reconstruction** — combine an order summary, merchant invoice, platform invoice, and delivery evidence while preserving their different truth scopes.
2. **Clickable evidence replay** — trace an answer through its calculation, graph path, evidence chunk, and privacy-reviewed page crop.
3. **Privacy-safe identity analysis** — distinguish high-confidence identity clusters from possible same-name mentions and unresolved delivery evidence.
4. **Query-adaptive GraphRAG** — route exact lookups, financial aggregation, lexical search, semantic discovery, evidence requests, and multi-hop economic questions through the appropriate retrieval strategy.
5. **Personal commerce intelligence** — support governed price indices, fee and discount analysis, membership ROI, spending decomposition, and safe scenario analysis.
6. **Document and business archaeology** — expose invoice-template drift, legal-entity rename history, emerging charge categories, and unexplained financial residuals without inventing causes.

## Architecture

```mermaid
flowchart LR
    A[Private PDFs and mailboxes] --> B[Deterministic ingestion]
    B --> C[Document and message contracts]
    C --> D[Layout-aware extraction]
    D --> E[Order evidence bundles]
    E --> F[Deterministic rich chunks]
    F --> G[Bounded semantic enrichment]
    G --> H[Typed validation and quarantine]
    H --> I[Entity and order resolution]
    I --> J[Financial reconciliation]
    J --> K[Neo4j temporal graph]
    K --> L[Exact, lexical, dense, and graph retrieval]
    L --> M[Evidence-grounded answer workflow]
    M --> N[Privacy-reviewed public projection]
```

The implemented backend covers ingestion, extraction, chunking, guarded semantic enrichment, reversible resolution, deterministic finance, canonical graph compilation, local Neo4j loading, Cohere/Mistral embeddings, hybrid retrieval, reranking, citation verification, a synthetic public projection, and an authenticated FastAPI retrieval surface. The interactive frontend and deployment remain behind explicit acceptance gates in [`PLAN.md`](PLAN.md).

## What the system preserves

Each deterministic chunk can carry:

- raw and normalized private text;
- semantic summary and embedding text;
- page number, bounding box, reading order, table ID, row index, and parent region;
- source document or message identity and source hash;
- candidate facts with exact source spans;
- deterministic entity mentions and money components;
- graph candidates and query-family metadata;
- extraction method, confidence, completeness, validation, and privacy state.

This metadata is not decorative. It enables reproducibility, source replay, deterministic validation, retrieval routing, and later graph invariants.

## Agentic enrichment: bounded, typed, and evidence-first

Lunarbit packs template-compatible order bundles into medium-sized calls rather than issuing one request per chunk or dumping the whole archive into one context. Provider adapters share the same evidence contract, and accepted output passes deterministic schema, coverage, provenance, financial-reference, cross-bundle, and privacy checks before entering a separate repaired archive.

The production boundary provides:

- deterministic batch plans with explicit context and output ceilings;
- exact ordered source-chunk and money-component coverage manifests;
- batch-, bundle-, chunk-, fact-, entity-, and money-scoped reference constraints;
- bounded region counts, narrative lengths, and candidate arrays;
- deterministic persistent IDs—never model-generated IDs;
- resumable provider calls with rate governance, retry classification, and atomic checkpoints;
- separate accepted, quarantined, repaired, retried, and final canonical archives;
- privacy-safe diagnostics that retain categories and numeric codes, not private provider messages;
- a final evidence-risk selector that accepts retries only when complete-bundle quality improves.

Models may propose semantic regions, retrieval text, query families, interpretations, relationships, conflicts, and uncertainty. They cannot perform authoritative arithmetic, resolve canonical identity, write Cypher, or mutate graph truth.

### Runtime stack

The current backend uses Python 3.12+, strict Pydantic contracts, Neo4j 5.26, Lucene full text, Neo4j HNSW, Cohere Embed v4 and Rerank v4, application-owned RRF, deterministic verification, and FastAPI. The serving dimension is 1,536 pending the corrected golden evaluation; Mistral 1,024-d vectors remain an ablation baseline. Next.js/Vercel and Aura deployment are planned only after the frontend direction and public privacy review are complete.

## Graph and truth model

The planned graph is layered so that an answer can distinguish what a source said from what the system normalized, calculated, resolved, or inferred:

```text
Evidence layer      documents, pages, chunks, assertions, source coordinates
Commerce layer      orders, order lines, merchants, outlets, platforms
Product layer       observed items, canonical items, comparable item groups
Identity layer      aliases, legal entities, business roles, reversible decisions
Financial layer     money components, promotions, taxes, payments, reconciliations
Intelligence layer  findings, metrics, query traces, evidence-backed explanations
```

Source claims remain separate from normalized facts. Deterministic calculations remain separate from model interpretations. Identity merges remain reversible. Unexplained residuals remain visible instead of being silently attributed.

## Explicit boundaries

Lunarbit is intentionally not:

- a PDF chatbot that hides its evidence chain;
- a generic expense dashboard that flattens truth scopes;
- an unverified text-to-Cypher generator;
- a banking core, payment processor, or financial-advice product;
- a public viewer over raw invoices, mailboxes, names, addresses, or registrations;
- a claim of universal superiority over platform or fintech infrastructure.

The system is a user-owned, privacy-reviewed commerce reconstruction and economic-intelligence project. Public claims must be supported by measured benchmarks or clearly labeled as planned behavior.

## Privacy and data boundaries

The repository is public-facing, but the source archive is private. The privacy boundary is treated as an engineering invariant:

- raw PDFs, mailboxes, processed private JSON, and model outputs are ignored by Git;
- `.env` and credentials are never committed;
- private result files are written atomically with restrictive permissions;
- public identifiers are deterministic aliases, not platform order IDs or invoice numbers;
- customer, proprietor, delivery-person, address, tax-registration, and payment details are not exposed in the public projection;
- public evidence is manually redacted or synthetic and is served separately from the private graph;
- canonical graph writes require deterministic validation and privacy review.

The private corpus is not included in this repository. Do not run the pipeline against data you do not have permission to process.

## Engineering workflow

The project follows visible test-driven development. Contract tests are written for failure modes such as incomplete coverage, unsupported entities, invalid spans, mixed tool content, truncation, provider errors, and privacy leakage before the implementation is accepted.

Run the local checks:

```bash
uv run pytest -q
uv run ruff check src scripts tests
uv run ruff format --check src scripts tests
uv run mypy src/lunarbit
```

Build the deterministic private pipeline:

```bash
uv run python scripts/build_json.py --input data --output data/processed
uv run python scripts/build_chunks.py --input data/processed
```

Inspect the agentic plan without sending private data to a model:

```bash
uv run python scripts/run_agentic_chunking.py --input data/processed
```

Build or inspect the current retrieval layers:

```bash
uv run python scripts/embed_graph_cohere.py \
  --graph-root data/processed/_graph/canonical_v1_20260811 \
  --output data/processed/_embeddings/cohere_embed_v4_1536

uv run python scripts/derive_mrl_indexes.py \
  --archive data/processed/_embeddings/cohere_embed_v4_1536

uv run python scripts/benchmark_mrl_retrieval.py --queries 40 --top-k 10
```

All live provider execution is opt-in. Put credentials only in ignored `.env`; begin with a bounded smoke run and inspect deterministic validation output before scaling.

## Repository map

```text
src/lunarbit/
├── models.py              # strict immutable source and pipeline contracts
├── extract.py / pdf.py    # deterministic email, PDF, layout, table, and quality extraction
├── chunk.py / agentic.py  # rich chunks, bounded enrichment, validation, and quarantine
├── resolve.py / finance.py# reversible identity/product resolution and Decimal truth
├── graph.py               # typed canonical nodes, relationships, and invariants
├── retrieval.py           # governed Cypher, RRF, authority, and evidence verification
├── cohere.py              # typed Embed v4 and Rerank v4 transport boundary
├── hybrid.py              # HNSW + Lucene + RRF + graph expansion + reranking
├── runtime.py             # read-only governed analytical execution
├── evaluation.py          # retrieval quality and latency metric contracts
└── api.py / service.py    # public demo and authenticated private retrieval API

scripts/
├── build_json.py / build_chunks.py       # private deterministic evidence archives
├── build_graph.py / ingest_graph.py      # canonical graph compilation and Neo4j load
├── embed_graph.py                         # retained Mistral ablation baseline
├── embed_graph_cohere.py                  # resumable native Embed v4 corpus vectors
├── derive_mrl_indexes.py                  # explicit normalized MRL ablation indexes
├── benchmark_mrl_retrieval.py             # privacy-safe aggregate retrieval benchmark
└── serve_api.py                           # local FastAPI + Neo4j + Cohere runtime

tests/          # 112 extraction, graph, finance, retrieval, API, privacy, and TDD checks
benchmarks/     # aggregate-only evaluation artifacts; never source evidence

PLAN.md       # complete architecture, ontology, acceptance criteria, and roadmap
MEMORY.md     # append-only engineering handoff and decisions
cypher/       # graph design assets and future migrations
web/          # public application surface under construction
```

## Delivery roadmap and proof gates

### Phase 1 — Evidence foundation

Completed foundation: source ingestion, PDF and email extraction, layout-aware chunks, order-evidence bundles, strict contracts, privacy controls, and reproducible validation.

### Phase 2 — Guarded semantic enrichment

Completed: 13,597 final regions cover all 24,675 chunks and 5,199 money components exactly once after validation, deterministic repair, selective retries, and complete-bundle evidence-risk selection.

### Phase 3 — Reversible resolution

Completed: 454 orders, platform-scoped merchants, provisional outlets, legal entities, delivery mentions, item observations, merchant items, aliases, duplicate evidence, and uncertainty are represented without unsafe global merges.

### Phase 4 — Deterministic financial truth

Completed: all 5,199 source amounts use Decimal semantics; 256 scoped reconciliations retain both exact results and explicit conflicts without model arithmetic.

### Phase 5 — Temporal graph and indexes

Completed locally: the 48,784-node/70,010-relationship graph loads idempotently with constraints, exact and Lucene indexes, four Cohere HNSW representations, and a retained Mistral baseline.

### Phase 6 — Hybrid GraphRAG retrieval

Backend retrieval completed: governed exact queries and hybrid HNSW/Lucene retrieval use RRF, bounded graph expansion, Cohere reranking, authority scoring, verification, and explicit fallback. Evidence-bound answer synthesis and the user-query golden evaluation remain the final backend gates.

### Phase 7–8 — Economic intelligence and public product

The deterministic public projection and synthetic demo contracts exist. Interactive graph, evidence, benchmark, transaction, and economic-intelligence pages begin only after frontend design review.

## Evaluation and definition of done

The project is not complete when a model produces plausible prose. Each stage has a measurable exit gate:

- extraction reproduces reviewed golden documents and preserves source coordinates;
- agentic regions retain complete chunk and money-component coverage;
- entity and order resolution meets reviewed precision gates and remains reversible;
- financial reconciliation is exact, scoped, and residual-aware;
- graph rebuilds are idempotent and satisfy relationship and privacy invariants;
- retrieval publishes exact, lexical, dense, hybrid, and graph results with ablations;
- every showcased answer exposes navigable evidence and its graph path;
- public privacy-leakage tests pass;
- deployment is stable and documented;
- resume claims match measured results rather than aspirations.

Benchmark reporting includes extraction and coverage invariants, entity and order resolution, reconciliation state, retrieval Hit@K/MRR/latency, end-to-end answer quality, citation support, abstention accuracy, and cost. Exact-chunk diagnostics are kept separate from relevance-set and user-query evaluation so duplicate evidence cannot create false failures.

## Measured engineering outcome

Lunarbit currently reconstructs 454 orders from 456 relevant emails and 763 private PDFs; compiles 24,675 source-addressable evidence chunks into a 48,784-node temporal knowledge graph; preserves 5,199 deterministic financial components; and executes verified hybrid GraphRAG through Neo4j, Cohere, RRF, graph traversal, reranking, and citation gates. Private source artifacts remain outside Git by construction.

## Project status

Lunarbit is an active evidence-systems build. The private data pipeline, canonical graph, vector and lexical indexes, hybrid retrieval, reranking, verification, public-safe synthetic projection, and authenticated retrieval API are implemented. Corrected relevance-set evaluation, evidence-bound answer synthesis, frontend implementation, deployment, and public privacy review remain open.

That distinction is part of the project: a trustworthy AI engineer should know exactly which results are measured, which are private, which are candidates, and which are still hypotheses.

## The standard

The goal is not to build the largest knowledge graph. It is to build the most convincing, trustworthy, and technically complete public GraphRAG demonstration possible from personal-commerce documents.

## License and responsible use

The source archive belongs to the data owner and is not distributed with this repository. Before processing any archive, verify consent, access rights, retention requirements, and privacy obligations. Public examples should use synthetic or manually redacted evidence.
