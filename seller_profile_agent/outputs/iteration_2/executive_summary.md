# Executive Sales Intelligence Report

## Iteration 2

---

## 1. Executive Summary

This report prioritizes **3 prospects** for **Amazon.com, Inc.** selling **Amazon AppFlow** (HG SKU: `Amazon AppFlow`).

ICP filtering produced **149 ICP-compatible candidate companies** documented in `candidate_companies.md`.

**Global formula:**

- Prospect Revenue Score =
- 25% **Company Size Fit** — How large the account is (revenue and employees).
- 20% **Estimated IT Budget Capacity** — Whether HG shows enough IT spend to fund a deal.
- 20% **Technology Category Need** — How active they are in your product's HG category.
- 20% **Purchase Intent Signal** — Whether HG sees recent buying interest on your topic.
- 15% **Product Adoption Momentum** — Whether usage of your product is rising or falling.

### Randomly Picked Companies From ICP Candidates

1. **Northland Clothing Company** — Prospect Revenue Score 14.3/100, PRS score reliability 42%
2. **SUPERIOR MACHINES LTD** — Prospect Revenue Score 11.2/100, PRS score reliability 52%
3. **Meitai Investment (Suzhou) Co.,Ltd.** — Prospect Revenue Score 9.4/100, PRS score reliability 52%

---

## 2. Prospect Ranking Overview

Only randomly sampled accounts with a full Prospect Revenue Score appear here, sorted by PRS descending.


| Rank | Company                             | Prospect Revenue Score (/100) | PRS score reliability |
| ---- | ----------------------------------- | ----------------------------- | --------------------- |
| 1    | Northland Clothing Company          | 14.3                          | 42%                   |
| 2    | SUPERIOR MACHINES LTD               | 11.2                          | 52%                   |
| 3    | Meitai Investment (Suzhou) Co.,Ltd. | 9.4                           | 52%                   |


---

## 3. Seller Product Impact Analysis

Elements from `seller_profile.json` that **directly change** scores (detail: `seller_profile.md`):

### ICP candidate filtering inputs

- **Seller product excluded from candidates** (`Amazon AppFlow`) → excluded at ICP via `search_companies.excludeTechnologies`, so the candidate pool focuses on accounts that do not already use the sold product.
- **Minimum company size required for ICP** (revenue / employees / IT spend vs seller) → computed from seller `company_firmographic`; `revenueMin` and `employeesMin` are sent to `search_companies`, while IT spend is checked when present and measured in deep scoring with `company_spend`.
- **Product sold by the sales user:** Amazon AppFlow → selected in the terminal.
  - `methodology_binding.py` matches this business label to HG catalog data: product/SKU, category, intent topic, and competitor products.
  - It then uses those HG parameters to build the ICP filters used by `search_companies`.

### Deep PRS scoring inputs

- **Technology category used to measure need** (`HG technographic product`) → used for Technology Category Need; during deep scoring, `company_technographic` reads installed products/categories and their intensity in this category.
- **Buying-intent topic to look for** (`None`) → used for Purchase Intent Signal; during deep scoring, `company_intent` reads `topics[].score` and `topics[].last_seen_at` for this topic.

---

## 4. Prospect Cards

### #1 — Northland Clothing Company


| Metric                        | Value |
| ----------------------------- | ----- |
| Prospect Revenue Score (/100) | 14.3  |
| PRS score reliability         | 42%   |


#### PRS Score Details (full calculations: `technical_scoring.md`)

**Prospect Revenue Score:** 14.3/100

- Company Size Fit = 15.9/100 because the score uses the stronger signal: revenue score 15.9 from $3.0M revenue, employee score 0.2 from 20 employees.
- Technology Category Need = 0/100 because the category `HG technographic product` is known, but `company_technographic` did not return a usable installed-product intensity in that category.
- Purchase Intent Signal = 0/100 because `company_intent` returned no matched topic score for `Amazon AppFlow`.
- Product Adoption Momentum = 50/100 because `company_install_time_series` did not find the target product; the scoring engine uses a neutral momentum value.
- Estimated IT Budget Capacity is not included in the PRS because it is not calculable.
- Final PRS = weighted average of calculable criteria only (active weight: 80%) = 14.3/100.

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
- **Data gap:** PRS score reliability 42% — validate HG spend and technographics before executive sponsorship.

---

### #2 — SUPERIOR MACHINES LTD


| Metric                        | Value |
| ----------------------------- | ----- |
| Prospect Revenue Score (/100) | 11.2  |
| PRS score reliability         | 52%   |


#### PRS Score Details (full calculations: `technical_scoring.md`)

**Prospect Revenue Score:** 11.2/100

- Company Size Fit = 18.0/100 because the score uses the stronger signal: revenue score 18.0 from $3.5M revenue, employee score 0.2 from 20 employees.
- Estimated IT Budget Capacity = -4.0/100 because `company_spend` returned Total IT spend of $69,457, normalized on a log scale.
- Technology Category Need = 0/100 because the category `HG technographic product` is known, but `company_technographic` did not return a usable installed-product intensity in that category.
- Purchase Intent Signal = 0/100 because `company_intent` returned no matched topic score for `Amazon AppFlow`.
- Product Adoption Momentum = 50/100 because `company_install_time_series` did not find the target product; the scoring engine uses a neutral momentum value.
- Final PRS = weighted average of calculable criteria only (active weight: 100%) = 11.2/100.

#### PRS Score Reliability

**PRS score reliability:** 52%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **1/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount` (missing: `company_spend.unknownRowCount`)) → reliability **50%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Commercial Brief (HG-Evidenced)

- No major positive HG signal beyond ICP compatibility and completed PRS scoring.
- **No intent evidence:** HG returned no `company_intent` topic match for `bound intent topic` — do not claim active buying signal in outreach.
- **Data gap:** PRS score reliability 52% — validate HG spend and technographics before executive sponsorship.

---

### #3 — Meitai Investment (Suzhou) Co.,Ltd.


| Metric                        | Value |
| ----------------------------- | ----- |
| Prospect Revenue Score (/100) | 9.4   |
| PRS score reliability         | 52%   |


#### PRS Score Details (full calculations: `technical_scoring.md`)

**Prospect Revenue Score:** 9.4/100

- Company Size Fit = 0.1/100 because the score uses the stronger signal: revenue score -31.5 from $113,596 revenue, employee score 0.1 from 7 employees.
- Technology Category Need = 0/100 because the category `HG technographic product` is known, but `company_technographic` did not return a usable installed-product intensity in that category.
- Purchase Intent Signal = 0/100 because `company_intent` returned no matched topic score for `Amazon AppFlow`.
- Product Adoption Momentum = 50/100 because `company_install_time_series` did not find the target product; the scoring engine uses a neutral momentum value.
- Estimated IT Budget Capacity is not included in the PRS because it is not calculable.
- Final PRS = weighted average of calculable criteria only (active weight: 80%) = 9.4/100.

#### PRS Score Reliability

**PRS score reliability:** 52%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **1/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount` (missing: `company_spend.unknownRowCount`)) → reliability **50%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Commercial Brief (HG-Evidenced)

- No major positive HG signal beyond ICP compatibility and completed PRS scoring.
- **No intent evidence:** HG returned no `company_intent` topic match for `bound intent topic` — do not claim active buying signal in outreach.
- **Data gap:** PRS score reliability 52% — validate HG spend and technographics before executive sponsorship.

---

