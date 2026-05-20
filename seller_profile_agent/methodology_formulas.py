"""Canonical PRS formulas from la-methodologie.md for report appendices."""

from __future__ import annotations

PROSPECT_REVENUE_SCORE_NAME = "Prospect Revenue Score"
WEIGHTED_RELIABILITY_LABEL = "PRS score reliability"

GLOBAL_SCORE_FORMULA = (
    "Prospect Revenue Score = 25% × Company Size Fit + 20% × Estimated IT Budget Capacity "
    "+ 20% × Technology Category Need + 20% × Purchase Intent Signal "
    "+ 15% × Product Adoption Momentum"
)

GLOBAL_RELIABILITY_FORMULA = (
    "PRS score reliability = 25% × reliability_size + 20% × reliability_budget "
    "+ 20% × reliability_need + 20% × reliability_intent + 15% × reliability_momentum"
)

# Weight, display name, short plain-language definition (executive summary).
PRS_FORMULA_BULLETS: list[tuple[str, str, str]] = [
    ("25%", "Company Size Fit", "How large the account is (revenue and employees)."),
    ("20%", "Estimated IT Budget Capacity", "Whether HG shows enough IT spend to fund a deal."),
    ("20%", "Technology Category Need", "How active they are in your product's HG category."),
    ("20%", "Purchase Intent Signal", "Whether HG sees recent buying interest on your topic."),
    ("15%", "Product Adoption Momentum", "Whether usage of your product is rising or falling."),
]

RENORMALIZE_NOTE = (
    "If a criterion is not calculable, renormalize on active weights: "
    "score = Σ(weightᵢ × scoreᵢ) / Σ(weightᵢ) for applicable criteria; "
    "PRS score reliability uses the same weights on per-criterion reliability values."
)

METHODOLOGY_INTRO = (
    "This appendix mirrors `la-methodologie.md`. The official architecture has **three simple "
    "steps**: configure the seller + ICP once, filter ICP-compatible companies without scoring, "
    "then randomly sample companies for deep PRS. PRS criteria use a **closed list** of HG MCP "
    "fields — reliability measures **whether we have the inputs to run the math**, not sales quality."
)

MAX_PRS_DEEP = 10

PIPELINE_STEPS: list[dict[str, str]] = [
    {
        "id": "step_1",
        "title": "Step 1 — Seller Profile + ICP Configuration (one-time setup)",
        "body": """**Purpose:** This step is performed **once** by the sales user to configure the AI sales agent for a seller and one product/service.

**Terminal inputs:**
- Seller company name/domain
- Product/service selection from the generated product menu

**HG MCP tools used:**
- `company_firmographic` — verifies the seller exists in HG and returns legal name, domain, industry, revenue, employeeCount, itSpend, location, and HG id.
- `get_vendor_information` — direct HG evidence for products/services: `vendors[].products[]` product names and ids.
- `list_product_categories`, `list_intent_topics`, vendor catalog match, and `get_product_information` — bind the selected product to HG SKU/category/intent/competitors.

**How product/service discovery works:**
- Direct HG evidence: product names and ids from `get_vendor_information`.
- Deterministic grouping: `product_discovery.py` applies regex families (`PRODUCT_LINE_RULES`) to merge related SKUs into sellable product lines.
- Explicit inference: if HG catalog evidence is sparse, industry fallback templates may add lines tagged `inferred from HG data` or `general business inference`.
- Not used: prospect data, PRS scoring, LLM judgment, or seller-installed technologies as proof of what the seller sells.

**ICP thresholds generated:**
- Revenue floor (`min_revenue_usd`)
- Employee floor (`min_employees`)
- IT spend floor (`min_it_spend_usd`)
- Technographic/category adjacency (`category_adjacency_search`)
- Product adjacency/exclusion (`exclude_target_product_installed`) so prospects already using the seller SKU are excluded for land motions.

**Competitor extraction (audit only):** `methodology_binding.py` may still call `get_product_information(includeCompetitors=True)` and store `competitor_resolution` in `seller_profile.json` for audit. Competitor installs are **not** part of PRS (HG competitor lists were too often empty).

**Outputs:** `seller_profile.json`, `icp_thresholds.json`.

**Why deterministic:** same HG inputs + same terminal product selection produce the same seller profile and same ICP thresholds. No prospect ranking exists here.""",
    },
    {
        "id": "step_2",
        "title": "Step 2 — ICP Candidate Filtering (no scoring, no ranking)",
        "body": """**Purpose:** Filter a large HG company universe using **only** the ICP thresholds.

**HG MCP tool used:** `search_companies`.

**Inputs:** HG Insights database + `icp_thresholds.json`.

**Filters applied:**
- `revenueMin` and `employeesMin` from the ICP floors.
- `technologies` / category adjacency from the selected HG product category.
- `excludeTechnologies` for the seller SKU, so the pool targets accounts that do **not** already use the sold product.
- Deterministic hygiene: de-duplicate domains and remove the seller domain.
- Optional row-level threshold checks when HG search returns revenue, employee, or IT spend fields.

**Strict non-goals:** no PRS, no lightweight PRS, no score, no weight, no ranking, no ordering.

**Question answered:** “Which companies pass the ICP filters?”

**Outputs:** `candidate_companies.json`, `candidate_companies.md`, and terminal count such as “183 companies matched the ICP filters.”

**Why deterministic filtering stays pure:** ICP is a gate, not a prediction. Keeping it deterministic makes the system auditable, cheap, and easy to explain live.""",
    },
    {
        "id": "step_3",
        "title": "Step 3 — Random Sample + Deep PRS Analysis",
        "body": f"""**Purpose:** Ask the user how many prospects to analyze deeply, randomly select that many companies from `candidate_companies.json`, then run full PRS only on that sample.

**Terminal input:** “How many prospects do you want to analyze deeply?” (`prs_count`, capped at **{MAX_PRS_DEEP}** by default).

**Sampling rule:** uniform random sample without replacement among ICP-compatible candidates. Optional `--sample-seed` makes demos reproducible.

**Why random sampling is acceptable:** Step 2 already guarantees every candidate is ICP-compatible. The random sample is not a claim that sampled accounts are better; it is a cost-control mechanism for choosing which valid accounts receive expensive deep analysis.

**Deep PRS MCP tools:** `company_firmographic`, `company_spend`, `company_technographic`, `company_intent`, `company_install_time_series`.

**When ranking starts:** only after full PRS is computed on the sampled prospects. Final ranking = PRS descending among deep-scored prospects only.

**Cost and complexity reduction:** candidate discovery costs one `search_companies` call plus deterministic filtering; deep analysis costs about **5 MCP calls × sampled prospects**. There is no intermediate ranking state to maintain, explain, debug, or defend.

**Outputs:** `sampled_prospects.json`, `executive_summary.md`, detailed prospect cards, `technical_scoring.md`, `scoring_manifest.json`, and ranking JSON."""
    },
]

