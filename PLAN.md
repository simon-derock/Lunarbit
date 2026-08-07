# Lunarbit — Evidence-Verifiable Personal Commerce GraphRAG

> **A public, privacy-safe, six-year personal-commerce intelligence system built from Zomato and Swiggy documents.**

**Version:** 2.0  
**Updated:** 2026-08-03  
**Owner:** Philip Simon Derock  
**Repository:** `lunarbit`  
**Primary objective:** Produce an exceptional live public demo and a defensible AI Engineer portfolio project.  
**Primary data:** Approximately 500+ Zomato, Swiggy Food, and Swiggy Instamart PDFs collected over several years.  
**Primary deployment:** Neo4j AuraDB + Python/FastAPI/LangGraph + Next.js + Vercel.  
**Primary embedding model:** Cohere `embed-v4.0`, with dimension selected by benchmark.  

---

## 1. Executive vision

Lunarbit converts fragmented food-delivery and grocery documents into a temporal, evidence-verifiable Neo4j knowledge graph.

It is not:

- a PDF chatbot;
- a generic expense dashboard;
- an unverified Text-to-Cypher demo;
- a decorative graph visualization;
- a banking core or payment processor;
- a claim that the project outscales Zomato, Swiggy, or regulated fintech systems.

It is:

> **A user-owned personal-commerce reconstruction and economic-intelligence system that separates source claims, normalized facts, deterministic calculations, identity resolutions, unresolved residuals, and analytical findings—and lets every important answer be replayed back to source evidence.**

The project must demonstrate senior-level capability in:

- PDF and layout processing;
- agentic chunking;
- graph ontology design;
- deterministic financial reconciliation;
- privacy-aware identity resolution;
- dense, lexical, exact, and graph-native retrieval;
- LangGraph orchestration;
- evidence-grounded reasoning;
- quantitative economic analysis;
- evaluation-driven development;
- public product engineering.

---

## 2. Public-demo-first product thesis

The live public demo is not a secondary presentation layer. It is the primary product outcome.

A recruiter should be able to open Lunarbit and, within two minutes:

1. understand what six years of records were reconstructed;
2. ask a difficult natural-language question;
3. see a direct answer and deterministic calculation;
4. inspect the graph path used;
5. open a redacted source-evidence crop;
6. inspect benchmark results and known limitations;
7. understand why this is more than a standard RAG application.

### 2.1 Defensible pioneer claim

Lunarbit must not claim universal superiority over internal platform or fintech infrastructure.

The defensible claim is:

> **Lunarbit combines cross-platform order reconstruction, evidence-level provenance, financial decomposition, temporal graph reasoning, privacy-preserving identity resolution, personal economic indices, and source-verifiable GraphRAG in one user-owned public system.**

Its pioneer status comes from the integration and demonstrability of these capabilities, not from graph size or the number of frameworks.

### 2.2 Resume-grade positioning

> Built Lunarbit, a public evidence-verifiable personal-commerce GraphRAG system that transformed 500+ Zomato and Swiggy documents into a temporal Neo4j knowledge graph using layout-aware agentic chunking, privacy-safe entity resolution, Cohere Matryoshka embeddings, hybrid graph retrieval, deterministic financial reconciliation, and source-grounded economic reasoning.

Measured metrics must replace adjectives before this statement appears on the final resume.

---

## 3. What the supplied samples prove

The initial golden corpus contains five supplied PDFs. These samples define the minimum ontology and reconciliation requirements.

### 3.1 Zomato order bundle: Order `8368252638`

#### Customer summary

Source: `Order_ID_8368252638(1).pdf`, pages 1–2.

Observed facts include:

- order timestamp: 18 July 2026, 02:01 PM;
- merchant: C3 Cafe;
- delivery-partner name mention;
- Chicken Zinger Burger: ₹227;
- Hot & Crispy Chicken: ₹107;
- taxes: ₹14.24;
- delivery charge subtotal: ₹22;
- platform fee: ₹14.90;
- Gold free-delivery benefit: ₹22;
- `MEALX` coupon: ₹140;
- customer total: ₹223.14.

Customer-facing reconciliation:

```text
Items gross                         ₹334.00
Taxes                                ₹14.24
Delivery charge                      ₹22.00
Platform fee                         ₹14.90
Gold delivery benefit               -₹22.00
MEALX coupon                        -₹140.00
                                     ───────
Customer total                       ₹223.14
```

#### Restaurant invoice

Source: `Order_Invoice8368252638(1).pdf`, page 1.

Observed facts include:

- restaurant name: C3 Cafe;
- private legal proprietor name;
- GSTIN and FSSAI identifiers;
- item-level gross values;
- item-level discounts;
- net taxable values;
- item-level CGST and SGST;
- restaurant invoice total: ₹242.72;
- document assertion that ₹242.72 was settled digitally.

Restaurant-side reconciliation:

```text
Items gross                         ₹334.00
Restaurant-observed discount       -₹102.84
                                     ───────
Net taxable value                   ₹231.16
Restaurant CGST + SGST               ₹11.56
                                     ───────
Restaurant invoice total            ₹242.72
```

#### Platform-fee invoice

Source: `User_Charge_Invoice8368252638(1).pdf`, page 1.

Observed facts include:

- issuer: Eternal Limited, formerly Zomato Limited;
- platform-fee taxable amount: ₹14.90;
- CGST: ₹1.34;
- SGST: ₹1.34;
- printed total: ₹17.582;
- document assertion that the amount was settled digitally.

The source precision of `17.582` must be preserved even when a display layer rounds to two decimals.

#### Correct discount-residual finding

```text
Customer-visible coupon             ₹140.00
Restaurant-observed discount       -₹102.84
                                     ───────
Unexplained discount residual        ₹37.16
```

The canonical label is initially:

```text
UNEXPLAINED_DISCOUNT_RESIDUAL
funding_status = UNRESOLVED
amount = 37.16
```

It must not be silently labeled platform-funded. Candidate explanations may include platform funding, membership benefit, bank offer, wallet credit, missing evidence, or document-scope differences.

### 3.2 Swiggy food invoice

Source: `taco_240334882204256_merged(1).pdf`, page 1.

The schema must support:

- invoice issued by Swiggy on behalf of a restaurant;
- present and former corporate names;
- restaurant GSTIN and FSSAI;
- restaurant-service HSN/SAC;
- item gross, discount, and net assessable value;
- packing charge;
- CGST and SGST;
- invoice total.

### 3.3 Swiggy Instamart invoice

Source: `taco_241432382897862_merged(1).pdf`, page 1.

The schema must support:

- grocery seller and outlet;
- multiple packaged products;
- quantity and unit of measure;
- product-level HSN codes;
- gross taxable value;
- item discount;
- net taxable value;
- CGST, SGST, cess, and additional cess fields;
- separately decomposed handling fee;
- food-safety and tax registrations.

### 3.4 Consequence

Lunarbit requires one unified ontology for:

- restaurant food;
- grocery products;
- platform services;
- merchant services;
- multiple documents per order;
- legal and brand identities;
- promotions and membership benefits;
- person mentions and uncertain identities;
- source-specific monetary truth.

---

## 4. Project constitution

These rules are non-negotiable.

1. Every important public claim must be traceable to source evidence or explicitly labeled as a scenario.
2. Source text and source precision must never be silently corrected.
3. Observed, normalized, resolved, calculated, inferred, and simulated values must remain distinguishable.
4. LLMs may interpret, route, summarize, and propose; deterministic code owns arithmetic and validation.
5. Every entity merge must be scored, reviewable, and reversible.
6. A repeated name does not prove a repeated person.
7. Every public identity transformation must be deterministic and privacy-reviewed.
8. No raw private invoice is served by the public application.
9. Exact identifiers, dates, and money are queried with deterministic indexes and Cypher—not semantic similarity alone.
10. Unknown, conflicting, or incomplete evidence remains visible.
11. Every metric has one governed definition and version.
12. Every benchmark claim is reproducible.
13. Project complexity must serve a measured capability; architecture theatre is prohibited.
14. `PLAN.md` defines intended architecture; tests and schemas define executable contracts; `MEMORY.md` records current state and rationale.

---

## 5. Scope

### 5.1 Version 1 scope

- historical processing of 500+ supplied PDFs;
- Zomato food orders;
- Swiggy food orders;
- Swiggy Instamart orders;
- order summaries and receipts;
- restaurant/seller invoices;
- platform and user-charge invoices;
- packing, handling, delivery, platform, tax, discount, benefit, and refund components where present;
- template detection and drift handling;
- multi-document order bundling;
- rich agentic chunking;
- entity and alias resolution;
- financial reconciliation and residual detection;
- Neo4j Aura graph construction;
- exact, full-text, dense, hybrid, and graph retrieval;
- natural-language query planning;
- redacted evidence replay;
- economic analytics and deterministic scenarios;
- public deployment.

### 5.2 Deferred scope

- bank/card statement reconciliation;
- merchant settlement statements;
- live Gmail watcher;
- real-time event streaming;
- multi-user SaaS;
- unrestricted user PDF uploads;
- causal inference from observational order history;
- full MCTS/GRPO training from Graph-O1;
- external SPLADE infrastructure;
- payment or refund execution.

