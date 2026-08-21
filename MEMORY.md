# MEMORY.md

## Session handoff

- Last updated: 2026-08-21
- Active phase: The local backend is complete through canonical-oracle evaluation. Nexus Insight is live-wired to the privacy-safe public FastAPI contract; remaining gates are public privacy review and cloud deployment.
- Current branch: `main`, pushed to `origin/main`
- Repository: `https://github.com/simon-derock/Lunarbit.git`
- Last verified implementation commit: `a9c3c8f` (`ci(repo): enforce public release boundaries`), pushed to `main`.
- Last passing checks: 184 committed Python tests, Ruff lint, strict MyPy across 36 modules, repository hygiene, Nexus Insight ESLint (six inherited fast-refresh warnings only), and a production Nexus Insight build. The public-only service and release audit passed with `200` health/showcase responses and absent private routes.

## Current state

- Completed:
  - Read `PLAN.md` and audited every source container, manifest, email, and PDF in `data/`.
  - Verified 456 relevant source emails, 763 unique PDFs, and 857 PDF pages.
  - Verified native text and coordinate extraction for all PDFs; current files do not require OCR by default.
  - Classified eight document roles and identified Swiggy manifest order-ID conflicts.
  - Established the current evidence-based total of 454 orders under the counting policy below.
  - Added a deny-by-default `.gitignore` for private commerce data and secrets.
  - Added strict Pydantic source-message, source-document, candidate, evidence, and inventory contracts.
  - Implemented deterministic ingestion for acquisition manifests and Takeout mboxes, including mail-only order evidence.
  - Added content-addressed IDs, manifest integrity checks, content-aware document roles, labelled order-ID extraction, and history-row deduplication.
  - Added atomic, byte-stable private JSONL output with `0600` permissions under ignored `data/processed/_inventory/`.
  - Added strict page, bounding-box, text-block, key-value, table, image, quality, document, and manifest contracts.
  - Implemented native text/layout extraction, table header links and merged-cell spans, image inspection, and deterministic reading order.
  - Added private per-document manifest/document JSON, page JSONL, Markdown previews, and lossless WebP page renders.
  - Added explicit OCR-required/quarantine routing for failed pages; every current page passed native extraction.
  - Preserved private email body text with HTML block boundaries so attachmentless messages can produce semantic evidence.
  - Added deterministic routing for order summaries, invoices, fee/tax documents, history tables, and email orders.
  - Added UUID5 evidence chunks with source regions, table coordinates, raw/normalized/summary/embedding representations, and query-family routing.
  - Added evidence-supported candidate facts, entity mentions, money components, and graph candidates without promoting them to canonical truth.
  - Added an atomic validator boundary that quarantines malformed agentic proposals without partial acceptance.
  - Added reproducible chunk archive and benchmark scripts covering every document and message source.
  - Corrected historical labelled Swiggy order-ID extraction, resolving 26 previously provisional orders.
  - Benchmarked Cloudflare Workers AI GLM-4.7-Flash, then selected `@cf/google/gemma-4-26b-a4b-it` after live comparison.
  - Added deterministic order-relevant batching with table preservation, mail-only cohort packing, hard prompt limits, and no one-chunk calls.
  - Added typed model-response validation for complete coverage, exact-source entities and relations, and cross-order isolation.
  - Added a sequential, opt-in runner that requires an explicit call cap and writes validated results privately with mode `0600`.
  - Expanded agent inputs to include deterministic text representations, coordinates, tables, facts, entities, money, graph candidates, confidence, completeness, validation, and privacy metadata.
  - Expanded proposals with bundle-scoped semantic regions, retrieval text, query families, exact facts/entities, money interpretations, governed relations, conflicts, and uncertainty.
  - Pinned Google's official Gemma 4 tokenizer and retained the verified 64k target and 80k input-token ceiling inside its 256k context.
  - Packed up to six template-compatible PDF or mail order bundles per call while deterministically rejecting all cross-bundle regions.
  - Added local `.env` loading and ignored the observed `.emv` typo without opening or tracking that credential-bearing file.
  - Added Cloudflare's documented SSE transport, low-reasoning/no-thinking controls, complete-stream and truncation guards, and a 600-second socket/wall-clock deadline.
  - Added privacy-safe JSON/schema diagnostics that retain only validation error types and field locations.
  - Replaced unstable free-form JSON with one required `submit_agentic_regions` function call generated from the Pydantic response schema.
  - Added exact ordered source and money-component coverage manifests, evidence-constrained batch/bundle/chunk identifiers, and deterministic entity-candidate tuples.
  - Added explicit region, narrative, and candidate-array bounds after money-dense pilots demonstrated that unconstrained rich output could exhaust 24,000 completion tokens.
  - Added privacy-safe transport categories and numeric-only Cloudflare error codes without retaining provider messages or private partial responses.
  - Verified the SSE event shape with a non-private request and ran isolated private pilots; all private artifacts remain ignored and mode `0600`.
  - Recorded TDD progression as separate red-test and green-implementation commits.
  - Completed 1,308 accepted agentic batch results containing 13,889 semantic regions with exact coverage of all 24,675 deterministic chunks and 5,199 money components.
  - Added deterministic post-processing that removes call-local aliases, restores supplied facts and entities, rejects candidates outside the deterministic contract, specializes duplicate embedding text, and enriches safe sparse regions without mutating the original model archive.
  - Produced a private repaired archive with exact bundle, source, money, fact, entity, and relation invariants and a content-addressed quality manifest.
  - Retried the 1,254 semantic-warning regions as 255 rate-governed batches, then deterministically repaired and accepted 1,388 replacement regions.
  - Compiled one canonical private region archive with deterministic region IDs, exact source and money coverage, batch/model provenance, and explicit residual quality flags.
  - Completed a second 248-batch semantic pass over complete conflict bundles and deterministically selected retries only when they reduced bundle-level evidence risk.
  - Compiled the final Phase 2 archive with all 24,675 source chunks and 5,199 money components represented exactly once, 13,597 unique deterministic region IDs, and zero blocking quality defects.
  - Resolved 559 immutable order-evidence records into 453 exact platform orders and 1 provisional order while retaining 105 duplicate evidence links and reversible decisions.
  - Resolved 1,231 entity mentions into 139 platform-scoped merchants, 423 provisional per-order outlets, 4 legal entities, and 4 mention-only delivery records without inferring any person identity.
  - Produced 320 source-backed item observations and 245 merchant-scoped items; cross-merchant canonical items and comparable groups remain intentionally unasserted.
  - Normalized all 5,199 source amounts into Decimal-backed financial truth records and ran 256 document/scope reconciliations without inventing a global zero-sum.
  - Compiled 48,784 typed nodes and 70,010 relationships into a closed-reference, storage-neutral canonical graph with content-addressed archives.
  - Loaded the complete graph into local Neo4j through indexed, parameterized, idempotent batches and verified that a replay leaves counts unchanged.
  - Embedded all 24,675 evidence chunks in 193 resumable batches with 1,024-dimensional `mistral-embed-2312` vectors.
  - Created an online Neo4j HNSW vector index with cosine similarity, scalar quantization, `M=16`, and construction effort `100`, while retaining full vectors on evidence nodes.
  - Added exact, full-text, dense, reciprocal-rank-fused, graph-expanded retrieval with fact-specific source authority and citation-level abstention gates.
  - Added Graph-O1-inspired action, depth, candidate-path, relationship, row, and read-only query limits before database execution.
  - Compiled all 5,199 canonical money components into exactly 5,199 temporal financial events and 5,199 evidence cells using source-message occurrence time, immutable component lineage, and deterministic event semantics.
  - Compiled 11,368 multi-resolution financial chunks spanning evidence cells, financial events, transaction bundles, 529 merchant/outlet histories, and seven annual research windows.
  - Extended the private graph to 53,983 nodes and 85,607 relationships, loaded it into local Neo4j twice, and verified identical counts after replay while preserving vector properties.
  - Added reviewed-basket personal food price indexing, exact spending-change decomposition, fee/discount/membership economics, descriptive elasticity/substitution signals, robust anomaly/change-point detection, immutable counterfactuals, and a governed hypothesis-to-finding loop.
  - Added an authenticated `/v1/private/answer` runtime using only allowlisted read queries, bounded pagination, Decimal arithmetic, citation verification, and explicit abstention; raw evidence text never enters the response contract.
  - Built private answer goldens from immutable JSONL archives rather than Neo4j and passed 24 of 24 canonical-oracle cases across financial aggregation, price history, merchant counts, delivery mentions, and abstention.
  - Implemented a Next.js 16 public workspace with overview, graph explorer, economic terrain, transactions, evidence lab, and benchmark routes.
  - Added four fully isolated synthetic commerce profiles and five independent visualization profiles, persisted in local state and shareable query parameters.
  - Translated the reviewed Dark Chromatic references into code-native constellation, terrain, signal, receipt, proof, and benchmark visual systems without committing the private sample directory.
  - Verified all six routes through interaction tests, strict TypeScript, ESLint, production build, and headless desktop/mobile visual review.
  - Added a keyboard-accessible governed query console with 16 question-matched synthetic answers, explicit calculations, profile-closed graph traces, and pre-traversal abstention for unreviewed requests.
  - Added Nexus Insight as the active public topology console, connected only to the public FastAPI contract and never directly to Neo4j.
  - Added a live Neo4j aggregate projection that exposes only graph classes, relationship types, and counts; canonical IDs, properties, source text, and private records remain unavailable to the browser.
  - Added a bounded public showcase-answer endpoint: reviewed synthetic scenarios return a deterministic calculation, graph path, and public evidence card; all other prompts explicitly abstain.
  - Added a public-only FastAPI launcher that omits private GraphRAG routes, requires an explicit non-wildcard CORS allowlist, works with a synthetic fallback, and can attach to the aggregate Neo4j projection with read-only queries.
  - Added a thread-safe 15-second cache around the already-safe aggregate projection to prevent concurrent public requests from multiplying Neo4j count queries.
  - Added repository hygiene contracts and GitHub Actions CI covering Python tests, strict typing, Nexus Insight build, public-container audit, and private-artifact exclusion on pull requests and pushes to `main`.