CRITERION_FORMULA_BLOCKS: list[dict[str, str]] = [
    {
        "id": "taille",
        "title": "Company Size Fit (25%)",
        "formulas": """**Business question:** What is the structural revenue ceiling for this account?

**Why logarithmic revenue?** Revenue spans orders of magnitude (millions to trillions). A log scale treats each tenfold increase equally so mid-market accounts are not crushed by mega-cap outliers.

**Why max(revenue score, employee score)?** Some platforms have huge revenue but modest headcount; averaging would under-rate them.

```
S_rev  = max(0, min(100, 100 × log10(company_firmographic.revenue / 1,000,000) / log10(1000)))
S_emp  = min(100, 100 × company_firmographic.employeeCount / 10,000)
S_size = max(S_rev, S_emp)
```

Values below the revenue anchor ($1M) floor to **0**, not negative.

**Reliability (2 HG fields):** `company_firmographic.revenue`, `company_firmographic.employeeCount`
```
reliability_size = (fields present) / 2
```""",
    },
    {
        "id": "budget",
        "title": "Estimated IT Budget Capacity (20%)",
        "formulas": """**Business question:** Can this account fund an IT project at the scale we sell?

**Why log on IT spend?** Same multi-scale problem as revenue. Anchor ~$1B Total IT → score near 100.

```
S_budget = max(0, min(100, 100 × log10(totalSpendAmount / 100,000) / 4))
```
Source row: `company_spend.spendByCategory` where categoryName = **Total IT**.

Spend below the $100k anchor floors to **0**, not negative.

**Reliability (2 HG fields):** `totalSpendAmount` (Total IT), `company_spend.unknownRowCount`
```
reliability_budget = (fields present) / 2
```""",
    },
    {
        "id": "besoin",
        "title": "Technology Category Need (20%)",
        "formulas": """**Business question:** Does the account already live in the seller's technology category?

```
intensity_max = max(company_technographic.products[].intensity) in seller HG category
S_need = min(100, intensity_max)
```

**Reliability (2 HG fields):** resolved category name, at least one `intensity` in that category
```
reliability_need = (fields present) / 2
```""",
    },
    {
        "id": "achat",
        "title": "Purchase Intent Signal (20%)",
        "formulas": """**Business question:** Is HG seeing recent buying interest on the **product topic**?

**Why score × freshness tiers?** `company_intent.topics[].score` is already 0–100 from HG. We only apply transparent day buckets (30 / 90) — no invented level mapping.

```
days = end_date − company_intent.topics[].last_seen_at
freshness_multiplier = 1.0 (≤30d) | 0.7 (31–90d) | 0.3 (>90d)
S_intent = min(100, topics[].score × freshness_multiplier)
```

**Reliability (3 HG fields):** product topic match, `topics[].score`, `topics[].last_seen_at`
```
reliability_intent = (fields present) / 3
```""",
    },
    {
        "id": "dynamique",
        "title": "Product Adoption Momentum (15%)",
        "formulas": """**Business question:** Is HG observing rising or falling product intensity on the bound seller SKU?

This is **not** company revenue growth — it is HG's `intensity_momentum` on the install time series (last 24 months).

```
S_momentum = 100 if intensity_momentum > 0
             = 50  if intensity_momentum = 0
             = 0   if intensity_momentum < 0
```
If SKU missing from series: neutral 50.

**Reliability (1 HG field):** `company_install_time_series.products[].intensity_momentum`
```
reliability_momentum = 1 if present, else 0
```""",
    },
]