### 5.3 Explicit non-goals

- pretending an invoice proves bank settlement;
- building a regulated accounting system;
- forcing every order into a synthetic global double-entry balance;
- identifying third-party people publicly;
- claiming fraud;
- unrestricted Text-to-Cypher writes;
- claiming AGI;
- using embeddings for exact financial computation.

---

## 6. Final system architecture

```text
Private PDF archive
        ↓
Phase 1 deterministic Python extraction
PDF → manifest + page JSON + document JSON + Markdown preview
        ↓
Phase 2 LLM-assisted agentic chunking
layout-aware semantic chunks + candidate facts + entity mentions
        ↓
Deterministic validation and normalization
        ↓
Entity resolution + order bundling + financial reconciliation
        ↓
Cohere embeddings
        ↓
Neo4j AuraDB
  ├── graph entities and relationships
  ├── exact/range indexes
  ├── Lucene full-text indexes
  ├── vector indexes
  ├── evidence graph
  └── economic intelligence artifacts
        ↓
LangGraph query workflow
exact Cypher + lexical + dense + graph traversal + rerank + verification
        ↓
FastAPI service
        ↓
Next.js public frontend on Vercel
```

### 6.1 Final stack

```text
Python 3.12+
Pydantic v2
PyMuPDF and/or pdfplumber
OCR fallback only where required
LangGraph
Neo4j AuraDB
Neo4j Python driver
neo4j-graphrag-python where useful
Cohere Embed v4
Cohere Rerank
FastAPI
Next.js
Vercel
pytest + Hypothesis
```

### 6.2 Storage decision

For the public portfolio version:

- Neo4j AuraDB is the operational graph and retrieval store.
- Local JSON/JSONL is the rebuildable canonical intermediate archive.
- The private PDF archive remains local and gitignored.
- Public evidence crops are manually redacted and deployed separately.
- PostgreSQL, Kafka, and external vector stores are not required for version 1.

The graph must always be rebuildable from processed JSON and deterministic scripts.

---

## 7. Phase 1 — deterministic PDF processing

The first phase is script-based and does not require agentic interpretation.

### 7.1 Pipeline

```text
scan PDFs
→ hash and deduplicate
→ classify probable platform/document type
→ extract native text and layout
→ extract tables
→ OCR only failed regions/pages
→ create page-level JSON
→ create document-level JSON
→ create Markdown inspection preview
→ run structural quality checks
```

### 7.2 Canonical formats

JSON/JSONL is canonical.

Markdown is only a human-readable inspection artifact because it cannot reliably preserve:

- page coordinates;
- table cells;
- row/column alignment;
- source precision;
- extraction method;
- confidence;
- reading order;
- evidence provenance.

### 7.3 Recommended local output

```text
data/processed/<document_id>/
├── manifest.json
├── document.json
├── document.md
├── pages.jsonl
└── evidence/
    └── page-render-001.webp
```

Do not create a deep folder hierarchy per page unless actual processing requires it.

### 7.4 Document manifest

```text
DocumentManifest {
  document_id
  sha256
  source_filename
  file_size
  page_count
  probable_platform
  probable_document_type
  probable_order_id_private
  template_signature
  native_text_available
  ocr_required
  extraction_version
  processing_status
  privacy_status
}
```

### 7.5 Page and layout model

```text
PageRecord {
  document_id
  page_number
  width
  height
  text_blocks[]
  key_value_blocks[]
  tables[]
  images[]
  reading_order[]
  extraction_method
  quality_profile
}
```

Tables must preserve:

- table identifier;
- row and column indexes;
- header-cell links;
- merged-cell information where available;
- bounding boxes;
- raw cell text;
- normalized cell text;
- parser confidence.

### 7.6 Script commands

```bash
python scripts/build_json.py --input data/raw --output data/processed
python scripts/run_evals.py --suite extraction
```

### 7.7 Phase 1 acceptance criteria

- all five supplied golden PDFs produce deterministic JSON;
- source amounts and source precision are preserved;
- item rows remain aligned with headers;
- documents are classified correctly;
- duplicate reruns are idempotent;
- failed pages are quarantined rather than silently accepted;
- a reviewer can compare JSON against the rendered PDF page.

---

## 8. Phase 2 — rich agentic chunking

Agentic chunking operates on structured document JSON, not directly on an opaque PDF whenever avoidable.

### 8.1 Goal

Create high-quality chunks that preserve complete commercial or financial meaning and are useful for:

- graph construction;
- exact querying;
- semantic retrieval;
- evidence replay;
- entity resolution;
- financial reconciliation;
- economic analysis.

### 8.2 Chunking strategy selection

```text
Known order-summary template
→ order-component chunker

Known restaurant/seller invoice
→ table-preserving invoice chunker

Known platform-fee invoice
→ fee-and-tax block chunker

Unknown template
→ vision/layout decomposition
→ schema validation
→ quarantine or human review
```

The LLM selects or proposes a strategy. Deterministic validators approve the result.

### 8.3 Chunk types

```text
ORDER_HEADER
ORDER_PARTIES
DELIVERY_MENTION
ITEM_TABLE
ITEM_ROW
SUBTOTAL
DISCOUNT_BLOCK
MEMBERSHIP_BENEFIT
PACKING_CHARGE
HANDLING_FEE
DELIVERY_CHARGE
PLATFORM_FEE
TAX_BLOCK
PAYMENT_ASSERTION
REFUND_BLOCK
LEGAL_ENTITY_BLOCK
REGULATORY_BLOCK
TERMS_BLOCK
```

### 8.4 Rich chunk schema

```text
EvidenceChunk {
  chunk_id
  document_id
  page_number
  chunk_type
  semantic_role
  financial_role

  raw_text_private
  normalized_text
  semantic_summary
  embedding_text

  bounding_box
  reading_order
  table_id
  row_index
  column_headers[]
  parent_region_id

  entity_mentions[]
  candidate_assertions[]
  candidate_money_components[]
  query_families[]
  graph_candidates[]

  source_hash
  extraction_method
  extraction_confidence
  chunk_completeness
  validation_status
  privacy_class

  embedding_model
  embedding_dimension
  embedding_version
}
```

### 8.5 Multi-representation rule

Every important chunk may contain:

1. raw source representation;
2. normalized lexical representation;
3. semantic summary;
4. deliberately composed embedding text;
5. structured facts;
6. source coordinates;
7. supported query families.

One vector is created from the composed `embedding_text`. Do not generate separate vectors merely for raw and normalized variants unless evaluation proves a benefit.

### 8.6 Reading-order rule

Persist `reading_order`, `parent_region_id`, and table coordinates.

Do not persist both `prev_chunk_id` and `next_chunk_id` by default. Adjacent chunks can be derived from document and reading order, avoiding reciprocal consistency problems.

### 8.7 Model-assisted batching contract

Phase 2B uses Cloudflare Workers AI model `@cf/google/gemma-4-26b-a4b-it` as a candidate-only semantic enrichment layer over deterministic chunks.

Batching must preserve commercial context without saturating the model context window:

- group each PDF-backed message and its attachments as one order-evidence bundle;
- batch up to six order bundles only when platform, category, evidence kind, and document-role cohort match;
- preserve explicit bundle boundaries and prevent model output from merging separate orders into one region;
- keep table parents and rows together when they fit the hard limit;
- count with the pinned official Google Gemma 4 tokenizer rather than a character heuristic;
- target 64,000 input tokens and enforce an 80,000-token input ceiling;
- reserve up to 24,000 completion tokens inside Gemma's 256,000-token context window;
- cap batches at 512 primitives and six bundles;
- require at least two chunks per call;
- execute sequentially with concurrency `1` over Cloudflare's documented HTTP Server-Sent Events interface;
- require a complete `[DONE]` event, reject length-limited output, disable thinking through Gemma's chat-template setting, and enforce a 600-second socket and wall-clock deadline;
- require one `submit_agentic_regions` function call whose JSON Schema is generated from the typed response contract, and count that schema in every input budget;
- require an exact ordered coverage manifest, constrain batch IDs, bundle IDs, chunk IDs, and entity candidates to supplied evidence, and independently validate region-level coverage;
- require an exact ordered money-component manifest and one source-linked interpretation for every deterministic money candidate;
- bound region counts, narrative lengths, and candidate arrays so rich graph output cannot grow without limit or repeat evidence until truncation;
- never send the entire corpus or make one request per deterministic chunk.

Each input primitive includes all deterministic representations and graph-relevant metadata: raw and normalized text, semantic and embedding text, page and bounding-box provenance, reading order, table hierarchy, candidate facts, entity mentions, money candidates, query families, graph candidates, source hash, extraction method/confidence, completeness, validation, and privacy state.

The model may propose coherent semantic regions, retrieval text, source-exact facts and entities, interpretations of existing money candidates, query families, governed graph relations, conflict flags, and uncertainty notes. A deterministic validator rejects unknown chunk IDs, partial or duplicate coverage, unsupported source spans, unsupported money references, unsupported exact-value candidates, cross-bundle regions, and malformed output. The model never creates persistent IDs or writes canonical graph state.