- In progress: Public privacy review and cloud deployment preparation. The current public UI consumes only the reviewed FastAPI contract.
- Pending external input: Public deployment target, Aura read-only credentials, and final privacy-reviewed API exposure. Provider credentials load from the ignored `.env`; do not expose or commit them.
- Retrieval architecture now includes adaptive Matryoshka embeddings, HNSW
  graph navigation, and RaBitQ quantization as first-class planned production
  capabilities. The design retains full-precision vectors for reranking and
  evidence audits while compressed indexes provide scale-efficient candidate
  search across future Neo4j, Zilliz/Milvus, LanceDB, and CockroachDB
  projections.
- Schema/model/index versions in use: extraction `1.0.0`, chunk schema `1.0.0`, agentic contract `1.5.0`, post-processing `1.0.0`, canonical graph `v1`, economic corpus `economic-corpus-v1.0.0`, financial chunks `financial-intelligence-chunks-v1.0.0`, retrieval policy `hybrid-retrieval-v1.0.0`, answer evaluation `grounded-answer-evaluation-v1.0.0`, package `0.1.0`.
- Latest metrics snapshot:
  - Relevant source emails: 456
  - Excluded unrelated emails: 1
  - Unique PDFs: 763
  - PDF pages: 857
  - PDF-backed ordinary order messages: 403
  - Mail-only order messages: 51
  - History report documents: 2
  - History rows deduplicated against ordinary evidence: 73
  - Native-quality complete documents: 763 of 763
  - Extracted text characters: 1,236,136
  - Detected tables: 620
  - Detected images: 1,668
  - OCR-required or quarantined documents: 0
  - Private artifact files: 3,913, all mode `0600`
  - Deterministic processed-archive SHA-256: `ff327694b2c831fbe530785904b59bae6515dc931d65292eac2371a7c196429c`
  - Chunk evidence sources: 1,219 accepted, 0 quarantined
  - Rich evidence chunks: 24,675 valid, 0 invalid
  - Candidate assertions: 4,096
  - Candidate entity mentions: 1,231
  - Candidate money components: 5,199
  - Phase 1 tables preserved as table chunks: 620 of 620
  - Mail-only evidence: 51 messages; 50 with order ID, 24 with explicit merchant, 31 with explicit money
  - Unsupported candidate rate: 0
  - Deterministic chunk-archive SHA-256: `71f9c919d6d71e677dc49dd30920a4dd0a356131ac97fa5560af3bbb98b60d4e`
  - Agentic order-evidence bundles: 456
  - Agentic input chunks covered: 24,675 of 24,675
  - Planned rich model calls: 423
  - Chunks per call: minimum 2, average 58.33, maximum 95
  - Exact rendered input tokens including dynamic tool schema: minimum 8,017, average 53,674.85, maximum 79,351
  - Reserved completion tokens per call: 24,000
  - Remaining context headroom at largest call: 152,649 tokens
  - Gemma tokenizer revision: `google/gemma-4-26B-A4B-it@4d7ae4984b7db7de8f8457170b3f1a419ee76d52`
  - Agentic batching concurrency: 1
  - Agentic input quarantines: 0
  - Deterministic agentic plan SHA-256: `fe99da2d4996eb634f9f2abb81c940deb0300303f01666af3f4f7f36b3f6125e`
  - Accepted agentic result files: 1,308
  - Agentic semantic regions: 13,889
  - Deterministically repaired regions: 5,420
  - Temporary call-local references removed: 7,946
  - Restored supplied fact candidates: 418
  - Restored supplied entity candidates: 59
  - Removed candidates outside the deterministic contract: 26 facts and 190 entity occurrences
  - Initial semantic retry targets: 1,254 regions across 759 result batches
  - Repaired agentic archive SHA-256: `3460f2c39106dc5ec5d2b3adc3ceadc433fc5b887354020eea5504fafb6a6124`
  - Targeted semantic retry batches: 255 accepted of 255
  - Second semantic retry batches: 248 accepted of 248, zero quarantines
  - Final canonical agentic regions: 13,597
  - Final canonical baseline regions retained: 10,736
  - Final canonical semantic-retry regions selected: 2,861
  - Residual explicitly flagged regions: 334
  - Residual quality flags: 296 deterministic fallbacks, 9 sparse regions, 30 under-cited amount conflicts
  - Final canonical agentic-region archive SHA-256: `9279ed9ad95cf1b4186f23d7abd270ec4524df1366c31e0cc90ff5d5c595939e`
  - Orders with recoverable unique IDs: 453
  - Provisional one-message/one-order records: 1
  - Current combined order total: 454
  - Order-resolution archive SHA-256: `0b32ab2a462cf3a64f2bc544515458b6ce544ef3818a0b3c8288a81e4f149a23`
  - Entity-resolution archive SHA-256: `99963af87ecf6d1fb63fc6fbff6f20f140dc9d37874c0cb70366363ec0c2ca6f`
  - Product-resolution archive SHA-256: `654230dd537ad4ed526521eddaf45b53b34ba69c27389b16df479cf23353cb1e`
  - Financial archive SHA-256: `3ef5de0ec2199199727f54f4539669c3fb1a3153981f25919ed0b9b279e4f078`
  - Reconciliations: 256 total; 57 exact, 199 explicitly conflicting
  - Canonical graph nodes: 48,784
  - Canonical graph relationships: 70,010
  - Temporal economic graph nodes: 53,983
  - Temporal economic graph relationships: 85,607
  - Financial events and evidence cells: 5,199 each
  - Multi-resolution financial chunks: 11,368
  - Entity histories: 529
  - Annual research windows: 7
  - Graph node archive SHA-256: `af4517cc4be79f6bb5a4878bc5b57976c71df1fb3db53e6f431c93ae046b07dd`
  - Graph relationship archive SHA-256: `3cb2c3607034d948942a17dda9734ef0344d95bd4479782df20d54ac7abd3093`
  - Embedded evidence nodes: 24,675 of 24,675 across 193 batches
  - Dense vector dimensions: 1,024
  - Live hybrid candidates: 30 dense, 30 lexical, 10 fused, 10 graph-expanded
  - Live evidence verification: verified
  - Canonical-oracle answer cases: 24
  - Answer status, exact answer, exact calculation, fact-count, citation-support, and abstention accuracy: 100%
  - Governed-answer local latency: P50 15.87 ms, P95 256.19 ms
  - Passing automated tests: 170

