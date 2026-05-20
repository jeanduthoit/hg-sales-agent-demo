# Technical Scoring Details

## Per-prospect calculations

Seller: Amazon.com, Inc. | Product: Alexa Certify

### 6Sigma EPCM (`6s.co.za`)

**Prospect Revenue Score:** 19.8/100

**PRS score reliability:** 42%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **0/2** HG fields (none among expected: `company_spend.spendByCategory[Total IT].totalSpendAmount`, `company_spend.unknownRowCount`) → reliability **0%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Company Size Fit

- S_rev = max(0, min(100, 100 × log10(revenue / 1,000,000) / log10(1000)))
-       = max(0, min(100, 100 × log10(10,000,000 / 1,000,000) / 3))
-       = 33.33
- S_emp = min(100, 100 × employeeCount / 10,000)
-       = min(100, 100 × 200 / 10,000)
-       = 2
- S_size = max(S_rev, S_emp) = max(33.33, 2) = 33.33
- reliability_size = (2 / 2) = 1
- Normalized score: 33.3/100
- Reliability: 100%

#### Estimated IT Budget Capacity

- S_budget = not calculable (Total IT spend missing or zero)
- reliability_budget = (0 / 2) = 0
- Normalized score: N/A/100
- Reliability: 0%

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

- Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = 15.83 / 0.8 = 19.79
-   + 0.25 × 33.33 (Company Size Fit) = 8.33
-   + 0.2 × 0 (Technology Category Need) = 0
-   + 0.2 × 0 (Purchase Intent Signal) = 0
-   + 0.15 × 50 (Product Adoption Momentum) = 7.5
- PRS score reliability = 0.42 / 1 = 0.42

---
