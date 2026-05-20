# Technical Scoring Details

## Per-prospect calculations

Seller: Amazon.com, Inc. | Product: Amazon AppFlow

### Northland Clothing Company (`northland-clothing.com`)

**Prospect Revenue Score:** 14.3/100

**PRS score reliability:** 42%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **0/2** HG fields (none among expected: `company_spend.spendByCategory[Total IT].totalSpendAmount`, `company_spend.unknownRowCount`) → reliability **0%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Company Size Fit

- S_rev = min(100, 100 × log10(revenue / 1,000,000) / log10(1000))
- ```
= min(100, 100 × log10(3,000,000 / 1,000,000) / 3)
```

```
- ```
  = 15.9
```

- S_emp = min(100, 100 × employeeCount / 10,000)
- ```
= min(100, 100 × 20 / 10,000)
```

```
- ```
  = 0.2
```

- S_size = max(S_rev, S_emp) = max(15.9, 0.2) = 15.9
- reliability_size = (2 / 2) = 1
- Normalized score: 15.9/100
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

- Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = 11.48 / 0.8 = 14.35
- - 0.25 × 15.9 (Company Size Fit) = 3.98
- - 0.2 × 0 (Technology Category Need) = 0
- - 0.2 × 0 (Purchase Intent Signal) = 0
- - 0.15 × 50 (Product Adoption Momentum) = 7.5
- PRS score reliability = 0.42 / 1 = 0.42

---

### SUPERIOR MACHINES LTD (`superiormachines.co.uk`)

**Prospect Revenue Score:** 11.2/100

**PRS score reliability:** 52%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **1/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount` (missing: `company_spend.unknownRowCount`)) → reliability **50%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Company Size Fit

- S_rev = min(100, 100 × log10(revenue / 1,000,000) / log10(1000))
- ```
= min(100, 100 × log10(3,463,155 / 1,000,000) / 3)
```

```
- ```
  = 17.98
```

- S_emp = min(100, 100 × employeeCount / 10,000)
- ```
= min(100, 100 × 20 / 10,000)
```

```
- ```
  = 0.2
```

- S_size = max(S_rev, S_emp) = max(17.98, 0.2) = 17.98
- reliability_size = (2 / 2) = 1
- Normalized score: 18.0/100
- Reliability: 100%

#### Estimated IT Budget Capacity

- S_budget = min(100, 100 × log10(totalSpendAmount / 100,000) / 4)
- ```
 = min(100, 100 × log10(69,457 / 100,000) / 4)
```

```
- ```
   = -3.96
```

- reliability_budget = (1 / 2) = 0.5
- Normalized score: -4.0/100
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

- Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = 11.2 / 1 = 11.2
- - 0.25 × 17.98 (Company Size Fit) = 4.5
- - 0.2 × -3.96 (Estimated IT Budget Capacity) = -0.79
- - 0.2 × 0 (Technology Category Need) = 0
- - 0.2 × 0 (Purchase Intent Signal) = 0
- - 0.15 × 50 (Product Adoption Momentum) = 7.5
- PRS score reliability = 0.52 / 1 = 0.52

---

### Meitai Investment (Suzhou) Co.,Ltd. (`spigroups.com`)

**Prospect Revenue Score:** 9.4/100

**PRS score reliability:** 52%

- Company Size Fit: **2/2** HG fields (`company_firmographic.revenue`, `company_firmographic.employeeCount`) → reliability **100%**
- Estimated IT Budget Capacity: **1/2** HG fields (`company_spend.spendByCategory[Total IT].totalSpendAmount` (missing: `company_spend.unknownRowCount`)) → reliability **50%**
- Technology Category Need: **1/2** HG fields (`list_product_categories (category)` (missing: `company_technographic.products.intensity`)) → reliability **50%**
- Purchase Intent Signal: **0/3** HG fields (none among expected: `company_intent.topics[].score`, `company_intent.topics[].last_seen_at`, `intent topic match`) → reliability **0%**
- Product Adoption Momentum: **0/1** HG fields (none among expected: `company_install_time_series.products[].intensity_momentum`) → reliability **50%**

#### Company Size Fit

- S_rev = min(100, 100 × log10(revenue / 1,000,000) / log10(1000))
- ```
= min(100, 100 × log10(113,596 / 1,000,000) / 3)
```

```
- ```
  = -31.49
```

- S_emp = min(100, 100 × employeeCount / 10,000)
- ```
= min(100, 100 × 7 / 10,000)
```

```
- ```
  = 0.07
```

- S_size = max(S_rev, S_emp) = max(-31.49, 0.07) = 0.07
- reliability_size = (2 / 2) = 1
- Normalized score: 0.1/100
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

- Prospect Revenue Score = sum(w_i × S_i) / sum(w_i) = 7.52 / 0.8 = 9.4
- - 0.25 × 0.07 (Company Size Fit) = 0.02
- - 0.2 × 0 (Technology Category Need) = 0
- - 0.2 × 0 (Purchase Intent Signal) = 0
- - 0.15 × 50 (Product Adoption Momentum) = 7.5
- PRS score reliability = 0.52 / 1 = 0.52

---