## Next actions — ordered

1. Pause and obtain the user's frontend visual system, graph-visualization references, page templates, and interaction requirements.
2. Build the Next.js graph explorer, evidence trace, transaction reconstruction, economic dashboard, and benchmark views against public-safe contracts only.
3. Create a human-reviewed natural-language golden set and public privacy-leakage review without publishing private cases.
4. Deploy the reviewed public projection and API to Aura/Vercel, then run the final end-to-end release audit.

## Decisions — append-only, newest first

### 2026-08-12 — Make canonical archives the oracle for financial answers

- Decision: Compile one temporal financial event and one evidence cell per canonical money component, extend the graph without mutating source truth, and evaluate Neo4j answers against expected values independently derived from immutable private archives. LLMs may propose research questions and prose, but deterministic code owns money, graph truth, validity time, evidence coverage, and privacy.
- Rationale: Evaluating a database query with values produced by the same query can hide schema, pagination, and calculation defects. An independent archive oracle proves storage/runtime agreement and makes partial lifetime totals impossible to present as verified answers.
- Alternatives rejected: LLM arithmetic; unbounded formula strings; grading Neo4j against its own rows; treating a row-limited page as a complete aggregate; publishing private goldens; silently inventing observation timestamps.
- Validation performed: The archive rebuild is byte-stable and mode `0600`; all 5,199 components have exact event/evidence coverage; two Neo4j loads end at 53,983 nodes and 85,607 relationships; 170 tests, Ruff, and strict mypy pass; all 24 canonical-oracle cases pass with 100% measured correctness and P50/P95 latency of 15.87/256.19 ms.
- Revisit trigger: A human-reviewed golden disagrees with the canonical oracle, a source correction requires temporal supersession, or the action budget cannot prove complete coverage for a supported aggregate.

