# Seller Profile

This document is the **source of truth** for how the seller account and the selected product line drive HG queries, ICP thresholds, and Prospect Revenue Score criteria. The executive summary references this file instead of repeating full seller detail.

## 1. Seller company (HG firmographics)

| Field | HG source | Value |
|-------|-----------|-------|
| Company | `company_firmographic` | Amazon.com, Inc. |
| Domain | `company_firmographic.domain` | `amazon.com` |
| Industry | `company_firmographic.industry` | Retail Trade |
| Revenue | `company_firmographic.revenue` | $716.92B |
| Employees | `company_firmographic.employeeCount` | 1576000 |
| IT spend | `company_firmographic.itSpend` | $26.14B |

### Why these seller fields matter

- **`revenue` and `employeeCount`** calibrate the **Company Size Fit** anchor on prospects.
- **ICP numeric floors** (`min_revenue_usd`, `min_employees`, `min_it_spend_usd`) are **entered by the sales user** when running `npm run profile:seller` — not derived from formulas.
- **`technologies_detected`** is a short sample from seller technographics — it does **not** build the product line menu (see `seller_profile.md` §2).

**Business context:** Amazon.com, Inc. is a company operating in the Retail Trade industry. HG reports estimated IT spend of approximately $26,139,876,977.

## 2. Sellable product lines (how the menu was built)

The profile lists **20** lines in `available_products` (max 20). They come from HG `get_vendor_information` + deterministic regex in `product_discovery.py` — **not** from an LLM and **not** from seller install data.

Each line has a `source_type`: `HG data` (catalog-backed), `inferred from HG data`, or `general business inference` (weak fallback). **Honest limit:** regex families are cloud-oriented; non-cloud sellers often get noisy `HG catalog product` rows.

Full step-by-step notes are in **§2** above and in `candidate_companies.md` for ICP application.

## 3. Selected product line & HG binding

| Field | Value |
|-------|-------|
| Product line sold | Managed databases |
| HG SKU | `Amazon Aurora PostgreSQL` (id: `31269`) |
| HG category | `Database Development` |
| Intent topic (HG) | `Amazon RDS For MariaDB` |
| Binding confidence | high |

### Product-specific HG features used in scoring

| Criterion | MCP tool | HG fields driven by this product binding |
|-----------|----------|------------------------------------------|
| Technology Category Need | `company_technographic` | Max `intensity` in **`Database Development`** |
| Purchase Intent Signal | `company_intent` | Topic **`Amazon RDS For MariaDB`** → `topics[].score`, `topics[].last_seen_at` |
| Product Adoption Momentum | `company_install_time_series` | `intensity_momentum` for target SKU |

These bindings are **differentiating**: changing the selected product changes which HG product, category, and intent topic are queried — and therefore changes need, intent, and momentum for every prospect.

### Competitor extraction audit

- Tool/method: `get_product_information(includeCompetitors=True)`
- Query product: `Amazon Aurora PostgreSQL`
- Status: `resolved`
- Competitor products extracted: **3**
- Accepted fields are explicit competitor/alternative product fields only; no competitors are guessed from free text.

## 4. ICP thresholds (prospect universe — not the PRS score)

Four filters are defined in `ideal_customer_profile.filters`. Three numeric floors are **user-defined at seller profile setup**; the fourth is a **technographic search rule**.

- **min_revenue_usd** >= 71692400 — HG field: `company_firmographic.revenue`. Default floor (non-interactive run or legacy profile without user floors).
- **min_employees** >= 200 — HG field: `company_firmographic.employeeCount`. Default floor (non-interactive run or legacy profile without user floors).
- **min_it_spend_usd** >= 2613988 — HG field: `company_spend.totalSpendAmount (Total IT)`. Default floor (non-interactive run or legacy profile without user floors).
- **category_adjacency_search** technographic_signal Database Development — HG field: `company_technographic.categories / search_companies`. Prospects should show activity in the same HG category as the sold product to avoid scoring random accounts with zero category fit.
- **exclude_target_product_installed** excludeTechnologies Amazon Aurora PostgreSQL — HG field: `search_companies.excludeTechnologies`. Land motion only: exclude accounts where the seller HG SKU is already installed.

**Why 3 numeric ICP lines + 1 search rule:** revenue, employee, and IT spend floors are thresholds you set in the terminal when creating the seller profile. **category_adjacency_search** restricts `search_companies` to accounts tagged with the seller product's HG category.

## 5. Differentiating elements for interview discussion

**Seller-side (profile granularity):**

1. **Product binding** — SKU `Amazon Aurora PostgreSQL` and category `Database Development` define what “installed” and “need” mean.
2. **Intent topic** — `Amazon RDS For MariaDB` must exist in HG; if wrong, Purchase Intent collapses to 0 with 0% reliability.
3. **ICP floors** — derived ratios vs seller revenue/employees/IT spend (see JSON values).
4. **Binding confidence** — whether HG catalog match was exact or approximate.

**Prospect-side (differentiating data per account):**

- `company_firmographic.revenue` / `employeeCount` → Company Size Fit
- `company_spend` Total IT → Estimated IT Budget Capacity
- Category intensities → Technology Category Need
- Intent topic score + freshness → Purchase Intent Signal
- `intensity_momentum` → Product Adoption Momentum

## 6. Prospect Revenue Score formula reference

Prospect Revenue Score = 25% × Company Size Fit + 20% × Estimated IT Budget Capacity + 20% × Technology Category Need + 20% × Purchase Intent Signal + 15% × Product Adoption Momentum

PRS score reliability = 25% × reliability_size + 20% × reliability_budget + 20% × reliability_need + 20% × reliability_intent + 15% × reliability_momentum

PRS criterion math and worked examples: `technical_scoring.md`.
