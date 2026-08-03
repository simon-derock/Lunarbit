# MEMORY.md

## Session handoff

- Last updated: 2026-08-03
- Active phase: Phase 1 deterministic PDF processing complete; Phase 2 agentic chunking next.
- Current branch: `main`
- Repository: `https://github.com/simon-derock/Lunarbit.git`
- Last verified implementation commit: `cf081cc` (`feat(extraction): emit deterministic PDF artifacts`).
- Last passing checks: Ruff lint/format, strict mypy, 15 pytest tests, and two byte-identical complete private-corpus artifact builds.

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
  - Recorded TDD progression as separate red-test and green-implementation commits.
- In progress: None; Phase 2 is ready to begin.
- Blocked: None.
- Schema/model/index versions in use: Phase 1 extraction version `1.0.0`, package version `0.1.0`; graph/index versions remain design-only.
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
  - Orders with recoverable unique IDs: 427
  - Provisional one-message/one-order records: 27
  - Current combined order total: 454

## Next actions — ordered

1. Add failing tests for Phase 2 rich-chunk contracts, routing, source-region provenance, validation, and quarantine.
2. Implement deterministic chunk-strategy routing over structured document JSON, never opaque PDFs.
3. Add candidate facts and entity mentions while preserving document/page/block evidence links.
4. Build the golden chunking benchmark and require complete financial/entity facts to remain source-linked.
5. Replace provisional identities only where stronger evidence proves an order ID or duplicate relationship.

## Decisions — append-only, newest first

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
- Use `python3` in this environment; the unversioned `python` command is unavailable.
- Do not use LLM or floating-point arithmetic for canonical money.
- Do not vectorize IDs, dates, or standalone amounts.
- Do not implement custom BM25 using Neo4j dense vectors.
- Do not label invoice settlement assertions as bank-confirmed.

## Open questions

- Which deterministic fallback fingerprint should identify the 27 provisional orders until stronger evidence is available?
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
```