### 2026-08-11 — Gate hybrid graph retrieval with evidence and hard execution budgets

- Decision: Retrieve independent dense and Lucene candidates, combine them through reciprocal-rank fusion, selectively expand the canonical graph, and accept answers only when every claim has source-addressable evidence. Constrain all online graph work through allowlisted parameterized Cypher, fact-specific source authority, read-only execution, and explicit action, depth, relationship, row, and candidate-path budgets.
- Rationale: Vector similarity is useful for discovery but cannot establish financial truth. Independent channels improve candidate recall, graph paths reconstruct economic context, and the verification boundary preserves the distinction between retrieval relevance and evidence-backed fact.
- Alternatives rejected: One retrieval channel; arbitrary generated Cypher; whole-subgraph serialization; database floating-point financial aggregation; treating one document role as universally authoritative; returning unsupported answers when evidence is incomplete or conflicting.
- Validation performed: All 24,675 evidence nodes carry 1,024-dimensional vectors. Neo4j reports the quantized HNSW index online. Live smoke tests returned 30 dense and 30 lexical candidates, fused and expanded 10 evidence paths, reached semantic regions and money components, and produced a verified citation pack. All 79 public tests, Ruff, and strict mypy pass.
- Portability note: Local Neo4j 5.26 uses its supported scalar-quantized HNSW implementation, not a native RaBitQ index. The retrieval adapter retains full vectors and can select native RaBitQ where a benchmarked backend exposes it.
- Revisit trigger: Retrieval ablations show a material Hit@k, MRR, latency, memory, or evidence-coverage improvement from different dimensions, HNSW parameters, quantization, fusion, reranking, or traversal budgets.

### 2026-08-11 — Resolve commerce truth conservatively before graph writes

- Decision: Resolve exact platform orders deterministically, retain one provisional order, scope merchants by platform and normalized trade name, keep outlets provisional without location identifiers, preserve every delivery name as an independent mention, restrict item identity to merchant scope, and reconcile money only within document and commercial scope.
- Rationale: Canonical graph richness is valuable only when merges and arithmetic remain reversible. Name similarity cannot prove outlet or person identity, identical dish names cannot prove cross-merchant comparability, and invoice/payment claims cannot prove bank settlement.
- Alternatives rejected: Dropping duplicate history evidence; globally merging merchants or delivery names; collapsing same-named dishes across restaurants; forcing all commercial legs into a synthetic zero-sum; hiding residual conflicts.
- Validation performed: Two deterministic executions produced stable private archives. The corpus resolves to 454 orders, 139 merchants, 423 provisional outlets, 4 legal entities, 4 mention-only delivery records, 320 item observations, 245 merchant items, 5,199 exactly covered money components, and 256 scoped reconciliations. All 73 tests, Ruff, and strict mypy pass.
- Revisit trigger: New exact address, GSTIN/FSSAI, platform merchant ID, user confirmation, reviewed item matching, or payment/bank evidence supports a stronger resolution status.

### 2026-08-11 — Select semantic retries by complete-bundle evidence risk