The Gemma-tokenizer-verified full-corpus dry run plans 423 calls for 24,675 chunks, averages 58.33 primitives and 53,674.85 input tokens per call, reaches 79,351 input tokens at maximum, reserves 24,000 completion tokens, and leaves 152,649 tokens of context headroom at the largest call. No input is skipped or quarantined. The dynamic tool-schema overhead is included. A two-chunk live SSE pilot produced two regions and passed complete coverage, typed schema, provenance, money-reference, relation-evidence, and bundle-isolation validation. A representative mail-only batch also passed after closed-vocabulary and coverage refinement. A four-chunk financial pilot exposed that structural acceptance could omit all money interpretations; the contract now requires an exact money-component manifest and one interpretation per supplied component. Production execution remains blocked on a passing bounded financial pilot under the latest contract.

### 8.8 Metadata governance

Metadata is accepted into the canonical graph only when it performs at least one declared function:

```text
ROUTES_PROCESSING
ENFORCES_INVARIANT
IMPROVES_RETRIEVAL
SUPPORTS_REPRODUCTION
CONTROLS_PRIVACY
ENABLES_QUERY
MEASURES_QUALITY
```

Every non-trivial metadata field must declare:

```text
field_id
producer
consumer
population_rule
nullable_reason
update_semantics
validation_rule
privacy_class
retention_policy
test_id
```

Do not add metadata merely because it sounds rich. A field without a producer, consumer, or test is not a moat; it is schema debt.

### 8.9 Provenance boundaries

Record provenance at material pipeline boundaries rather than creating a graph node for every internal function call.

```text
ProvenanceRun {
  run_id
  run_type
  pipeline_version
  code_commit
  model_name
  model_revision
  prompt_version
  schema_version
  input_hash
  output_hash
  started_at
  completed_at
}
```

Create provenance runs for:

- document ingestion;
- extraction/OCR;
- agentic chunking;
- entity resolution;
- financial derivation;
- reconciliation;
- embedding generation;
- public projection;
- analytical experiments;
- human correction.

Relationships may include:

```text
(ProvenanceRun)-[:USED]->(Document|EvidenceChunk|Assertion)
(ProvenanceRun)-[:GENERATED]->(EvidenceChunk|Assertion|ResolutionDecision|Finding)
```

### 8.10 Chunker boundaries

The chunker may propose:

- normalized strings;
- semantic roles;
- entity mentions;
- graph candidates;
- candidate financial meanings.

The chunker must not make the final decision on:

- entity identity;
- monetary reconciliation;
- public privacy transformation;
- graph commit;
- funding attribution;
- settlement verification.

---

## 9. Deterministic identifiers

LLMs never invent persistent IDs.

### 9.1 Document

```text
document_id = "doc_" + sha256(file_bytes)[0:16]
```

### 9.2 Chunk

```text
chunk_id = UUID5(
  document_id
  + page_number
  + chunk_type
  + reading_order
  + normalized_content_hash
)
```

### 9.3 Mention

```text
mention_id = UUID5(
  chunk_id
  + entity_type
  + source_span
  + raw_value
)
```

### 9.4 Order

Preferred:

```text
platform + private platform order ID
```

Fallback:

```text
platform + order date + outlet candidate + amount + item fingerprint
```

Fallback IDs are marked provisional and may be superseded after bundle resolution.

### 9.5 Public identifiers

Exact platform order IDs, invoice numbers, personal names, and registrations are never used as public IDs.

Examples:

```text
ORD-ZM-2026-0042
OUT-C3-TNJ-001
DP-017
DM-0042
```

---

## 10. Identity resolution and privacy-safe normalization

### 10.1 General flow

```text
raw source mention
→ normalized mention
→ candidate generation
→ positive and negative evidence
→ scored resolution decision
→ canonical entity or unresolved mention
```

Raw evidence remains immutable.

### 10.2 Restaurant and outlet resolution signals

Positive evidence:

- exact GSTIN/FSSAI;
- platform merchant identifier;
- normalized trade name;
- legal name;
- address and postal code;
- locality;
- historical continuity;
- menu overlap;
- template context.

Negative evidence:

- conflicting GSTIN/FSSAI;
- incompatible addresses;
- distinct simultaneously active outlets;
- different legal owners;
- contradictory platform identifiers.

### 10.3 Item resolution hierarchy

Do not collapse all similarly named dishes or products into one identity.

```text
OrderLine
  → ItemObservation
      → MerchantItem
          → DishStyle or GroceryProduct
              → FoodConcept or ProductCategory
```

Identity and economic comparability are separate.

A `ComparableItemGroup` is created for price-index analysis and includes its matching method, constraints, and confidence.

### 10.4 Business owner handling

The private source may contain a proprietor's legal name. The public graph must use a role label.

Example:

```text
BusinessRole {
  role_id: "role:c3-cafe-tanjore:owner"
  role_type: OWNER
  public_label: "C3 Cafe Owner"
}
```

Relationships:

```text
(PersonMention)-[:OBSERVED_AS_HOLDER_OF]->(BusinessRole)
(BusinessRole)-[:ROLE_AT]->(Outlet)
```

The source person name remains encrypted/private and is never replaced inside immutable evidence.

### 10.5 Delivery-person handling

Every document appearance creates a unique `DeliveryPartnerMention`.

A stable `PersonIdentity` is created only when evidence supports it.

```text
DeliveryPartnerMention {
  mention_id
  public_alias
  normalized_name_hmac
  source_document_id
  source_chunk_id
  platform
  locality
}

PersonIdentity {
  person_id
  public_alias
  identity_status
}
```

Resolution statuses:

```text
MENTION_ONLY
POSSIBLE_MATCH
PROBABLE_MATCH
HIGH_CONFIDENCE_MATCH
USER_CONFIRMED
REJECTED
```

Public output must distinguish:

```text
11 high-confidence deliveries
3 possible same-name mentions
2 unresolved mentions
```

It must not state that a repeated name proves the same person.

### 10.6 ResolutionDecision

```text
ResolutionDecision {
  resolution_id
  resolution_type
  selected_candidate_id
  selected_score
  second_candidate_score
  decision_margin
  positive_signals[]
  negative_signals[]
  policy_version
  status
  decided_at
}
```

Every merge is reversible.

---

## 11. Financial truth model

Lunarbit is a reconstruction system, not an operational bank ledger.

### 11.1 Truth scopes

```text
DOCUMENT_ASSERTED
CROSS_DOCUMENT_DERIVED
PAYMENT_EVIDENCED
BANK_CONFIRMED          # future only
USER_CONFIRMED
```

An invoice that says “settled digitally” creates `DOCUMENT_ASSERTED` payment evidence. It does not prove that a bank transfer occurred.

### 11.2 Epistemic modes

```text
OBSERVED
NORMALIZED
RESOLVED
CALCULATED
INFERRED
SIMULATED
```

### 11.3 Core financial primitives

```text
MoneyComponent
Promotion
MembershipProgram
PaymentEvidence
ReconciliationRun
```

### 11.4 MoneyComponent

```text
MoneyComponent {
  component_id
  component_type
  amount
  source_amount_string
  currency
  source_precision
  scope
  tax_inclusive
  tax_rate
  epistemic_mode
  truth_scope
  verification_status
  funding_status
  source_document_id
  source_chunk_id
}
```

Supported component types include:

```text
ITEM_GROSS
ITEM_DISCOUNT
ITEM_NET
PACKING_CHARGE
HANDLING_FEE
DELIVERY_CHARGE
PLATFORM_FEE
CGST
SGST
IGST
CESS
COUPON_DISCOUNT
MEMBERSHIP_BENEFIT
INVOICE_TOTAL
CUSTOMER_TOTAL
REFUND
ROUNDING_ADJUSTMENT
UNEXPLAINED_DISCOUNT_RESIDUAL
UNEXPLAINED_FINANCIAL_RESIDUAL
```

### 11.5 Reconciliation scopes

```text
DOCUMENT_INTERNAL
CUSTOMER_ORDER
RESTAURANT_SUPPLY
SELLER_SUPPLY
PLATFORM_SERVICE
PAYMENT_ASSERTION
REFUND
CROSS_DOCUMENT
DISCOUNT_ATTRIBUTION
```

Each scope reconciles independently where evidence permits.

Do not require a synthetic global zero-sum across customer, restaurant, platform, delivery partner, and governments when the archive does not expose every financial leg.

### 11.6 ReconciliationRun

```text
ReconciliationRun {
  reconciliation_id
  reconciliation_type
  formula
  expected_amount
  calculated_amount
  residual
  tolerance
  explained_value_ratio
  status
  assumptions[]
  algorithm_version
  executed_at
}
```

Statuses:

```text
EXACT
WITHIN_SOURCE_PRECISION
WITHIN_ROUNDING
PARTIAL
CONFLICTING
UNRESOLVED
```

### 11.7 Discount attribution

```text
funding_status:
  MERCHANT_OBSERVED
  PLATFORM_OBSERVED
  EXTERNAL_OBSERVED
  MIXED_OBSERVED
  CONSISTENT_WITH_PLATFORM_FUNDING
  PROBABLE_PLATFORM_FUNDING
  UNRESOLVED
```

`CONSISTENT_WITH_*` and `PROBABLE_*` are inferences and must include alternatives and supporting evidence.

### 11.8 Deterministic arithmetic

Use Python `Decimal`.

Preserve:

- original amount string;
- source precision;
- normalized Decimal;
- display precision;
- rounding policy.

No float arithmetic is allowed in financial invariants.

---

## 12. Economic and fintech intelligence

The architecture is lightweight, but the economic layer remains deep.

### 12.1 Governed metric definitions

```text
MetricDefinition {
  metric_id
  name
  formula
  unit
  required_components[]
  aggregation_method
  valid_scope
  version
}
```

Example metrics:

```text
effective_order_cost
fee_burden_ratio
discount_capture_rate
delivery_burden_ratio
packing_handling_burden
membership_net_benefit
unexplained_discount_share
personal_food_price_index
personal_grocery_price_index
```

### 12.2 MetricObservation

```text
MetricObservation {
  observation_id
  metric_id
  subject_id
  period_start
  period_end
  value
  calculation_version
  evidence_coverage
  confidence
}
```

### 12.3 Personal price indices

Support progressively stronger comparison levels:

1. exact same grocery SKU and package size;
2. same merchant item at the same outlet;
3. manually or confidently matched comparable items;
4. broader dish style or product category with lower confidence.

Possible index methods:

- same-item change;
- matched basket;
- Laspeyres;
- Paasche;
- Fisher;
- rolling median effective price.

Every index displays coverage and comparability confidence.

### 12.4 Spending decomposition

```text
AttributionRun {
  attribution_id
  period_a
  period_b
  total_change
  order_frequency_effect
  basket_size_effect
  item_price_effect
  merchant_mix_effect
  item_mix_effect
  delivery_effect
  packing_handling_effect
  platform_fee_effect
  tax_effect
  discount_effect
  residual
  method
}
```

The system must be able to answer:

> Did spending rise because prices increased, the user ordered more frequently, baskets became larger, merchants changed, fees increased, or discounts weakened?

### 12.5 Safe scenarios

```text
ScenarioRun {
  scenario_id
  scenario_type
  observed_total
  counterfactual_total
  difference
  assumptions[]
  unsupported_elements[]
  calculation_version
}
```

Allowed in version 1:

- no platform fees;
- no delivery charges;
- no packing/handling charges;
- observed discounts removed;
- membership benefit removed;
- constant observed order frequency;
- fixed historical price under explicit assumptions.

Not allowed as causal conclusions:

- which restaurant the user would have chosen;
- whether a discount caused an order;
- which platform would always have been cheaper without complete contemporaneous alternatives.

---

## 13. Final Neo4j schema

The schema is rich but disciplined. A node exists only when it has identity, lifecycle, relationships, temporal versions, uncertainty, or repeated query value.

### 13.1 Evidence layer

#### `Document`

```text
Document {
  document_id
  sha256
  document_type
  platform
  invoice_number_hash
  invoice_date
  page_count
  source_role
  extraction_method
  extraction_version
  template_signature
  privacy_class
}
```

#### `TemplateVersion`

```text
TemplateVersion {
  template_id
  platform
  document_type
  structural_signature
  active_from
  active_to
  extraction_strategy
  known_failure_modes[]
  version
}
```

#### `EvidenceChunk`

Defined in Section 8.4. This is the main evidence vector entity.

#### `Assertion`

Use assertion nodes selectively for uncertain, conflicting, derived, or versioned facts.

```text
Assertion {
  assertion_id
  predicate
  value_json
  value_type
  truth_scope
  epistemic_mode
  verification_status
  confidence
  valid_from
  valid_to
  pipeline_version
}
```

### 13.2 Commerce layer

#### `Order`

```text
Order {
  order_id
  public_order_id
  platform_order_id_hash
  order_time
  time_precision
  order_type: FOOD | GROCERY
  bundle_status
  evidence_coverage
  reconciliation_status
  platform
  city
  privacy_class
}
```

#### `OrderLine`

```text
OrderLine {
  order_line_id
  sequence
  quantity
  unit_of_measure
  raw_item_name
  unit_price
  gross_amount
  discount_amount
  net_amount
  final_amount
}
```

#### `Platform`

```text
Platform {
  platform_id
  brand_name
  platform_type
}
```

#### `Merchant`

```text
Merchant {
  merchant_id
  display_name
  normalized_name
  merchant_type
  alias_names[]
}
```

#### `Outlet`

```text
Outlet {
  outlet_id
  display_name
  locality
  city
  state
  postal_code
  exact_address_private
  address_hash
  gstin_hash
  fssai_hash
  platform_merchant_id_hash
  valid_from
  valid_to
}
```

#### `LegalEntity`

```text
LegalEntity {
  legal_entity_id
  public_display_name
  legal_name_private
  legal_name_hash
  entity_type
  gstin_hash
  pan_hash
  cin_hash
  valid_from
  valid_to
}
```

#### `BusinessRole`

```text
BusinessRole {
  role_id
  role_type
  public_label
  valid_from
  valid_to
}
```

### 13.3 Product layer

#### `ItemObservation`

```text
ItemObservation {
  observation_id
  raw_name
  normalized_name
  item_type
  brand_name
  variant
  package_size
  observed_at
  outlet_id
  embedding
}
```

#### `MerchantItem`

```text
MerchantItem {
  merchant_item_id
  display_name
  merchant_id
  valid_from
  valid_to
}
```

#### `CanonicalItem`

```text
CanonicalItem {
  canonical_item_id
  canonical_name
  concept_type
  category
  cuisine
  brand
  embedding
}
```

#### `ComparableItemGroup`

```text
ComparableItemGroup {
  group_id
  comparison_method
  portion_normalization
  outlet_constraint
  package_constraint
  similarity_threshold
  confidence
  review_status
}
```

#### `TaxCode`

```text
TaxCode {
  tax_code_id
  code
  system: HSN | SAC
  description
}
```

### 13.4 Identity layer

```text
EntityMention
PersonMention
PersonIdentity
ResolutionDecision
```

These follow Section 10.

### 13.5 Financial layer

```text
MoneyComponent
Promotion
MembershipProgram
PaymentEvidence
ReconciliationRun
```

#### `Promotion`

```text
Promotion {
  promotion_id
  promotion_type
  code_private
  public_name
  stated_value
  funding_status
}
```

#### `MembershipProgram`

```text
MembershipProgram {
  membership_id
  name
  platform_id
  valid_from
  valid_to
}
```

#### `PaymentEvidence`

```text
PaymentEvidence {
  payment_evidence_id
  stated_amount
  payment_method
  source_statement
  evidence_status
  stated_settlement_date
}
```

### 13.6 Intelligence layer

```text
MetricDefinition
MetricObservation
AttributionRun
ScenarioRun
Finding
QueryTrace
```

#### `Finding`

```text
Finding {
  finding_id
  finding_type
  title
  summary
  calculation
  confidence
  claim_type: DESCRIPTIVE | ASSOCIATIONAL
  algorithm_version
  created_at
  embedding
}
```

#### `QueryTrace`

```text
QueryTrace {
  trace_id
  normalized_question
  intent
  selected_tools[]
  query_template_ids[]
  graph_path_summary
  verification_status
  answer_hash
  latency_ms
  created_at
  approved_for_memory
}
```

### 13.7 Core relationships

```text
(PersonIdentity)-[:PLACED]->(Order)
(Order)-[:PLACED_ON]->(Platform)
(Order)-[:ORDERED_FROM]->(Outlet)
(Order)-[:HAS_LINE]->(OrderLine)
(Order)-[:DOCUMENTED_BY]->(Document)
(Order)-[:HAS_COMPONENT]->(MoneyComponent)
(Order)-[:HAS_PAYMENT_EVIDENCE]->(PaymentEvidence)
(Order)-[:RECONCILED_BY]->(ReconciliationRun)
(Order)-[:HAS_DELIVERY_MENTION]->(PersonMention)

(Document)-[:USES_TEMPLATE]->(TemplateVersion)
(Document)-[:ISSUED_BY]->(LegalEntity)
(Document)-[:ISSUED_ON_BEHALF_OF]->(LegalEntity|Outlet)
(Document)-[:HAS_CHUNK]->(EvidenceChunk)

(EvidenceChunk)-[:SUPPORTS]->(Assertion)
(Assertion)-[:ABOUT]->(Order|Outlet|OrderLine|MoneyComponent|LegalEntity)
(Assertion)-[:DERIVED_FROM]->(Assertion)
(Assertion)-[:CONTRADICTS]->(Assertion)
(Assertion)-[:SUPERSEDES]->(Assertion)

(Outlet)-[:OUTLET_OF]->(Merchant)
(Outlet)-[:OPERATED_BY]->(LegalEntity)
(BusinessRole)-[:ROLE_AT]->(Outlet)
(PersonMention)-[:OBSERVED_AS_HOLDER_OF]->(BusinessRole)

(OrderLine)-[:OBSERVED_AS]->(ItemObservation)
(ItemObservation)-[:LISTING_OF]->(MerchantItem)
(MerchantItem)-[:RESOLVED_TO]->(CanonicalItem)
(CanonicalItem)-[:MEMBER_OF]->(ComparableItemGroup)
(OrderLine)-[:CLASSIFIED_UNDER]->(TaxCode)

(PersonMention)-[:EVALUATED_BY]->(ResolutionDecision)
(EntityMention)-[:EVALUATED_BY]->(ResolutionDecision)
(ResolutionDecision)-[:RESOLVES_TO]->(PersonIdentity|Merchant|Outlet|LegalEntity|CanonicalItem)

(MoneyComponent)-[:APPLIES_TO]->(Order|OrderLine)
(MoneyComponent)-[:EVIDENCED_BY]->(EvidenceChunk)
(MoneyComponent)-[:TAX_ON]->(MoneyComponent)
(MoneyComponent)-[:DERIVED_FROM]->(MoneyComponent)
(MoneyComponent)-[:FUNDED_BY]->(Platform|Merchant|LegalEntity)
(Promotion)-[:GENERATED]->(MoneyComponent)
(Promotion)-[:APPLIED_TO]->(Order|OrderLine)
(MembershipProgram)-[:PROVIDED]->(MoneyComponent)

(ReconciliationRun)-[:USED]->(MoneyComponent)
(ReconciliationRun)-[:VALIDATED]->(Document|Order)
(ReconciliationRun)-[:PRODUCED]->(MoneyComponent)

(Finding)-[:SUPPORTED_BY]->(Order|ReconciliationRun|MetricObservation|AttributionRun)
(Finding)-[:EVIDENCED_BY]->(EvidenceChunk)
(Finding)-[:ABOUT]->(Merchant|Outlet|CanonicalItem|PersonIdentity|Platform)
```

