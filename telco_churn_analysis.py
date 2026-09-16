"""
Telco Customer Churn Analysis
=============================
End-to-end analysis of customer churn drivers and revenue impact,
using the IBM Telco Customer Churn dataset.

Pipeline: Python (this script) -> PostgreSQL -> Power BI

Sections:
    1. Data Loading & Cleaning
    2. Feature Engineering
    3. Q1 - Overall Churn Rate
    4. Q2 - Churn by Demographics
    5. Q3 - Churn by Tenure
    6. Q4 - Churn by Contract Type
    7. Q5 - Churn by Services
    8. Q6 - Churn by Billing & Payment
    9. Q7 - Revenue Impact & High-Value Customer Churn
    10. Q8 - Priority Segment Table
"""

import numpy as np
import pandas as pd

RAW_DATA_PATH = "data/WA_Fn-UseC_-Telco-Customer-Churn.csv"
CLEANED_DATA_PATH = "data/telco_cleaned.csv"


# ============================================================
# 1. Data Loading & Cleaning
# ============================================================

df = pd.read_csv(RAW_DATA_PATH)

print(f"Dataset shape: {df.shape}")
print(df.info())

# TotalCharges is loaded as text because a handful of rows contain
# blank strings instead of numbers. Coerce to numeric so blanks become NaN.
df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")

n_missing_total_charges = df["TotalCharges"].isnull().sum()
print(f"Rows with missing TotalCharges: {n_missing_total_charges}")

# Inspect who these blank rows are before deciding how to handle them.
print(df.loc[df["TotalCharges"].isnull(), ["tenure", "MonthlyCharges", "TotalCharges"]])
# -> All 11 blank rows have tenure == 0, i.e. brand-new customers who
#    haven't been billed yet. Filling with 0 is the correct, non-distorting choice.
df["TotalCharges"] = df["TotalCharges"].fillna(0)

# Confirm there are no duplicate customer records.
n_duplicate_ids = df["customerID"].duplicated().sum()
print(f"Duplicate customerIDs: {n_duplicate_ids}")

# Binary version of the target variable, used throughout for aggregation.
df["churn_numeric"] = df["Churn"].map({"Yes": 1, "No": 0})


# ============================================================
# 2. Feature Engineering
# ============================================================

# Tenure buckets: group customers by how long they've been with the company.
tenure_conditions = [
    df["tenure"] == 0,
    (df["tenure"] >= 1) & (df["tenure"] <= 12),
    (df["tenure"] > 12) & (df["tenure"] <= 48),
    (df["tenure"] > 48) & (df["tenure"] <= 72),
]
tenure_labels = ["Not Applicable", "New", "Mid-Level", "Loyal"]
df["tenure_bucket"] = np.select(tenure_conditions, tenure_labels, default="Out of Range")

# Charge tiers: split customers into 5 equal-sized groups by MonthlyCharges,
# used later for the "High charge tier" segment in the priority table.
df["charge_tier"] = pd.qcut(
    df["MonthlyCharges"], q=5, labels=["Low", "Upper Low", "Mid", "Upper Mid", "High"]
)

# Save the cleaned & feature-engineered dataset. The RAW file above is never
# modified -- this is a separate output so the analysis stays reproducible.
df.to_csv(CLEANED_DATA_PATH, index=False)
print(f"Cleaned dataset saved to: {CLEANED_DATA_PATH}")


# ============================================================
# 3. Q1 - Overall Churn Rate
# ============================================================

total_customers = df["customerID"].shape[0]
total_churned = df["churn_numeric"].sum()
churn_rate = (total_churned / total_customers) * 100

churned_revenue = df.loc[df["churn_numeric"] == 1, "MonthlyCharges"].sum()

print("\n--- Q1: Overall Churn Rate ---")
print(f"Total customers: {total_customers}")
print(f"Churned customers: {total_churned}")
print(f"Churn rate: {churn_rate:.2f}%")
print(f"Baseline churned revenue (monthly): ${churned_revenue:,.2f}")


# ============================================================
# 4. Q2 - Churn by Demographics
# ============================================================

partner_churn = df.groupby("Partner")["churn_numeric"].mean() * 100
senior_churn = df.groupby("SeniorCitizen")["churn_numeric"].mean() * 100
dependents_churn = df.groupby("Dependents")["churn_numeric"].mean() * 100

print("\n--- Q2: Churn by Demographics ---")
print("Partner:\n", partner_churn)
print("Senior Citizen:\n", senior_churn)
print("Dependents:\n", dependents_churn)
# Insight: household ties (Partner/Dependents) lower churn, but SeniorCitizen
# raises it -- an opposite pattern worth flagging as a distinct risk group.


# ============================================================
# 5. Q3 - Churn by Tenure
# ============================================================

tenure_churn = df.groupby("tenure")["churn_numeric"].agg(["sum", "count"])
tenure_churn["churn_rate_pct"] = (tenure_churn["sum"] / tenure_churn["count"]) * 100

print("\n--- Q3: Churn by Tenure ---")
print(tenure_churn.head(10))
# Insight: churn peaks sharply at tenure=1 (~62%, n~613) then declines steadily.
# tenure=0 (11 customers) is excluded from interpretation -- sample too small.


# ============================================================
# 6. Q4 - Churn by Contract Type
# ============================================================

contract_churn = df.groupby("Contract")["churn_numeric"].agg(["sum", "count"])
contract_churn["churn_rate_pct"] = (contract_churn["sum"] / contract_churn["count"]) * 100

print("\n--- Q4: Churn by Contract Type ---")
print(contract_churn)
# Insight: Month-to-month is the strongest single predictor of churn (~42.71%)
# and the largest segment (~55% of customers) -> drives ~87% of churned revenue.