- Decision: Compare repaired baseline and second-pass retry candidates at complete bundle scope, weight under-cited amount conflicts above sparse structure and deterministic fallback prose, and replace a bundle only when its aggregate evidence-risk score improves.
- Rationale: A blanket retry replacement reduced total warning counts but could regress a previously safe financial explanation. Bundle-level selection preserves interdependent order evidence while making provenance correctness the primary optimization target.
- Alternatives rejected: Blindly replacing every retried region; selecting individual regions and splitting bundle context; minimizing raw warning count without distinguishing financial provenance risk; hiding residual flags through cosmetic rewriting.
- Validation performed: All 248 second-pass batches were accepted with zero quarantines. The final archive contains 13,597 unique deterministic regions, covers all 24,675 source chunks and all 5,199 money components exactly once, and retains 335 explicit non-blocking flags across 334 regions. Blocking alias, candidate-support, coverage, identity, and money invariants are zero. Archive SHA-256 is `9279ed9ad95cf1b4186f23d7abd270ec4524df1366c31e0cc90ff5d5c595939e`.
- Revisit trigger: A reviewed benchmark shows that a different evidence-risk weighting improves grounded retrieval without increasing unresolved financial provenance risk.

### 2026-08-10 — Repair model enrichment through a deterministic provenance boundary

- Decision: Preserve the original accepted model archive, write repaired results to a separate private archive, restore only candidates already supplied by deterministic extraction, remove candidates outside that contract, eliminate call-local retrieval aliases, and queue semantic-only warnings for selective retry.
- Rationale: Structural acceptance proved complete source and money coverage but did not guarantee exhaustive fact/entity transfer or retrieval-text hygiene. Deterministic evidence already contains enough information to repair those defects without spending tokens or weakening provenance.
- Alternatives rejected: Mutating the original model archive; rerunning all 1,308 calls; accepting temporary `cNNNN` aliases into embeddings; allowing grounded but contract-external model candidates into canonical graph state; hiding fallbacks by rewriting their labels.
- Validation performed: The repaired archive contains 1,308 valid results and 13,889 regions. A selective 255-batch retry reduced 1,254 semantic-warning regions to 418 explicitly flagged replacements. The compiled archive contains 14,023 deterministic region records; all 24,675 source chunks and all 5,199 money components occur exactly once, and bundle, alias, fact, entity, money, and relation invariant error counts are zero.
- Revisit trigger: A reviewed semantic retry introduces incomplete coverage, unsupported candidates, cross-bundle regions, or worse retrieval quality than the deterministic repair.

### 2026-08-07 — Make adaptive quantized retrieval a core Lunarbit capability

- Decision: Build the dense retrieval layer around Cohere Embed v4 Matryoshka
  dimensions, HNSW navigation, and RaBitQ quantization, followed by
  full-precision reranking and evidence verification.
- Rationale: Lunarbit's retrieval design should demonstrate production-grade
  systems thinking: one embedding model supports multiple operating points,
  HNSW supplies scalable graph navigation, and RaBitQ reduces vector memory and
  distance-computation cost while retaining a correctness reference.
- Scope: Benchmark 256/512/1024/1536 dimensions; HNSW `M`, construction,
  search-expansion settings; provider-native and RaBitQ quantization; exact and
  evidence-grounded retrieval quality; latency, build time, memory, and storage.
- Architectural invariant: compressed vectors are an ANN representation only.
  Canonical evidence, source provenance, deterministic values, and
  full-precision reranking remain authoritative.
- Revisit trigger: A backend lacks a production RaBitQ/HNSW implementation;
  the retrieval contract then falls back to provider-native quantization or
  full-vector HNSW without changing graph semantics.

#### MRL — adaptive representation resolution

- Cohere Embed v4 provides one embedding model with 256, 512, 1024, and 1536
  dimensional operating points.
- Lunarbit uses smaller representations for broad candidate search and larger
  representations for precision reranking, selected by query-family benchmarks.
- Arbitrary truncation of embeddings that were not trained for Matryoshka use is
  not part of the design.

#### HNSW — navigable dense retrieval graph

- HNSW is the dense candidate-navigation layer for evidence, item, entity, and
  finding indexes.
- Graph degree, construction effort, and search expansion are explicit tuning
  controls, recorded with each index build.
- HNSW results are fused with exact, lexical, metadata, and graph retrieval;
  evidence coverage remains the final answer gate.

#### RaBitQ — compact quantized ANN search

- RaBitQ is the vector-index compression and distance-estimation layer.
- It reduces vector memory and distance-computation cost while preserving a
  full-precision reranking path for correctness and auditability.
- Backend adapters may use native RaBitQ/HNSW support or the nearest supported
  quantized implementation without changing canonical graph semantics.

### 2026-08-05 — Require deterministic money-component coverage

- Decision: Require exact ordered source and money-component manifests; constrain batch, bundle, chunk, entity, and money reference values to deterministic batch evidence; cap regions at the input chunk count; and bound narrative and candidate-array sizes.
- Rationale: A structurally accepted four-chunk financial proposal covered every chunk but omitted all four money interpretations. The contract now makes that omission a quarantine, while provider-facing money fields use simple enums and the validator proves the exact component-to-chunk pairing.
- Alternatives rejected: Treating structural acceptance as quality acceptance; raising completion limits indefinitely; accepting partial tool arguments; weakening exact-source validation; making one call per chunk; launching the 423-call plan before a bounded financial pilot passes.
- Files/contracts affected: `src/lunarbit/agentic.py`, `tests/test_agentic.py`, `PLAN.md`, and `MEMORY.md`.
- Validation performed: Forty-seven tests, Ruff, and strict mypy pass. A non-private money-schema probe completed with HTTP 200 and a typed tool call. The full dry run covers 24,675 chunks in 423 calls with zero input quarantine and a 79,351-token maximum. The prior financial omission is now rejected deterministically; the latest private contract run did not persist a result and remains unverified.
- Revisit trigger: The bounded financial pilot still truncates, violates a deterministic candidate constraint, omits a money interpretation, or produces graph regions that do not outperform the deterministic baseline.

