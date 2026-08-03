# MEMORY.md

## Session handoff

- Last updated: 2026-08-03
- Active phase: Phase 2B Cloudflare adapter and complete medium-batch plan implemented; live model benchmark pending credentials.
- Current branch: `main`
- Repository: `https://github.com/simon-derock/Lunarbit.git`
- Last verified implementation commit: `64687fe` (`feat(chunking): add validated Cloudflare batch enrichment`).
- Last passing checks: Ruff lint/format, strict mypy, 34 pytest tests, the complete deterministic chunking benchmark, and the full-corpus agentic dry run.

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
  - Selected Cloudflare Workers AI `@cf/zai-org/glm-4.7-flash` for Phase 2B candidate enrichment.
  - Added deterministic order-relevant batching with table preservation, mail-only cohort packing, hard prompt limits, and no one-chunk calls.
  - Added typed model-response validation for complete coverage, exact-source entities and relations, and cross-order isolation.
  - Added a sequential, opt-in runner that requires an explicit call cap and writes validated results privately with mode `0600`.
  - Recorded TDD progression as separate red-test and green-implementation commits.
- In progress: None; the Phase 2B dry-run plan is ready for a small live pilot.
- Pending external input: `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_AUTH_TOKEN` are not set, so no private evidence has been sent and no live model result exists yet.
- Schema/model/index versions in use: extraction `1.0.0`, chunk schema `1.0.0`, package `0.1.0`; graph/index versions remain design-only.
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
  - Planned medium model calls: 1,107
  - Chunks per call: minimum 2, average 22.29, maximum 32
  - User-prompt characters per call: minimum 2,722, average 16,368.58, maximum 30,008
  - Agentic batching concurrency: 1
  - Agentic input quarantines: 0
  - Deterministic agentic plan SHA-256: `422cb28faf195ba9a6579984cad14732aeca9e149751dc4770ba36a1f162454d`
  - Orders with recoverable unique IDs: 453
  - Provisional one-message/one-order records: 1
  - Current combined order total: 454

## Next actions — ordered

1. Set the two Cloudflare credentials locally and run a three-call live pilot with `--execute --max-calls 3`.
2. Manually review pilot regions against the supplied PDFs and representative mail-only evidence before expanding the call cap.
3. Add private golden expectations for benchmark-designated hard cases, conflicts, and future unknown templates.
4. Compare model-assisted proposals with the deterministic baseline; accept only measured improvements after typed validation.
5. Begin Phase 3 order bundling and entity resolution only after golden financial/entity facts remain source-linked.

## Decisions — append-only, newest first

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

## Open questions

- Which deterministic fallback fingerprint should identify the one remaining provisional order until stronger evidence is available?
- Should reviewed public fixtures be synthetic, manually redacted, or a combination of both?

## Important commands

```bash
UV_CACHE_DIR=/tmp/lunarbit-uv-cache uv sync --extra dev
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