# ============================================================
# 7. Q5 - Churn by Services
# ============================================================

service_columns = [
    "PhoneService", "MultipleLines", "InternetService",
    "OnlineSecurity", "OnlineBackup", "DeviceProtection",
    "TechSupport", "StreamingTV", "StreamingMovies",
]

print("\n--- Q5: Churn by Services ---")
for col in service_columns:
    print(f"\n{col}:")
    print(df.groupby(col)["churn_numeric"].mean() * 100)
# Insight: Fiber optic churns far more than DSL (41.89% vs 18.96%). Add-on
# services (OnlineSecurity, TechSupport, etc.) roughly halve churn when present.


# ============================================================
# 8. Q6 - Churn by Billing & Payment
# ============================================================

payment_churn = df.groupby("PaymentMethod")["churn_numeric"].mean() * 100
paperless_churn = df.groupby("PaperlessBilling")["churn_numeric"].mean() * 100

print("\n--- Q6: Churn by Billing & Payment ---")
print("Payment Method:\n", payment_churn)
print("Paperless Billing:\n", paperless_churn)
# Insight: Electronic check churns highest by far (45.29%). Paperless billing
# customers churn ~2x more than non-paperless (33.57% vs 16.33%).


# ============================================================
# 9. Q7 - Revenue Impact & High-Value Customer Churn
# ============================================================

churned = df[df["churn_numeric"] == 1]
retained = df[df["churn_numeric"] == 0]

print("\n--- Q7: Revenue Impact ---")
print(f"Churned avg MonthlyCharges: ${churned['MonthlyCharges'].mean():.2f}")
print(f"Retained avg MonthlyCharges: ${retained['MonthlyCharges'].mean():.2f}")

total_revenue = df["MonthlyCharges"].sum()
revenue_churn_rate = (churned["MonthlyCharges"].sum() / total_revenue) * 100
print(f"Revenue churn rate: {revenue_churn_rate:.2f}% (vs {churn_rate:.2f}% by headcount)")

charge_tier_churn = df.groupby("charge_tier")["churn_numeric"].mean() * 100
print("Churn rate by charge tier:\n", charge_tier_churn)

# Compounding-risk check: do risk factors stack, or just overlap?
mtm_churn_rate = df.loc[df["Contract"] == "Month-to-month", "churn_numeric"].mean() * 100

mtm_ec_mask = (df["Contract"] == "Month-to-month") & (df["PaymentMethod"] == "Electronic check")
mtm_ec_churn_rate = df.loc[mtm_ec_mask, "churn_numeric"].mean() * 100
mtm_ec_count = mtm_ec_mask.sum()

mtm_ec_fiber_mask = mtm_ec_mask & (df["InternetService"] == "Fiber optic")
mtm_ec_fiber_churn_rate = df.loc[mtm_ec_fiber_mask, "churn_numeric"].mean() * 100
mtm_ec_fiber_count = mtm_ec_fiber_mask.sum()

print("\nCompounding risk check:")
print(f"Month-to-month alone: {mtm_churn_rate:.2f}%")
print(f"+ Electronic check: {mtm_ec_churn_rate:.2f}% (n={mtm_ec_count})")
print(f"+ Fiber optic: {mtm_ec_fiber_churn_rate:.2f}% (n={mtm_ec_fiber_count})")
# Insight: risk factors compound rather than overlap -- this combined segment
# churns at more than 2x the baseline rate. The standout finding of the project.


# ============================================================
# 10. Q8 - Priority Segment Table
# ============================================================
# Priority score = churn_rate x monthly_total_revenue (revenue-weighted,
# not headcount-weighted, since the project's motivation is revenue impact).
# Baseline is intentionally excluded -- it isn't an actionable segment.

def segment_stats(mask):
    """Return (count, churn_rate, churned_revenue, total_revenue) for a boolean mask."""
    segment = df[mask]
    count = segment.shape[0]
    churn_rate_ = segment["churn_numeric"].mean()
    churned_revenue_ = segment.loc[segment["churn_numeric"] == 1, "MonthlyCharges"].sum()
    total_revenue_ = segment["MonthlyCharges"].sum()
    return count, churn_rate_, churned_revenue_, total_revenue_

segment_masks = {
    "Month-to-month": df["Contract"] == "Month-to-month",
    "Electronic check": df["PaymentMethod"] == "Electronic check",
    "Fiber optic": df["InternetService"] == "Fiber optic",
    "High charge tier": df["charge_tier"] == "High",
    "Month-to-month + Electronic check": mtm_ec_mask,
    "Month-to-month + Electronic check + Fiber optic": mtm_ec_fiber_mask,
}

rows = []
for name, mask in segment_masks.items():
    count, rate, churned_rev, total_rev = segment_stats(mask)
    rows.append({
        "segment": name,
        "total_customers": count,
        "churn_rate": round(rate, 4),
        "churned_total_revenue": round(churned_rev, 2),
        "monthly_total_revenue": round(total_rev, 2),
    })

priority_df = pd.DataFrame(rows)
priority_df["priority_score"] = priority_df["churn_rate"] * priority_df["monthly_total_revenue"]
priority_df = priority_df.sort_values("priority_score", ascending=False).reset_index(drop=True)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)

print("\n--- Q8: Priority Segment Table ---")
print(priority_df)
# Insight: Fiber optic ranks #1 by revenue exposure despite a lower churn rate
# than the compound segments, because its larger customer base means more
# total dollars at risk. The triple-compound segment has the highest churn
# rate in the analysis (60.37%) but ranks lower here due to its smaller size --
# still worth flagging as a high-risk customer profile for targeted retention.

priority_df.to_csv("data/priority_segments.csv", index=False)
print("\nPriority segment table saved to: data/priority_segments.csv")