### 2026-08-04 — Bound rich output and constrain model evidence choices

- Decision: Require an exact ordered coverage manifest; constrain batch, bundle, chunk, and entity-candidate values to deterministic batch evidence; cap regions at the input chunk count; and bound narrative and candidate-array sizes.
- Rationale: Repeated eight-chunk money pilots showed that a 15k-token input could still exhaust a 24k completion budget. A compact coverage manifest removed the pathological repeated `allOf` schema, while a later completed response proved that prompt-only exact-entity guidance was insufficient. Machine constraints preserve graph richness while preventing repetition and normalized citations from crossing the validator boundary.
- Alternatives rejected: Raising completion limits indefinitely; accepting partial tool arguments; weakening exact-source validation; making one call per chunk; launching the 419-call plan before a bounded financial pilot passes.
- Files/contracts affected: `src/lunarbit/agentic.py`, `tests/test_agentic.py`, `PLAN.md`, and `MEMORY.md`.
- Validation performed: Forty-six tests, Ruff, and strict mypy pass. A non-private compact-schema probe completed with HTTP 200 and a typed tool call. The full dry run covers 24,675 chunks in 419 calls with zero input quarantine and a 77,881-token maximum. Private truncations and unsupported candidates were quarantined atomically; the bounded contract awaits its next live financial pilot.
- Revisit trigger: The bounded financial pilot still truncates, violates a deterministic candidate constraint, or produces graph regions that do not outperform the deterministic baseline.

### 2026-08-04 — Use Gemma 4 over Cloudflare SSE with bounded execution

- Decision: Use `@cf/google/gemma-4-26b-a4b-it` through Cloudflare's REST SSE interface with `stream: true`, `reasoning_effort: low`, `chat_template_kwargs.enable_thinking: false`, a 600-second socket/wall-clock deadline, and one required schema-constrained `submit_agentic_regions` function call.
- Rationale: GLM synchronous calls timed out or exhausted completion tokens in reasoning. Gemma exposes a 256,000-token context and streamed answer/reasoning deltas. Disabling thinking prevents reasoning from consuming the output budget, while SSE avoids waiting for a fully buffered response.
- Alternatives rejected: Treating the endpoint as WebSocket; combining JSON Mode with streaming when Cloudflare documents that JSON Mode does not support streaming; relying on unstable free-form JSON; accepting partial streams; retaining the GLM tokenizer after changing models; launching the full corpus before a pilot passes validation.
- Files/contracts affected: `src/lunarbit/agentic.py`, `scripts/run_agentic_chunking.py`, `tests/test_agentic.py`, `PLAN.md`, and `MEMORY.md`.
- Validation performed: Live SSE and tool-call delta shapes verified with `[DONE]`, finish reason, usage, and incremental function arguments. The official Gemma tokenizer dry run covers all 24,675 chunks in 330 calls with zero input quarantine after counting the tool schema. A two-chunk tool-call stream produced two regions and passed atomic validation. Forty-four tests, Ruff, and strict mypy pass.
- Revisit trigger: A representative pilot still fails typed output validation after privacy-safe diagnostics and prompt/schema refinement, or Cloudflare changes Gemma's streaming contract.

### 2026-08-03 — Expand enrichment to an 80k tokenizer-verified input budget

- Decision: Target 64,000 and cap 80,000 GLM input tokens using the pinned official tokenizer. Reserve 24,000 completion tokens and pack up to six template-compatible order bundles per sequential call with deterministic bundle isolation.
- Rationale: The earlier 32-chunk/32k-character profile underused a 131,072-token reasoning model and required 1,107 calls. Larger compatible cohorts give the model full order, invoice, table, fact, money, and provenance context while retaining 29,296 tokens of headroom at the largest current request.
- Alternatives rejected: Keeping the 1,107-call character profile; estimating tokens only from characters; filling the entire context window; mixing incompatible document-role cohorts; dropping metadata to reduce input size; permitting model output to merge orders.
- Files/contracts affected: `src/lunarbit/agentic.py`, `scripts/run_agentic_chunking.py`, agent dependencies, and agentic contract tests.
- Validation performed: The pinned tokenizer plans 307 calls covering all 24,675 chunks with zero quarantine. Exact rendered prompts peak at 77,776 input tokens; 37 tests plus Ruff and strict mypy pass. No live inference was made because the environment variables remain unavailable.
- Revisit trigger: The live pilot shows truncation, cross-bundle confusion, weak graph regions, high validation failure, or actual Cloudflare usage materially differs from pinned-tokenizer estimates.

### 2026-08-03 — Use bounded order-relevant GLM enrichment batches

- Decision: Use Cloudflare Workers AI `@cf/zai-org/glm-4.7-flash` for Phase 2B. Send medium order-relevant batches sequentially: target 18,000 and cap 32,000 user-prompt characters, at most 32 chunks and six mail-only bundles, and never fewer than two chunks.
- Rationale: One request per primitive loses order-level relationships, while a whole-corpus prompt dilutes evidence and weakens graph-oriented chunking. Message-plus-attachment bundles preserve order context; same-cohort packing handles otherwise singleton mail orders without cross-order merging.
- Alternatives rejected: One API call per chunk; one full-corpus request; concurrent unbounded calls; arbitrary cross-order packing; trusting model JSON without deterministic validation.
- Files/contracts affected: `src/lunarbit/agentic.py`, `scripts/run_agentic_chunking.py`, `.env.example`, and agentic contract tests.
- Validation performed: Full-corpus dry run covers all 24,675 chunks in 1,107 batches with no singleton calls or quarantined inputs; 34 tests plus Ruff and strict mypy pass. No live call was made because credentials are absent.
- Revisit trigger: Reviewed pilot results show poorer region quality, unacceptable validation failure rates, excessive output truncation, or a better model wins the same private benchmark.