### 13.8 Temporal rules

Use temporal fields only where they express real change:

```text
valid_from
valid_to
observed_at
knowledge_time
superseded_at
```

Examples:

- corporate rename;
- outlet operator change;
- business-role holder change;
- merchant-item listing evolution;
- template version evolution;
- finding or assertion supersession.

Do not add full bitemporal properties to every trivial node.

---

## 14. Embeddings and vector-index strategy

### 14.1 Model

Use Cohere `embed-v4.0`.

Required API semantics:

- stored documents/chunks: `input_type="search_document"`;
- live queries: `input_type="search_query"`;
- float embeddings for the initial benchmark;
- cosine similarity;
- cache embeddings by content hash, model, dimension, and input type.

Cohere Embed v4 supports Matryoshka dimensions:

```text
256
512
1024
1536
```

Start with **1024 dimensions**, then benchmark all four dimensions.

Selection rule:

> Choose the smallest dimension whose end-to-end Hit@1, MRR, and evidence recall are within 1% of the best tested dimension, unless latency or storage creates a material difference.

### 14.2 Four production vector indexes

#### 1. `evidence_vector`

Node label: `EvidenceChunk`

Purpose:

- semantic evidence retrieval;
- fee, tax, discount, and delivery-language variation;
- source-grounded answer support;
- ambiguous natural-language evidence requests.

Estimated scale: approximately 5,000–15,000 vectors.

#### 2. `item_vector`

Common node label: `SemanticItem`

Applied to:

- `ItemObservation`;
- `MerchantItem` where useful;
- `CanonicalItem`.

Purpose:

- dish/product normalization;
- similar-item discovery;
- grocery SKU and package matching;
- comparable-item candidate generation;
- personal inflation analysis.

#### 3. `entity_alias_vector`

Common node label: `ResolvableEntity`

Applied to:

- `EntityMention`;
- `Merchant`;
- `Outlet`;
- `LegalEntity`;
- selected `PersonMention` nodes privately.

Purpose:

- OCR variation;
- aliases;
- abbreviated legal names;
- merchant/outlet candidate generation;
- former company names.

Vector similarity generates candidates only. Exact identifiers, time, locality, and negative evidence make the final decision.

#### 4. `finding_vector`

Common node label: `IntelligenceArtifact`

Applied to:

- `Finding`;
- approved `AttributionRun` summaries;
- approved `ScenarioRun` summaries.

Purpose:

- search prior discoveries;
- reuse verified analytical artifacts;
- connect new questions to existing findings.

### 14.3 Optional fifth index

`query_memory_vector` is added only after a meaningful number of approved `QueryTrace` nodes exist.

Purpose:

```text
new question
→ retrieve similar verified query trace
→ adapt typed parameters
→ execute governed query template
```

Do not create an empty index before this capability exists.

### 14.4 What is not vectorized

Do not vectorize standalone:

- order IDs;
- invoice numbers;
- dates;
- amounts;
- quantities;
- tax rates;
- GSTIN/FSSAI values;
- status enums.

These belong to exact, range, or full-text indexes.

### 14.5 Neo4j version capability gate

At setup time run:

```cypher
CALL dbms.components();
SHOW VECTOR INDEXES;
```

Preferred on Neo4j/Aura 2026.01+:

- `VECTOR` property type where supported;
- `SEARCH` clause;
- in-index filterable properties;
- multi-label vector index support.

Fallback for older compatible versions:

- `LIST<FLOAT>` properties;
- `db.index.vector.queryNodes`;
- post-retrieval metadata filtering.

The code must expose one compatibility abstraction rather than spreading version checks across the project.

### 14.6 HNSW and quantization benchmark

Lunarbit's dense retrieval layer is a first-class systems component. It combines
three independently valuable capabilities:

#### 14.6.1 MRL — adaptive representation resolution

Use Cohere Embed v4's supported Matryoshka dimensions (`256`, `512`, `1024`,
and `1536`) to expose multiple retrieval operating points from one embedding
model. MRL allows cheap broad candidate generation and richer precision for
reranking without maintaining separate embedding models.

The dimension is selected by retrieval benchmark and query family. Arbitrary
post-hoc truncation of a non-MRL embedding is not permitted.

#### 14.6.2 HNSW — navigable dense retrieval graph

Use HNSW as the dense candidate-navigation layer over evidence, item, entity,
and finding vectors. Its hierarchical proximity graph enables fast approximate
nearest-neighbor search with explicit controls for graph degree, construction
quality, search expansion, memory, and latency.

HNSW candidates are fused with exact IDs, Lucene/BM25, graph traversal, and
metadata filters. Approximate retrieval never replaces evidence verification.

#### 14.6.3 RaBitQ — compact, high-throughput vector search

Use RaBitQ to encode vectors into compact quantized distance representations and
accelerate ANN distance estimation. This provides a production path to lower
vector memory, faster distance computation, and larger effective search
capacity while preserving a full-precision reranking path.

RaBitQ is an index representation, not canonical data. Full-precision vectors
remain available for reranking, reproducibility, and quality audits.

#### 14.6.4 Combined retrieval path

```text
Cohere Embed v4 MRL vector
  → dimension-aware candidate index
  → HNSW navigation
  → RaBitQ-compressed distance estimation where supported
  → full-precision reranking
  → lexical/exact/graph fusion
  → evidence coverage verification
```

The initial deployment uses provider-supported HNSW and quantization features;
the adapter must also support a dedicated RaBitQ/HNSW implementation where the
selected vector backend exposes it. This keeps the retrieval contract portable
across Neo4j, Zilliz/Milvus, LanceDB, and CockroachDB-backed projections.

Benchmark the complete retrieval stack:

```text
vector.hnsw.m: 16, 32
vector.hnsw.ef_construction: 100, 200
vector.hnsw.ef_search: 50, 100, 200
embedding_dimension: 256, 512, 1024, 1536
quantization: full, provider-native, RaBitQ
search expansion factor: default, 1.5 where supported
```

Publish exact-neighbour recall, Hit@K, MRR/nDCG, evidence recall, answer
grounding, p50/p95 latency, index build time, memory footprint, and storage
bytes per vector. Retain the full-vector baseline as the correctness reference.

Choose settings by measured end-to-end quality and operational efficiency.

---

## 15. Lexical retrieval, BM25, and sparse embeddings

### 15.1 Final decision

Use Neo4j Lucene full-text indexes as the lexical retrieval arm.

Do not store term-frequency vectors in Neo4j's dense `VECTOR` type and attempt to simulate BM25.

Reasons:

- the vector index is optimized for fixed-dimensional dense nearest-neighbour search;
- a manual BM25 implementation would require term/document statistics and an efficient inverted index;
- Neo4j full-text already provides the appropriate Lucene-backed lexical mechanism;
- custom Cypher BM25 would be slower, harder to maintain, and unnecessary at this dataset size.

### 15.2 Terminology rule

In documentation call it:

> **Neo4j Lucene full-text lexical retrieval**

Do not claim user-tuned BM25 parameters unless the deployed environment explicitly exposes and verifies that configuration.

### 15.3 SPLADE

Neo4j does not provide a native SPLADE-style sparse token-weight vector index as part of the planned stack.

Version 1 will not add an external sparse engine.

Keep an interface boundary:

```python
class LexicalRetriever: ...
class DenseRetriever: ...
class SparseRetriever: ...  # optional future adapter
```

Add SPLADE or an external sparse store only if the benchmark proves a meaningful improvement over:

```text
full-text + dense + graph + reranker
```

---

## 16. Hybrid retrieval and query routing

### 16.1 Query classes

#### Exact graph query

Example: “How many times did I order from C3 Cafe?”

```text
entity resolution → governed Cypher
```

#### Financial aggregation

Example: “How much platform fee did I pay in 2026?”

```text
typed metric/query plan → governed Cypher → Decimal calculation
```

#### Lexical lookup

