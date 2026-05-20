# Technical Scoring Details

## Per-prospect calculations

Seller: Amazon.com, Inc. | Product: Managed databases

### Guangzhou Orsan Gourmet Powder Co. Ltd. (`tateandlyle.com`)

**Prospect Revenue Score:** 45.7/100

**PRS score reliability:** 62%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **2/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount`, `company_spend.unknownRowCount`) → reliability **100%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Company Size Fit

- S_rev = min(100, 100 × log10(revenue / 1,000,000) / log10(1000))
-       = min(100, 100 × log10(2,208,700,768 / 1,000,000) / 3)
-       = 100
- S_emp = min(100, 100 × employeeCount / 10,000)
-       = min(100, 100 × 5,000 / 10,000)
-       = 50
- S_size = max(S_rev, S_emp) = max(100, 50) = 100
- reliability_size = (2 / 2) = 1
- Normalized score: 100/100
- Reliability: 100%

#### Estimated IT Budget Capacity

- S_budget = min(100, 100 × log10(totalSpendAmount / 100,000) / 4)
-        = min(100, 100 × log10(43,224,174 / 100,000) / 4)
-        = 65.89
- reliability_budget = (2 / 2) = 1
- Normalized score: 65.9/100
- Reliability: 100%

#### Technology Category Need

- HG category: Database Development
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

- Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = 45.68 / 1 = 45.68
-   + 0.25 × 100 (Company Size Fit) = 25
-   + 0.2 × 65.89 (Estimated IT Budget Capacity) = 13.18
-   + 0.2 × 0 (Technology Category Need) = 0
-   + 0.2 × 0 (Purchase Intent Signal) = 0
-   + 0.15 × 50 (Product Adoption Momentum) = 7.5
- PRS score reliability = 0.62 / 1 = 0.62

---

### J.V. Driver Projects Inc (`jvdriver.com`)

**Prospect Revenue Score:** 19.7/100

**PRS score reliability:** 38%

- Company Size Fit: **0/2** HG fields (none among expected: `company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **0%**
- Estimated IT Budget Capacity: **2/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount`, `company_spend.unknownRowCount`) → reliability **100%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Company Size Fit

- S_size = not calculable (revenue and employeeCount missing)
- reliability_size = (0 / 2) = 0
- Normalized score: N/A/100
- Reliability: 0%

#### Estimated IT Budget Capacity

- S_budget = min(100, 100 × log10(totalSpendAmount / 100,000) / 4)
-        = min(100, 100 × log10(2,832,043 / 100,000) / 4)
-        = 36.3
- reliability_budget = (2 / 2) = 1
- Normalized score: 36.3/100
- Reliability: 100%

#### Technology Category Need

- HG category: Database Development
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

- Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = 14.76 / 0.75 = 19.68
-   + 0.2 × 36.3 (Estimated IT Budget Capacity) = 7.26
-   + 0.2 × 0 (Technology Category Need) = 0
-   + 0.2 × 0 (Purchase Intent Signal) = 0
-   + 0.15 × 50 (Product Adoption Momentum) = 7.5
- PRS score reliability = 0.38 / 1 = 0.38

---