### 2026-08-03 — Keep rich chunks candidate-only until deterministic resolution

- Decision: Chunking may propose facts, entity mentions, money components, graph candidates, and retrieval text, but none becomes canonical identity, financial truth, or graph state until later deterministic resolution and reconciliation stages approve it.
- Rationale: Rich semantic extraction is useful for retrieval and downstream reasoning, but candidate confidence does not prove identity, settlement, funding, or arithmetic correctness.
- Alternatives rejected: Writing chunker output directly to the canonical graph; allowing partial acceptance of invalid model output; inventing persistent IDs in prompts.
- Files/contracts affected: `src/lunarbit/chunk.py`, rich chunk Pydantic contracts, `scripts/build_chunks.py`, and `scripts/run_evals.py`.
- Validation performed: Evaluated 1,219 sources and 24,675 chunks with zero invalid or unsupported candidates; malformed synthetic proposals quarantine atomically.
- Revisit trigger: Phase 3 introduces reviewed resolution decisions or Phase 4 introduces reconciled financial components.

### 2026-08-03 — Accept historical Swiggy IDs only from labelled evidence

- Decision: Label-aware Swiggy extraction accepts 11–15 digit order IDs, including historical `Order no: #…` forms; unlabelled digit sequences and 16-digit invoice/attachment tokens remain ineligible as strong order IDs.
- Rationale: The private corpus contains valid historical 11- and 12-digit Swiggy IDs as well as current 15-digit IDs. Restricting all Swiggy orders to 15 digits incorrectly left evidence-backed orders provisional.
- Alternatives rejected: Keeping the 15-digit-only rule; accepting arbitrary nearby numbers; trusting the manifest's 16-digit field.
- Files/contracts affected: ingestion order-ID patterns, message chunks, order evidence, and current metrics.
- Validation performed: 453 ordinary evidence records now map to 453 unique platform IDs with no duplicates or ambiguous mail candidates; one message remains genuinely provisional and the total stays 454.
- Revisit trigger: New labelled evidence demonstrates another historical format or contradicts an extracted ID.

### 2026-08-03 — Keep PDF processing deterministic and quarantine-first

- Decision: Canonical page and document artifacts are produced entirely by deterministic scripts. Native extraction is accepted only when text, table, and image inspection complete without structural issues; failed pages are marked OCR-required and the document is quarantined rather than silently accepted.
- Rationale: Page coordinates, source precision, table alignment, and evidence provenance must be reproducible before any agentic interpretation begins.
- Alternatives rejected: Direct LLM parsing of opaque PDFs; unconditional OCR; accepting partial extraction without a quality signal.
- Files/contracts affected: `src/lunarbit/pdf.py`, Phase 1 Pydantic contracts, `scripts/build_json.py`, and private processed artifacts.
- Validation performed: Processed all 763 PDFs and 857 pages twice with identical archive hashes; all 763 documents passed native quality checks, with 620 tables and 1,668 images recorded.
- Revisit trigger: A future source page is quarantined, requiring a region/page-scoped OCR adapter and new golden regression.

### 2026-08-03 — Count mail-only evidence as provisional orders

- Decision: Each relevant email without a PDF represents one provisional order unless later evidence proves duplication. PDFs attached to one ordinary order email are bundled as evidence for one order, not counted individually. Multi-order history reports are expanded by row-level order ID and deduplicated against ordinary order evidence.
- Rationale: Email bodies contain order evidence even when invoices are absent, while multiple PDFs commonly describe different financial scopes of the same order.
- Alternatives rejected: Dropping attachmentless emails; counting every PDF as an order; counting aggregate history reports as one order.
- Files/contracts affected: Future source-message, document, order-candidate, and bundle contracts.
- Validation performed: Reconciled 456 relevant emails, 763 PDFs, ordinary PDF bundles, two history reports, and mail-only messages. Current total is 454 orders: 427 ID-resolved and 27 provisional.
- Revisit trigger: Phase 1 resolves a provisional record or proves that two source messages describe the same order.

### 2026-08-03 — Repository, privacy, and commit-history standards

- Decision: Use `https://github.com/simon-derock/Lunarbit.git` as the repository. `PLAN.md` and `MEMORY.md` may be committed. Never commit private PDFs, EML/mbox files, archive ZIPs, private processed JSON, unredacted page renders, secrets, or raw personal data.
- Rationale: The repository is intended to be public while the source archive contains direct personal and third-party identifiers.
- Alternatives rejected: Relying on developer memory or manual staging discipline alone.
- Files/contracts affected: `.gitignore`, future privacy checks, commit workflow, and public projection.
- Validation performed: Added a deny-by-default data ignore policy and explicit source-file exclusions.
- Revisit trigger: A reviewed public-data allowlist and automated privacy test permit a specific sanitized asset.

### 2026-08-03 — Professional, test-driven commit history

