# Executive Sales Intelligence Report
## Test

---

## 1. Executive Summary

This report prioritizes **1 prospects** for **Amazon.com, Inc.** selling **Alexa Certify** (HG SKU: `Alexa Certify`).

ICP filtering produced **164 ICP-compatible candidate companies** documented in `candidate_companies.md`.

**Global formula:**

- Prospect Revenue Score =
- 25% **Company Size Fit** — How large the account is (revenue and employees).
- 20% **Estimated IT Budget Capacity** — Whether HG shows enough IT spend to fund a deal.
- 20% **Technology Category Need** — How active they are in your product's HG category.
- 20% **Purchase Intent Signal** — Whether HG sees recent buying interest on your topic.
- 15% **Product Adoption Momentum** — Whether usage of your product is rising or falling.

### Randomly Picked Companies From ICP Candidates

1. **6Sigma EPCM** — Prospect Revenue Score 19.8/100, PRS score reliability 42%

---

## 2. Prospect Ranking Overview

Only randomly sampled accounts with a full Prospect Revenue Score appear here, sorted by PRS descending.

| Rank | Company | Prospect Revenue Score (/100) | PRS score reliability |
|------|---------|-------------------------------|-------------------|
| 1 | 6Sigma EPCM | 19.8 | 42% |

---

## 3. Seller Product Impact Analysis

Elements from `seller_profile.json` that **directly change** scores:

### ICP candidate filtering inputs

- **Seller product excluded from candidates** (`Alexa Certify`) → excluded at ICP via `search_companies.excludeTechnologies`, so the candidate pool focuses on accounts that do not already use the sold product.
- **Minimum company size required for ICP** (revenue / employees / IT spend vs seller) → computed from seller `company_firmographic`; `revenueMin` and `employeesMin` are sent to `search_companies`, while IT spend is checked when present and measured in deep scoring with `company_spend`.
- **Product sold by the sales user:** Alexa Certify → selected in the terminal.
  - `methodology_binding.py` matches this business label to HG catalog data: product/SKU, category, intent topic, and competitor products.
  - It then uses those HG parameters to build the ICP filters used by `search_companies`.

### Deep PRS scoring inputs

- **Technology category used to measure need** (`HG technographic product`) → used for Technology Category Need; during deep scoring, `company_technographic` reads installed products/categories and their intensity in this category.
- **Buying-intent topic to look for** (`None`) → used for Purchase Intent Signal; during deep scoring, `company_intent` reads `topics[].score` and `topics[].last_seen_at` for this topic.

---

## 4. Prospect Cards

### #1 — 6Sigma EPCM

| Metric | Value |
|--------|-------|
| Prospect Revenue Score (/100) | 19.8 |
| PRS score reliability | 42% |

#### PRS Score Details (full calculations: `technical_scoring.md`)

**Prospect Revenue Score:** 19.8/100

- Company Size Fit = 33.3/100 because the score uses the stronger signal: revenue score 33.3 from $10.0M revenue, employee score 2 from 200 employees.
- Technology Category Need = 0/100 because the category `HG technographic product` is known, but `company_technographic` did not return a usable installed-product intensity in that category.
- Purchase Intent Signal = 0/100 because `company_intent` returned no matched topic score for `Alexa Certify`.
- Product Adoption Momentum = 50/100 because `company_install_time_series` did not find the target product; the scoring engine uses a neutral momentum value.
- Estimated IT Budget Capacity is not included in the PRS because it is not calculable.
- Final PRS = weighted average of calculable criteria only (active weight: 80%) = 19.8/100.

#### PRS Score Reliability

**PRS score reliability:** 42%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **0/2** HG fields (none among expected: `company_spend.spendByCategory[Total IT].totalSpendAmount`, `company_spend.unknownRowCount`) → reliability **0%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Commercial Brief (HG-Evidenced)

- No major positive HG signal beyond ICP compatibility and completed PRS scoring.
- **No intent evidence:** HG returned no `company_intent` topic match for `bound intent topic` — do not claim active buying signal in outreach.
- **Data gap:** PRS score reliability 42% — validate HG spend and technographics before prospection calls.

---