Example: “Find invoice rows containing MEALX.”

```text
full-text index → metadata filter → evidence pack
```

#### Semantic discovery

Example: “Which orders felt expensive for what I received?”

```text
dense + lexical candidates → graph context → statistical features → rerank
```

#### Evidence request

Example: “Prove the ₹14.24 tax.”

```text
MoneyComponent → EvidenceChunk → document page → redacted crop
```

#### Multi-hop economic query

Example: “Did higher discounts offset rising fees for comparable chicken meals?”

```text
item resolution → comparable group → orders → components → metric calculation → evidence
```

### 16.2 Retrieval pipeline

```text
query classification
→ entity resolution
→ exact/full-text/dense candidate generation
→ independent rank normalization
→ reciprocal rank fusion
→ graph expansion
→ Cohere rerank
→ source-authority and reconciliation scoring
→ evidence verification
→ deterministic answer
```

Recommended candidate counts:

```text
full-text: top 30
dense: top 30
exact/entity: top 20
fused/reranked: top 8–12
```

Tune by benchmark.

### 16.3 Graph-aware ranking signals

```text
dense similarity
lexical rank
exact identifier/entity match
time overlap
platform match
outlet match
graph distance
document authority
bundle completeness
reconciliation status
evidence confidence
contradiction penalty
privacy eligibility
```

### 16.4 Source-authority policy

Authority depends on the fact family.

Examples:

- customer payable total: order summary;
- restaurant taxable supply: restaurant invoice;
- platform service fee and tax: platform-fee invoice;
- grocery item HSN/tax: seller tax invoice;
- delivery-person mention: order summary or delivery invoice;
- actual bank debit: bank statement, future only.

No document is universally authoritative for every fact.

---

## 17. Graph-O1-inspired bounded graph reasoning

The Graph-O1 paper motivates selective, interactive graph exploration instead of serializing a large one-hop or two-hop subgraph into an LLM context.

Lunarbit will adopt the practical principle, not reproduce full MCTS and reinforcement-learning training in version 1.

### 17.1 Bounded actions

```text
ResolveEntity
SearchEvidence
ReadNodeFacts
ExpandNeighbors
RunMetric
RunReconciliation
VerifyPath
FinishAnswer
```

### 17.2 Limits

```text
maximum traversal depth: 4–6
candidate paths per step: 2–3
maximum graph actions: configurable hard limit
read-only Cypher
relationship-type allowlist
row and timeout limits
```

### 17.3 Path scoring

```text
query relevance
evidence coverage
financial validity
source authority
entity confidence
path-length penalty
contradiction penalty
privacy eligibility
```

### 17.4 Research extension

After enough verified `QueryTrace` data exists:

- compare greedy traversal, beam search, and MCTS-style exploration;
- train or tune a traversal policy only if evaluation justifies it;
- publish ablations against direct vector retrieval and fixed-hop expansion.

---

## 18. LangGraph workflow

Use a small number of meaningful workflow graphs rather than many theatrical agents.

### 18.1 Offline ingestion graph

```text
Manifest
→ Classify
→ Extract
→ Validate
→ Chunk
→ Resolve entities
→ Reconcile
→ Embed
→ Commit to Neo4j
→ Verify graph invariants
```

### 18.2 Online query graph

```text
Interpret query
→ Resolve entities and time range
→ Select governed tools
→ Retrieve candidates
→ Expand graph
→ Calculate metrics
→ Retrieve evidence
→ Verify claims
→ Answer or abstain
```

### 18.3 Core query state

```text
QueryState {
  user_query
  intent
  resolved_entities[]
  time_range
  query_plan
  selected_tools[]
  graph_results[]
  calculations[]
  evidence[]
  reasoning_paths[]
  answer
  verification_status
  abstention_reason
}
```

### 18.4 Tools

```text
run_cypher_template
fulltext_search
vector_search
hybrid_search
expand_neighbors
retrieve_evidence
calculate_metric
reconcile_order
compare_platforms
get_price_history
run_scenario
verify_answer
```

### 18.5 Prompt engineering and versioning

Every production prompt must declare:

```text
prompt_id
semantic_version
purpose
input_contract
output_contract
forbidden_behaviours
few-shot fixture IDs
last benchmark date
benchmark score
rollback version
```

Prompts must explicitly require:

- evidence-bound extraction;
- no invented identifiers;
- no silent arithmetic;
- explicit unknowns;
- source versus normalized values;
- typed JSON output;
- bounded reasoning;
- privacy-safe output.

Prompt changes cannot merge unless the relevant regression suite passes.

### 18.6 Critic and verifier policy

Use critique selectively where failure cost is high:

```text
draft candidate
→ schema validator
→ financial validator
→ evidence verifier
→ privacy validator
→ accept / revise / abstain
```

Do not run expensive self-consistency on every chunk. Trigger it for unknown templates, conflicting financial values, low confidence, or benchmark-designated hard cases.

### 18.5 Safety

- no arbitrary graph writes from an LLM;
- parameterized Cypher;
- read-only production database user;
- allowlisted query templates where possible;
- AST or plan validation for generated Cypher;
- bounded retries;
- deterministic financial tools;
- abstain on missing evidence.

---

## 19. Public application

The frontend is not only a chat interface.

### 19.1 Landing page

Display real, measured values:

```text
documents processed
orders reconstructed
merchants/outlets resolved
item observations
financial value analysed
reconciliation rate
evidence support rate
Hit@1 / MRR
P95 latency
```

### 19.2 Ask Lunarbit

Each answer displays:

- direct answer;
- calculation;
- confidence/truth scope;
- graph path;
- evidence cards;
- limitations or unresolved residuals.

### 19.3 Transaction reconstruction

Show one order as a visual bundle:

```text
customer summary
restaurant/seller invoice
platform invoice
financial components
promotions and benefits
reconciliation equations
unexplained residuals
```

### 19.4 Evidence laboratory

For selected safe examples show:

- redacted PDF crop;
- extracted JSON;
- rich chunk;
- graph nodes and relationships;
- deterministic reconciliation;
- final answer trace.

### 19.5 Graph explorer

Allow bounded exploration of:

```text
Platform → Order → Outlet → Merchant → Item → Promotion → MoneyComponent → Evidence
```

Do not expose the full private graph.

### 19.6 Economic dashboard

Include:

- food and grocery spending over time;
- item-price and effective-price trends;
- fee burden;
- discount capture;
- membership savings;
- merchant and platform mix;
- spending decomposition;
- archive coverage and uncertainty.

### 19.7 Benchmark laboratory

Publish:

- golden-set composition;
- extraction metrics;
- entity-resolution metrics;
- reconciliation metrics;
- retrieval ablations;
- end-to-end answer metrics;
- failure examples;
- known limitations.

---

## 20. Deployment

### 20.1 Runtime

```text
Next.js frontend on Vercel
        ↓
FastAPI serverless/service deployment
        ↓
Neo4j AuraDB
Cohere Embed/Rerank APIs
LLM provider
```

If FastAPI runtime constraints on the chosen Vercel setup become restrictive, deploy the API to a lightweight Python host while keeping Next.js on Vercel. The public architecture and repository remain unchanged.

### 20.2 Offline versus online work

Offline/private:

- PDF extraction;
- OCR;
- agentic chunking;
- bulk entity resolution;
- bulk embeddings;
- graph rebuild;
- evidence redaction.

Online/public:

- read-only queries;
- query embeddings;
- reranking;
- graph traversal;
- deterministic metric calculation;
- redacted evidence serving.

### 20.3 Public projection and privacy architecture

The public application must query only public-safe properties and redacted evidence.

Recommended approach:

```text
private processed JSON / private graph state
        ↓ deterministic privacy projection
public-safe Neo4j properties + redacted evidence assets
        ↓ automated privacy tests
public application
```

Private-by-default fields include:

- exact addresses;
- phone numbers and emails;
- third-party personal names;
- exact order and invoice identifiers;
- raw payment references;
- full GSTIN/FSSAI/PAN/CIN values in the public UI;
- raw invoices.

Public-safe fields may include, after review:

- platform names;
- merchant trade names;
- item names;
- city/state;
- public aliases;
- broad time periods;
- aggregate prices, fees, taxes, discounts, and metrics;
- manually redacted evidence crops.

Use synthetic data where a real longitudinal pattern could reveal a personal behavioural fingerprint. The public demo may combine a synthetic six-year mirror, safe aggregates, and a few manually redacted real examples.

### 20.3 Secrets

- Aura credentials are server-side only;
- Cohere and LLM keys are server-side only;
- browser never connects directly to Aura;
- separate read-only public database credentials;
- `.env.example` contains names, never values.

---

## 21. Evaluation laboratory

### 21.1 Golden corpus

Begin with the five supplied PDFs and manually validated expected outputs.

Expand by template-stratified sampling:

- every known document type;
- every template signature;
- food and grocery;
- discounts and memberships;
- refunds/cancellations when available;
- incomplete bundles;
- OCR failures;
- ambiguous entities;
- precision/rounding edge cases.

### 21.2 Extraction metrics

```text
document-type accuracy
exact monetary field accuracy
table-row reconstruction accuracy
source-precision preservation
bounding-box accuracy
document-level exact match
unknown-template detection recall
```