- Decision: Commit messages must read like concise senior-engineer work: imperative, specific, and focused on intent and constraints. Use conventional scopes where natural, for example `test(ingestion): define source inventory invariants` followed by `feat(ingestion): normalize Gmail source bundles`. Do not use AI-style narration, generated-by notices, or AI co-author trailers.
- Rationale: The public history must demonstrate engineering judgment and test-driven development.
- Alternatives rejected: Vague messages such as `updates`, oversized mixed commits, or AI-attributed commit text.
- Files/contracts affected: All future commits and pull requests.
- Validation performed: Policy recorded before repository initialization.
- Revisit trigger: Project maintainers adopt a different documented commit convention.

### 2026-08-03 — Treat acquisition manifests as hints, not commerce truth

- Decision: Preserve existing manifest values immutably, but independently extract labelled order IDs from PDF or email evidence and record conflicts.
- Rationale: In 100 of 152 ordinary Swiggy invoice bundles, the manifest stores a 16-digit attachment/invoice token while the PDF labels a different 15-digit platform order ID.
- Alternatives rejected: Trusting manifest `orderId` values or silently replacing them.
- Files/contracts affected: Future source normalization and order-candidate schemas.
- Validation performed: Compared every existing Swiggy invoice bundle against labelled PDF fields.
- Revisit trigger: A new acquisition-manifest version provides a validated field with explicit semantics.

## Known failures / do not repeat

- Do not count PDFs as orders; several PDFs can document one order.
- Do not ingest both a Takeout ZIP and its byte-identical extracted mbox.
- Do not trust the existing Swiggy manifest `orderId` without evidence-level validation.
- Do not discard attachmentless emails; they are provisional order evidence.
- Do not add the 73 history-report rows again when matching ordinary order evidence exists.
- Do not repeat the incorrect ₹59.16 discount residual; the supplied Zomato bundle yields ₹37.16.
- Do not infer stable delivery identity from a repeated name alone.
- Do not expose proprietor, customer, or delivery-person names publicly.
- Do not classify a sender from its display name; parse and validate the actual sender domain.
- Do not treat a MIME body part with no filename as `attachment.pdf`; require PDF MIME type, a real `.pdf` filename, or a PDF byte signature.
- Do not infer merged-cell spans from consecutive missing grid slots; derive spans from detected cell geometry.
- Do not accept a failed native page silently; mark it OCR-required and quarantine its document.
- Do not assume every Swiggy order ID has 15 digits; accept historical lengths only behind an explicit order label.
- Do not promote chunk candidates directly into canonical identity, finance, or graph records.
- Do not partially accept malformed model output; quarantine the complete proposal set for that source.
- Do not send one deterministic chunk per model call or dump the full corpus into one context.
- Do not allow shared mail-only calls to merge separately marked orders into one semantic region.
- Do not run uncapped or concurrent private model calls; require `--max-calls` and concurrency `1`.
- Do not flatten HTML block boundaries before mail-field extraction.
- Use `python3` in this environment; the unversioned `python` command is unavailable.
- Do not use LLM or floating-point arithmetic for canonical money.
- Do not vectorize IDs, dates, or standalone amounts.
- Do not implement custom BM25 using Neo4j dense vectors.
- Do not label invoice settlement assertions as bank-confirmed.
- Do not mount private GraphRAG routes in a browser-facing service; use `scripts/serve_public_api.py` and an explicit non-wildcard CORS allowlist.

### 2026-08-20 — Isolate the public GraphRAG boundary

- Decision: The public API is a separate process from authenticated private GraphRAG. It may return a synthetic mirror or aggregate Neo4j topology, but it never mounts private retrieval or answer routes.
- Rationale: A browser deployment must not acquire private-model credentials, source records, canonical graph properties, or an authenticated path merely to render the public demonstration.
- Alternatives rejected: Running the shared private launcher for public traffic; redacting individual canonical nodes in the browser; wildcard CORS; returning a plausible answer for arbitrary public questions.
- Files/contracts affected: `src/lunarbit/api.py`, `src/lunarbit/public_projection.py`, `scripts/serve_public_api.py`, and the Nexus Insight FastAPI adapter.
- Validation performed: Public payload validation, route-absence tests, deterministic verified/abstained showcase tests, projection-query inspection, bounded-cache expiry tests, 180 committed Python tests, and a local public-service smoke check.
- Revisit trigger: A manually privacy-reviewed public fixture or a new aggregate class needs exposure; extend the allowlisted public contract first and add a leakage regression before serving it.

## Open questions

- Which deterministic fallback fingerprint should identify the one remaining provisional order until stronger evidence is available?
- Should reviewed public fixtures be synthetic, manually redacted, or a combination of both?

## Important commands

```bash
UV_CACHE_DIR=/tmp/lunarbit-uv-cache uv sync --extra dev
UV_CACHE_DIR=/tmp/lunarbit-uv-cache uv sync --extra dev --extra agent
.venv/bin/ruff check src scripts tests
.venv/bin/ruff format --check src scripts tests
.venv/bin/mypy src scripts
.venv/bin/pytest -q
.venv/bin/python scripts/build_json.py --input data --output data/processed
.venv/bin/python scripts/build_json.py --input data --output data/processed --inventory-only
.venv/bin/python scripts/build_chunks.py --input data/processed
.venv/bin/python scripts/run_agentic_chunking.py --input data/processed
.venv/bin/python scripts/run_agentic_chunking.py --input data/processed --execute --max-calls 3
.venv/bin/python scripts/run_evals.py --suite chunking --input data/processed
```
