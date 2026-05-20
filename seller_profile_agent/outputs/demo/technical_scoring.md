# Technical Scoring Details

## Per-prospect calculations

Seller: Amazon.com, Inc. | Product: Amazon API Gateway

### KINKI SANGYO SHINYO KUMIAI (`kinsan.co.jp`)

**Prospect Revenue Score:** 39.5/100

**PRS score reliability:** 62%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **2/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount`, `company_spend.unknownRowCount`) → reliability **100%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Company Size Fit

- S_rev = max(0, min(100, 100 × log10(revenue / 1,000,000) / log10(1000)))
-       = max(0, min(100, 100 × log10(232,674,675 / 1,000,000) / 3))
-       = 78.89
- S_emp = min(100, 100 × employeeCount / 10,000)
-       = min(100, 100 × 798 / 10,000)
-       = 7.98
- S_size = max(S_rev, S_emp) = max(78.89, 7.98) = 78.89
- reliability_size = (2 / 2) = 1
- Normalized score: 78.9/100
- Reliability: 100%

#### Estimated IT Budget Capacity

- S_budget = max(0, min(100, 100 × log10(totalSpendAmount / 100,000) / 4))
-        = max(0, min(100, 100 × log10(28,994,931 / 100,000) / 4))
-        = 61.56
- reliability_budget = (2 / 2) = 1
- Normalized score: 61.6/100
- Reliability: 100%

#### Technology Category Need

- HG category: HG technographic product
- No intensity in target category → S_need = 0
- reliability_need = (1 / 2) = 0.5
- Normalized score: 0/100
- Reliability: 50%

#### Purchase Intent Signal

- No company_intent topic for target product → S_intent = 0
- reliability_intent = 0 (topics[].score or topics[].last_seen_at missing)
- Normalized score: 0/100
- Reliability: 0%

#### Product Adoption Momentum

- Product absent from install time series → S_momentum = 50 (neutral)
- reliability_momentum = 0.5
- Normalized score: 50/100
- Reliability: 50%

#### Aggregation

- Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = 39.53 / 1 = 39.53
-   + 0.25 × 78.89 (Company Size Fit) = 19.72
-   + 0.2 × 61.56 (Estimated IT Budget Capacity) = 12.31
-   + 0.2 × 0 (Technology Category Need) = 0
-   + 0.2 × 0 (Purchase Intent Signal) = 0
-   + 0.15 × 50 (Product Adoption Momentum) = 7.5
- PRS score reliability = 0.62 / 1 = 0.62

---

### NESTLE HELLAS SINGLE MEMBER S.A. (`nestle.gr`)

**Prospect Revenue Score:** 38.6/100

**PRS score reliability:** 62%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **2/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount`, `company_spend.unknownRowCount`) → reliability **100%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Company Size Fit

- S_rev = max(0, min(100, 100 × log10(revenue / 1,000,000) / log10(1000)))
-       = max(0, min(100, 100 × log10(444,614,229 / 1,000,000) / 3))
-       = 88.27
- S_emp = min(100, 100 × employeeCount / 10,000)
-       = min(100, 100 × 794 / 10,000)
-       = 7.94
- S_size = max(S_rev, S_emp) = max(88.27, 7.94) = 88.27
- reliability_size = (2 / 2) = 1
- Normalized score: 88.3/100
- Reliability: 100%

#### Estimated IT Budget Capacity

- S_budget = max(0, min(100, 100 × log10(totalSpendAmount / 100,000) / 4))
-        = max(0, min(100, 100 × log10(6,330,719 / 100,000) / 4))
-        = 45.04
- reliability_budget = (2 / 2) = 1
- Normalized score: 45.0/100
- Reliability: 100%

#### Technology Category Need

- HG category: HG technographic product
- No intensity in target category → S_need = 0
- reliability_need = (1 / 2) = 0.5
- Normalized score: 0/100
- Reliability: 50%

#### Purchase Intent Signal

- No company_intent topic for target product → S_intent = 0
- reliability_intent = 0 (topics[].score or topics[].last_seen_at missing)
- Normalized score: 0/100
- Reliability: 0%

#### Product Adoption Momentum

- Product absent from install time series → S_momentum = 50 (neutral)
- reliability_momentum = 0.5
- Normalized score: 50/100
- Reliability: 50%

#### Aggregation

- Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = 38.57 / 1 = 38.57
-   + 0.25 × 88.27 (Company Size Fit) = 22.07
-   + 0.2 × 45.04 (Estimated IT Budget Capacity) = 9.01
-   + 0.2 × 0 (Technology Category Need) = 0
-   + 0.2 × 0 (Purchase Intent Signal) = 0
-   + 0.15 × 50 (Product Adoption Momentum) = 7.5
- PRS score reliability = 0.62 / 1 = 0.62

---

### Elior India Food Services LLP (`elior.in`)

**Prospect Revenue Score:** 21.0/100

**PRS score reliability:** 52%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **1/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount` (missing: `company_spend.unknownRowCount`)) → reliability **50%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Company Size Fit

- S_rev = max(0, min(100, 100 × log10(revenue / 1,000,000) / log10(1000)))
-       = max(0, min(100, 100 × log10(12,993,063 / 1,000,000) / 3))
-       = 37.12
- S_emp = min(100, 100 × employeeCount / 10,000)
-       = min(100, 100 × 795 / 10,000)
-       = 7.95
- S_size = max(S_rev, S_emp) = max(37.12, 7.95) = 37.12
- reliability_size = (2 / 2) = 1
- Normalized score: 37.1/100
- Reliability: 100%

#### Estimated IT Budget Capacity

- S_budget = not calculable (Total IT spend missing or zero)
- reliability_budget = (1 / 2) = 0.5
- Normalized score: N/A/100
- Reliability: 50%

#### Technology Category Need

- HG category: HG technographic product
- No intensity in target category → S_need = 0
- reliability_need = (1 / 2) = 0.5
- Normalized score: 0/100
- Reliability: 50%

#### Purchase Intent Signal

- No company_intent topic for target product → S_intent = 0
- reliability_intent = 0 (topics[].score or topics[].last_seen_at missing)
- Normalized score: 0/100
- Reliability: 0%

#### Product Adoption Momentum

- Product absent from install time series → S_momentum = 50 (neutral)
- reliability_momentum = 0.5
- Normalized score: 50/100
- Reliability: 50%

#### Aggregation

- Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = 16.78 / 0.8 = 20.98
-   + 0.25 × 37.12 (Company Size Fit) = 9.28
-   + 0.2 × 0 (Technology Category Need) = 0
-   + 0.2 × 0 (Purchase Intent Signal) = 0
-   + 0.15 × 50 (Product Adoption Momentum) = 7.5
- PRS score reliability = 0.52 / 1 = 0.52

---