### 21.3 Chunking metrics

```text
semantic completeness
header-row preservation
financial-role accuracy
query-family coverage
unsupported candidate-fact rate
chunk-boundary error rate
```

### 21.4 Entity-resolution metrics

```text
precision
recall
F1
overmerge rate
undermerge rate
precision by confidence bucket
reversible-merge success
```

Delivery-person resolution must report mention-level and identity-level results separately.

### 21.5 Financial metrics

```text
document reconciliation rate
cross-document explained-value ratio
unexplained residual rate
incorrect funding-attribution rate
unsupported settlement-claim rate
source-precision preservation
duplicate-ingestion rate
```

### 21.6 Retrieval metrics

Benchmark:

```text
exact only
full-text only
dense only
full-text + dense
full-text + dense + graph
full-text + dense + graph + rerank
bounded graph exploration
```

Track:

```text
Hit@1
Hit@2
Hit@5
MRR
evidence recall
evidence precision
answer-support coverage
```

### 21.7 End-to-end metrics

```text
exact answer accuracy
numeric absolute error
calculation reproducibility
unsupported claim rate
correct abstention rate
graph-path validity
evidence citation accuracy
P50/P95 latency
cost per query
```

### 21.8 Confidence calibration

Track confidence by component rather than one opaque score:

```text
extraction confidence
entity-resolution confidence
reconciliation confidence
evidence completeness
answer-verification status
```

Use reliability buckets, expected calibration error, and abstention thresholds where sample size permits.

---

## 22. Testing strategy

### 22.1 Unit tests

- amount parsing;
- Decimal arithmetic;
- source precision;
- deterministic IDs;
- normalization;
- metric formulas;
- privacy transformations.

### 22.2 Property tests

- idempotent ingestion;
- reconciliation stability;
- no negative amounts where prohibited;
- reversible entity merges;
- deterministic public aliases;
- order-independent metric calculations where specified.

### 22.3 Graph invariants

- unique IDs;
- no orphan public evidence;
- every public MoneyComponent has evidence or derivation;
- every resolution decision points to valid candidates;
- no public node contains private raw names or addresses;
- every vector matches the configured dimension;
- every derived finding links to evidence and a calculation artifact.

### 22.4 Prompt regression

Maintain fixed examples for:

- known templates;
- unknown templates;
- item rows;
- discount blocks;
- delivery ambiguity;
- corporate renames;
- evidence abstention;
- privacy transformation.

### 22.5 End-to-end tests

A golden query must validate:

```text
question
→ routing
→ graph query
→ calculation
→ evidence
→ answer
```


### 22.6 Observability

Record structured events for:

```text
document ingestion
extraction and OCR fallback
chunk validation
entity-resolution decisions
reconciliation status
embedding cache hits/misses
retrieval candidates and ranks
graph traversal actions
reranker inputs/outputs
answer verification
privacy filtering
latency and API cost
```

A query trace must make it possible to answer:

- Which retrieval paths ran?
- Which candidates were rejected and why?
- Which graph path supported the final answer?
- Which deterministic calculations were executed?
- Which evidence was shown?
- Why did the system abstain?

Logs must never contain raw secrets or unredacted private fields.

---

## 23. Compact repository structure

The repository must stay easy to understand. Richness belongs in contracts and graph semantics, not directory count.

```text
lunarbit/
├── README.md
├── PLAN.md
├── MEMORY.md
├── pyproject.toml
├── package.json
├── .env.example
│
├── src/lunarbit/
│   ├── models.py          # Pydantic contracts and enums
│   ├── extract.py         # PDF → JSON/JSONL
│   ├── chunk.py           # agentic chunking
│   ├── resolve.py         # identity and aliases
│   ├── finance.py         # MoneyComponent, metrics, reconciliation
│   ├── graph.py           # Neo4j schema, writes, migrations
│   ├── retrieval.py       # exact/full-text/vector/hybrid/rerank
│   ├── agent.py           # LangGraph workflows
│   └── api.py             # FastAPI
│
├── cypher/
│   ├── schema.cypher
│   └── queries.cypher
│
├── scripts/
│   ├── build_json.py
│   ├── build_graph.py
│   └── run_evals.py
│
├── web/
│   ├── app/
│   ├── components/
│   └── package.json
│
├── data/
│   ├── raw/               # private and gitignored
│   ├── processed/         # private and gitignored
│   ├── public/
│   └── evals/
│
└── tests/
    ├── test_extract.py
    ├── test_finance.py
    ├── test_graph.py
    └── test_retrieval.py
```

Split a source file only after it becomes genuinely difficult to maintain. Do not pre-create empty packages.

---

## 24. Development standards

### 24.1 Python

- Python 3.12+;
- Pydantic v2;
- strict typing;
- Ruff;
- Black;
- Pyright or MyPy;
- pytest;
- Hypothesis;
- structured logging;
- explicit exception hierarchy;
- no hidden global state.

### 24.2 Dependency direction

```text
models
  ↑
extract → chunk → resolve/finance → graph → retrieval → agent → api
```

Stages may import declared models, not another stage's private implementation.

### 24.3 Money boundary

Functions that perform arithmetic or reconciliation:

- accept typed inputs;
- return typed outputs;
- use `Decimal`;
- contain no network calls;
- contain no LLM calls;
- contain no direct graph writes.

### 24.4 AI output boundary

- typed structured output;
- schema validation;
- bounded retries;
- candidate state before canonical state;
- deterministic validation before graph write;
- prompt and model versions recorded;
- invalid output quarantined.

### 24.5 Cypher

- parameterized queries;
- constraints before data load;
- bounded traversals;
- query profiling;
- explicit timeouts and row limits;
- read-only online user;
- no raw user-input concatenation.

### 24.6 Governed metrics

Every reusable economic metric is defined once with:

- formula;
- required components;
- valid scope;
- version;
- tests;
- display rules.

Do not duplicate financial formulas in arbitrary Cypher or frontend code.

---

## 25. `MEMORY.md` maintenance protocol

### 25.1 Purpose

`PLAN.md` describes what Lunarbit is intended to become.

`MEMORY.md` records:

- where implementation currently stands;
- why non-obvious decisions were made;
- what should happen next;
- which mistakes must not be repeated;
- current measured results;
- unresolved questions.

It is not a second plan, schema file, or changelog.

### 25.2 Source-of-truth hierarchy

```text
Executable tests and versioned schemas  → actual contract
PLAN.md and accepted ADRs               → intended architecture
MEMORY.md                                → current state and rationale
Git history                              → code-change history
```

If these disagree, stop and reconcile the conflict rather than guessing.

### 25.3 Required structure

```markdown
# MEMORY.md

## Session handoff
- Last updated:
- Active phase:
- Current branch:
- Last verified commit:
- Last passing test/eval command:

## Current state
- Completed:
- In progress:
- Blocked:
- Schema/model/index versions in use:
- Latest metrics snapshot:

## Next actions — ordered
1. ...
2. ...
3. ...

## Decisions — append-only, newest first
### YYYY-MM-DD — Decision title
- Decision:
- Rationale:
- Alternatives rejected:
- Files/contracts affected:
- Validation performed:
- Revisit trigger:

## Known failures / do not repeat
- ...

## Open questions
- ...

## Important commands
```bash
# only commands required to resume work
```
```

### 25.4 Start-of-session discipline

Before changing code, every human or AI agent must:

1. read `PLAN.md`;
2. read `MEMORY.md`;
3. inspect `git status`;
4. inspect recent commits;
5. run or verify the last recorded test command;
6. confirm the active phase and next action.

Recommended agent instruction:

> Read `PLAN.md` and `MEMORY.md` before touching code. Follow the active phase and ordered next actions. Do not reopen accepted decisions unless a listed revisit trigger is met or tests contradict the decision.

### 25.5 End-of-session discipline

Before ending a work session:

1. update the current state;
2. record the exact last successful command;
3. reorder the next actions;
4. append any non-obvious decision;
5. record failed approaches that future sessions must not repeat;
6. update metrics if an evaluation changed;
7. remove stale blockers;
8. ensure no secrets or private invoice data entered `MEMORY.md`.

### 25.6 Decision-entry quality

Every decision entry must answer:

- What changed?
- Why?
- What was rejected?
- Which files or schemas changed?
- How was the decision validated?
- Under what condition should it be reconsidered?

Example:

```markdown
### 2026-08-03 — Keep discount residual unresolved
- Decision: Store ₹37.16 from Zomato order 8368252638 as
  UNEXPLAINED_DISCOUNT_RESIDUAL with funding_status=UNRESOLVED.
- Rationale: The customer summary shows ₹140 coupon value while the restaurant
  invoice exposes ₹102.84 merchant-side discount; the supplied documents do not
  directly identify the remaining funder.
- Alternatives rejected: Labeling the residual as platform-funded.
- Files/contracts affected: finance models, golden-order fixture, reconciliation tests.
- Validation performed: Recomputed from the three supplied Zomato documents.
- Revisit trigger: A source document explicitly identifying the funding allocation.
```

### 25.7 Size and pruning

- Keep `MEMORY.md` below approximately 300 lines.
- Move stable architectural decisions into `docs/adr/` only when the repository genuinely needs them.
- Leave a one-line link in `MEMORY.md` after moving a decision.
- Remove completed next actions rather than accumulating history.
- Keep only the most useful recent metrics snapshot.

