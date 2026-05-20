# Executive Sales Intelligence Report
## Demo

---

## 1. Executive Summary

This report prioritizes **3 prospects** for **Amazon.com, Inc.** selling **Amazon API Gateway** (HG SKU: `Amazon API Gateway`).

ICP filtering produced **156 ICP-compatible candidate companies** documented in `candidate_companies.md`.

**Global formula:**

- Prospect Revenue Score =
- 25% **Company Size Fit** — How large the account is (revenue and employees).
- 20% **Estimated IT Budget Capacity** — Whether HG shows enough IT spend to fund a deal.
- 20% **Technology Category Need** — How active they are in your product's HG category.
- 20% **Purchase Intent Signal** — Whether HG sees recent buying interest on your topic.
- 15% **Product Adoption Momentum** — Whether usage of your product is rising or falling.

### Randomly Picked Companies From ICP Candidates

1. **KINKI SANGYO SHINYO KUMIAI** — Prospect Revenue Score 39.5/100, PRS score reliability 62%
2. **NESTLE HELLAS SINGLE MEMBER S.A.** — Prospect Revenue Score 38.6/100, PRS score reliability 62%
3. **Elior India Food Services LLP** — Prospect Revenue Score 21.0/100, PRS score reliability 52%

---

## 2. Prospect Ranking Overview

Only randomly sampled accounts with a full Prospect Revenue Score appear here, sorted by PRS descending.

| Rank | Company | Prospect Revenue Score (/100) | PRS score reliability |
|------|---------|-------------------------------|-------------------|
| 1 | KINKI SANGYO SHINYO KUMIAI | 39.5 | 62% |
| 2 | NESTLE HELLAS SINGLE MEMBER S.A. | 38.6 | 62% |
| 3 | Elior India Food Services LLP | 21.0 | 52% |

---

## 3. Seller Product Impact Analysis

Elements from `seller_profile.json` that **directly change** scores:

### ICP candidate filtering inputs

- **Seller product excluded from candidates** (`Amazon API Gateway`) → excluded at ICP via `search_companies.excludeTechnologies`, so the candidate pool focuses on accounts that do not already use the sold product.
- **Minimum company size required for ICP** (revenue / employees / IT spend vs seller) → computed from seller `company_firmographic`; `revenueMin` and `employeesMin` are sent to `search_companies`, while IT spend is checked when present and measured in deep scoring with `company_spend`.
- **Product sold by the sales user:** Amazon API Gateway → selected in the terminal.
  - `methodology_binding.py` matches this business label to HG catalog data: product/SKU, category, intent topic, and competitor products.
  - It then uses those HG parameters to build the ICP filters used by `search_companies`.

### Deep PRS scoring inputs

- **Technology category used to measure need** (`HG technographic product`) → used for Technology Category Need; during deep scoring, `company_technographic` reads installed products/categories and their intensity in this category.
- **Buying-intent topic to look for** (`Amazon API Gateway`) → used for Purchase Intent Signal; during deep scoring, `company_intent` reads `topics[].score` and `topics[].last_seen_at` for this topic.

---

## 4. Prospect Cards

### #1 — KINKI SANGYO SHINYO KUMIAI

| Metric | Value |
|--------|-------|
| Prospect Revenue Score (/100) | 39.5 |
| PRS score reliability | 62% |

#### PRS Score Details (full calculations: `technical_scoring.md`)

**Prospect Revenue Score:** 39.5/100

- Company Size Fit = 78.9/100 because the score uses the stronger signal: revenue score 78.9 from $232.7M revenue, employee score 8.0 from 798 employees.
- Estimated IT Budget Capacity = 61.6/100 because `company_spend` returned Total IT spend of $29.0M, normalized on a log scale.
- Technology Category Need = 0/100 because the category `HG technographic product` is known, but `company_technographic` did not return a usable installed-product intensity in that category.
- Purchase Intent Signal = 0/100 because `company_intent` returned no matched topic score for `Amazon API Gateway`.
- Product Adoption Momentum = 50/100 because `company_install_time_series` did not find the target product; the scoring engine uses a neutral momentum value.
- Final PRS = weighted average of calculable criteria only (active weight: 100%) = 39.5/100.