### 25.8 Prohibited content

Never store in `MEMORY.md`:

- secrets or API keys;
- raw personal addresses;
- unmasked phone numbers or emails;
- third-party names from invoices;
- full raw invoice text;
- duplicated schemas;
- speculative claims presented as decisions;
- a verbose transcript of every coding action.

### 25.9 Current “do not repeat” baseline

The initial `MEMORY.md` must include:

- do not repeat the incorrect ₹59.16 discount residual; the supplied Zomato bundle yields ₹37.16;
- do not infer stable delivery identity from a repeated name alone;
- do not expose proprietor or delivery-person names publicly;
- do not use LLM arithmetic for canonical money;
- do not vectorize IDs, dates, or standalone amounts;
- do not implement custom BM25 using Neo4j dense vectors;
- do not add SPLADE infrastructure without an evaluation win;
- do not rebuild the oversized repository tree;
- do not label invoice settlement assertions as bank-confirmed;
- do not create empty vector indexes without a retrieval use case.

---

## 26. Delivery phases

### Phase 0 — Design freeze and golden corpus

- adopt this plan;
- initialize compact repository;
- initialize `MEMORY.md`;
- create private/public data rules;
- manually validate the five supplied PDFs;
- define Pydantic contracts;
- define expected graph and financial outputs for the Zomato bundle.

**Exit:** all golden expected outputs reviewed, including ₹37.16 unresolved discount residual.

### Phase 1 — PDF to JSON

- manifest and hashing;
- native extraction;
- table and layout extraction;
- OCR fallback;
- JSON/JSONL export;
- Markdown previews;
- extraction tests.

**Exit:** all golden PDFs deterministically reproduce validated JSON.

### Phase 2 — Agentic chunking

- chunk strategy router;
- rich chunk contract;
- candidate facts and entity mentions;
- validation and quarantine;
- chunking benchmark.

**Exit:** all golden financial and entity facts remain linked to correct source regions.

### Phase 3 — Entity and order resolution

- order-document bundles;
- merchant/outlet/legal-entity resolution;
- item hierarchy;
- business-role transformation;
- delivery mention/identity model;
- reversible decisions.

**Exit:** golden entities and bundles meet precision gates.

### Phase 4 — Financial and economic core

- MoneyComponent compiler;
- scoped reconciliation;
- source precision;
- residual detection;
- governed metrics;
- Zomato and Swiggy golden reconciliation tests.

**Exit:** exact deterministic results for supplied samples.

### Phase 5 — Neo4j graph and indexes

- constraints and exact indexes;
- full-text indexes;
- four vector indexes;
- Cohere embedding benchmark;
- graph load and invariant checks.

**Exit:** graph rebuild is idempotent and all indexes are online.

### Phase 6 — Hybrid GraphRAG

- query router;
- exact/full-text/dense retrieval;
- RRF;
- Cohere reranking;
- graph expansion;
- evidence pack;
- answer verifier.

**Exit:** benchmark publishes retrieval and end-to-end results.

### Phase 7 — Economic intelligence

- price indices;
- fee and discount metrics;
- membership ROI;
- spending decomposition;
- safe scenarios;
- finding graph.

**Exit:** findings are reproducible and evidence-linked.

### Phase 8 — Public application

- landing dashboard;
- Ask Lunarbit;
- transaction reconstruction;
- graph explorer;
- evidence laboratory;
- benchmark page;
- privacy tests;
- Vercel deployment.

**Exit:** a recruiter can verify one complex answer in under two minutes.

### Phase 9 — Advanced bounded graph reasoning

- Graph-O1-inspired path exploration;
- verified query memory;
- greedy/beam/bounded-search ablations;
- optional `query_memory_vector`.

**Exit:** advanced reasoning is retained only if it improves measured answer accuracy or evidence efficiency.

### Phase 10 — Archive backfill and maintenance

- process complete archive;
- monitor template drift;
- review unresolved bundles;
- regenerate metrics;
- publish final benchmark and demo video.

**Exit:** new documents can be inserted or the graph rebuilt without manual code changes for known templates.

---

## 27. Definition of done

Lunarbit is complete when:

- 500+ available documents are inventoried and deduplicated;
- public/private data boundaries are enforced;
- known template variants are represented;
- order bundles are reconstructed;
- monetary source precision is preserved;
- scoped reconciliations are deterministic;
- unexplained residuals remain visible;
- entity merges are reversible;
- delivery identity uncertainty is explicit;
- corporate rename history is queryable;
- exact, lexical, dense, hybrid, and graph queries work;
- every showcased answer has navigable evidence;
- economic metrics use governed formulas;
- retrieval and end-to-end benchmarks are published;
- public privacy leakage tests pass;
- deployment is stable;
- documentation includes failures and limitations;
- resume claims match measured results.

---

## 28. Headline demo features

1. **Cross-document financial reconstruction**  
   Combine customer summary, merchant invoice, and platform invoice while preserving differing truth scopes.

2. **Clickable evidence replay**  
   Answer → calculation → graph path → chunk → redacted page crop.

3. **Privacy-safe repeated-person analysis**  
   High-confidence identity clusters separated from possible same-name mentions.

4. **Query-adaptive GraphRAG**  
   Exact Cypher, Lucene full-text, Cohere dense retrieval, graph expansion, reranking, and verification selected by query type.

5. **Personal food and grocery inflation**  
   Same-item, same-outlet, comparable-item, and matched-basket views with coverage confidence.

6. **Spending-change decomposition**  
   Frequency, basket, price, merchant mix, item mix, fees, tax, discount, and residual effects.

7. **Corporate and document archaeology**  
   Discover legal-entity renames, invoice-template drift, and emerging charge categories from historical documents.

8. **Unexplained-value detector**  
   Surface unsupported residuals without inventing attribution.

9. **Verified query memory**  
   Reuse approved query plans only after sufficient query traces exist.

10. **Bounded multi-path graph reasoning**  
    Explore only useful graph paths instead of dumping large subgraphs into the LLM context.

---

## 29. Resume-grade outputs

The completed project must publish:

- live public application;
- architecture diagram;
- Neo4j ontology diagram;
- one complete evidence-replay walkthrough;
- benchmark report with ablations;
- privacy architecture;
- technical write-up;
- short demonstration video;
- clean GitHub repository;
- one concise resume entry with measured results.

Recommended final metric block:

```text
Documents processed:       X
Orders reconstructed:      Y
Exact monetary accuracy:   X%
Reconciliation rate:       X%
Entity resolution F1:      X
Retrieval Hit@1:           X%
MRR:                       X
Evidence support coverage: X%
P95 latency:               X ms
```

---

## 30. Risks and controls

### Overengineering

Control: compact repository, phase gates, and measurement before adding infrastructure.

### Incorrect financial claims

Control: source precision, Decimal arithmetic, scoped reconciliation, unresolved residuals.

### Entity overmerge

Control: negative evidence, decision margins, reversible resolutions, separate mentions and identities.

### Privacy leakage

Control: public aliases, redacted evidence, separate public graph view, automated leakage tests.

### Retrieval theatre

Control: ablation tests and exact/lexical/dense routing rather than forcing every query through embeddings.

### Unsupported economic causality

Control: descriptive/associational labels and deterministic scenarios only in version 1.

### Template drift

Control: signatures, unknown-template quarantine, template-stratified golden set.

### Graph explosion

Control: assertion nodes only for facts that are uncertain, conflicting, derived, or temporally versioned.

### Public latency/cost

Control: offline ingestion, cached embeddings, bounded candidate sets, read-only optimized queries.

### Memory drift across AI coding sessions

Control: mandatory `MEMORY.md` start/end protocol and conflict reconciliation.

---

## 31. Final standard

Lunarbit should not appear advanced because it has many folders, agents, node labels, or frameworks.

It becomes advanced through:

- a difficult real dataset;
- strong evidence contracts;
- rich but purposeful chunks;
- deterministic finance;
- precise identity uncertainty;
- expressive graph relationships;
- hybrid retrieval with measured ablations;
- bounded graph reasoning;
- meaningful economic intelligence;
- privacy-safe public proof;
- transparent failures;
- reproducible evaluation.

> **The goal is not to build the largest knowledge graph. The goal is to build the most convincing, trustworthy, and technically complete public GraphRAG demonstration possible from personal-commerce documents.**

---

## 32. Research references

Use official documentation as the implementation source of truth and re-check versions during development.

- Cohere Embed API: https://docs.cohere.com/v2/reference/embed
- Cohere Embed model details: https://docs.cohere.com/v2/docs/cohere-embed
- Cohere Embed v4 Matryoshka announcement: https://docs.cohere.com/v2/changelog/embed-multimodal-v4
- Neo4j vector indexes: https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/
- Neo4j index syntax and full-text query procedures: https://neo4j.com/docs/cypher-manual/current/indexes/syntax/
- Neo4j GraphRAG for Python: https://neo4j.com/docs/neo4j-graphrag-python/current/
- Neo4j GraphRAG retrievers: https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_rag.html
- Graph-O1 paper: https://arxiv.org/abs/2512.17912