#### PRS Score Reliability

**PRS score reliability:** 62%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **2/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount`, `company_spend.unknownRowCount`) → reliability **100%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Commercial Brief (HG-Evidenced)

- **Funding capacity:** HG Total IT spend supports a meaningful infrastructure deal (Estimated IT Budget Capacity Score = 61.6/100).
- **Enterprise scale:** Revenue and headcount support a large-platform conversation (Company Size Fit Score = 78.9/100).
- **No intent evidence:** HG returned no `company_intent` topic match for `Amazon API Gateway` — do not claim active buying signal in outreach.

---

### #2 — NESTLE HELLAS SINGLE MEMBER S.A.

| Metric | Value |
|--------|-------|
| Prospect Revenue Score (/100) | 38.6 |
| PRS score reliability | 62% |

#### PRS Score Details (full calculations: `technical_scoring.md`)

**Prospect Revenue Score:** 38.6/100

- Company Size Fit = 88.3/100 because the score uses the stronger signal: revenue score 88.3 from $444.6M revenue, employee score 7.9 from 794 employees.
- Estimated IT Budget Capacity = 45.0/100 because `company_spend` returned Total IT spend of $6.3M, normalized on a log scale.
- Technology Category Need = 0/100 because the category `HG technographic product` is known, but `company_technographic` did not return a usable installed-product intensity in that category.
- Purchase Intent Signal = 0/100 because `company_intent` returned no matched topic score for `Amazon API Gateway`.
- Product Adoption Momentum = 50/100 because `company_install_time_series` did not find the target product; the scoring engine uses a neutral momentum value.
- Final PRS = weighted average of calculable criteria only (active weight: 100%) = 38.6/100.

#### PRS Score Reliability

**PRS score reliability:** 62%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **2/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount`, `company_spend.unknownRowCount`) → reliability **100%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Commercial Brief (HG-Evidenced)

- **Enterprise scale:** Revenue and headcount support a large-platform conversation (Company Size Fit Score = 88.3/100).
- **No intent evidence:** HG returned no `company_intent` topic match for `Amazon API Gateway` — do not claim active buying signal in outreach.

---

### #3 — Elior India Food Services LLP

| Metric | Value |
|--------|-------|
| Prospect Revenue Score (/100) | 21.0 |
| PRS score reliability | 52% |

#### PRS Score Details (full calculations: `technical_scoring.md`)

**Prospect Revenue Score:** 21.0/100

- Company Size Fit = 37.1/100 because the score uses the stronger signal: revenue score 37.1 from $13.0M revenue, employee score 8.0 from 795 employees.
- Technology Category Need = 0/100 because the category `HG technographic product` is known, but `company_technographic` did not return a usable installed-product intensity in that category.
- Purchase Intent Signal = 0/100 because `company_intent` returned no matched topic score for `Amazon API Gateway`.
- Product Adoption Momentum = 50/100 because `company_install_time_series` did not find the target product; the scoring engine uses a neutral momentum value.
- Estimated IT Budget Capacity is not included in the PRS because it is not calculable.
- Final PRS = weighted average of calculable criteria only (active weight: 80%) = 21.0/100.

#### PRS Score Reliability

**PRS score reliability:** 52%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **1/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount` (missing: `company_spend.unknownRowCount`)) → reliability **50%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Commercial Brief (HG-Evidenced)

- No major positive HG signal beyond ICP compatibility and completed PRS scoring.
- **No intent evidence:** HG returned no `company_intent` topic match for `Amazon API Gateway` — do not claim active buying signal in outreach.
- **Data gap:** PRS score reliability 52% — validate HG spend and technographics before prospection calls.

---

