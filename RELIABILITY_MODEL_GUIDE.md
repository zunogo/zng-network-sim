# Reliability Model Guide

## Overview

The simulator includes interactive visualizations for both **pack failure** and **charger failure** models, helping you understand and configure reliability distributions before running simulations.

---

## Pack Failure Model

### Distribution Type
**Exponential (Constant Hazard Rate)**

### Key Parameters

#### MTBF (Mean Time Between Failures)
- **Definition:** Average operating hours between failures across the entire pack fleet
- **Typical Range:** 20,000 – 100,000 hours
- **Interpretation:**
  - 50,000 hours = ~5.7 years of continuous operation
  - Higher MTBF = more reliable packs, fewer disruptions
  - Covers: BMS faults, cell defects, connector damage, handling accidents

#### MTTR (Mean Time To Repair)
- **Definition:** Average time to diagnose, swap out, and repair a failed pack
- **Typical Range:** 2 – 8 hours
- **Interpretation:**
  - Includes diagnosis, physical swap, and repair/reconditioning
  - Lower MTTR = faster turnaround, less downtime

#### Availability
- **Formula:** MTBF / (MTBF + MTTR)
- **Example:** MTBF = 50,000 hrs, MTTR = 4 hrs → 99.99% availability
- **Interpretation:** Percentage of time packs are operational

### Failure Characteristics

**Memoryless Property:**
- The probability of failure in the next hour is **constant**, regardless of pack age
- Appropriate for random, unpredictable failures
- Does NOT model gradual degradation (that's handled separately by the SOH model)

**When to Use:**
- Proven battery technology with established reliability
- Random failures dominate (not systematic wear-out)
- Field data shows constant failure rate over time

### Visualization Features

1. **Failure Probability (PDF):**
   - Shows when failures are most likely to occur
   - Peak at t=0, exponential decay
   - MTBF marked as vertical line

2. **Reliability Over Time:**
   - Probability that a pack survives to time t
   - 50% survival line marked (median lifetime)
   - Useful for warranty and replacement planning

---

## Charger Failure Model

### Distribution Types

#### 1. Exponential Distribution
**Same as pack failures — constant hazard rate**

- **Use when:** Mature, proven charger technology
- **Characteristics:** Memoryless, random failures
- **Examples:** Power supply faults, connector wear, software glitches

#### 2. Weibull Distribution
**Shape-dependent hazard rate — captures infant mortality or wear-out**

The Weibull shape parameter (β) determines the failure pattern:

##### β < 1: Infant Mortality
- **Failure rate DECREASES over time**
- Early defects and manufacturing issues get weeded out
- Common in new electronics, unproven technology
- **Example:** β = 0.7
  - High failure rate initially
  - Stabilizes as defective units are replaced
  - Good for pilot deployments with new equipment

##### β = 1: Exponential (Special Case)
- **Constant failure rate**
- Equivalent to exponential distribution
- Random, memoryless failures

##### β > 1: Wear-out
- **Failure rate INCREASES over time**
- Mechanical wear, fatigue, aging effects dominate
- Typical for mature equipment approaching end-of-life
- **Example:** β = 2.5
  - Low failure rate when new
  - Accelerates as equipment ages
  - Signals need for proactive replacement strategy

### Key Parameters

#### MTBF (Mean Time Between Failures)
- **Typical Range:** 10,000 – 50,000 hours per charger
- **Interpretation:**
  - 20,000 hours = ~2.3 years of continuous operation
  - Lower than packs due to higher mechanical/electrical stress

#### MTTR (Mean Time To Repair)
- **Typical Range:** 4 – 48 hours
- **Interpretation:**
  - Includes diagnosis, parts procurement, repair/replacement
  - May include waiting for technician availability

#### Weibull Shape (β)
- **Range:** 0.1 – 5.0
- **Default:** 1.0 (exponential)
- **Interpretation:**
  - β = 0.5–0.8: Strong infant mortality
  - β = 0.8–1.2: Approximately constant hazard
  - β = 1.5–3.0: Moderate to strong wear-out

### Visualization Features

1. **Failure Probability (PDF):**
   - Shows when failures are most likely
   - Shape changes dramatically with β:
     - β < 1: Peak at t=0, rapid decay
     - β = 1: Exponential decay from t=0
     - β > 1: Peak shifts right, bell-shaped

2. **Hazard Rate Over Time:**
   - **Critical for understanding failure dynamics**
   - β < 1: Decreasing hazard (infant mortality)
   - β = 1: Flat hazard (constant risk)
   - β > 1: Increasing hazard (wear-out)
   - Informs maintenance strategy

---

## Configuration Recommendations

### Conservative (Risk-Averse)
**For bankable projects, investor presentations**

**Packs:**
- MTBF: 30,000 – 40,000 hours (lower = more conservative)
- MTTR: 6 – 8 hours

**Chargers:**
- Distribution: Weibull with β = 1.5 (moderate wear-out)
- MTBF: 12,000 – 15,000 hours
- MTTR: 24 – 36 hours

**Why:** Assumes higher failure rates, captures wear-out effects, builds in buffer for unexpected issues.

---

### Moderate (Realistic)
**For internal planning, proven technology**

**Packs:**
- MTBF: 50,000 hours
- MTTR: 4 hours

**Chargers:**
- Distribution: Exponential (β = 1.0)
- MTBF: 20,000 hours
- MTTR: 24 hours

**Why:** Based on typical field data for mature battery swap systems.

---

### Optimistic (Best-Case)
**For sensitivity analysis, best-in-class equipment**

**Packs:**
- MTBF: 80,000 – 100,000 hours
- MTTR: 2 hours

**Chargers:**
- Distribution: Exponential
- MTBF: 40,000 – 50,000 hours
- MTTR: 12 hours

**Why:** Assumes premium equipment, excellent maintenance, favorable operating conditions.

---

## How to Use the Visualizations

### Step 1: Enable Preview
In the sidebar, under **"Pack Specs"** or **"Charger Variants"**, check the box:
- ☑ **Show failure distribution**

### Step 2: Interpret the Charts

**Left Chart (Failure Probability):**
- Where is the peak? (When are failures most likely?)
- How wide is the distribution? (Predictability of failure timing)
- Where is the MTBF line relative to the peak?

**Right Chart (Reliability or Hazard Rate):**
- **For packs:** How quickly does reliability decay?
- **For chargers:** Is the hazard rate flat, increasing, or decreasing?

### Step 3: Adjust Parameters
- Increase MTBF → shift distribution right, lower failure rate
- Decrease MTTR → improve availability
- Adjust Weibull β (chargers only):
  - Lower β → model infant mortality
  - Higher β → model wear-out

### Step 4: Validate with Field Data
If you have field data:
1. Run simulation with current parameters
2. Go to **Intelligence** tab → **Field Data Integration**
3. Upload BMS telemetry (packs) or charger failure logs
4. Use **Auto-tune** to adjust MTBF based on actual failures

---

## Key Insights

### Availability vs. Reliability
- **Availability** = uptime percentage (MTBF / (MTBF + MTTR))
- **Reliability** = probability of survival to time t
- High availability doesn't mean high reliability if MTTR is very low

### MTBF is a Population Metric
- MTBF = 50,000 hours does NOT mean each pack lasts 50,000 hours
- It means across 100 packs operating 1,000 hours each (100,000 pack-hours), you'd expect ~2 failures
- Individual pack lifetimes vary widely around the mean

### Exponential vs. Weibull Trade-offs
- **Exponential:** Simpler, fewer parameters, conservative for mature tech
- **Weibull:** More realistic, captures age-dependent failures, requires shape parameter tuning

### Impact on Financials
- Lower MTBF → higher OpEx (repairs, replacements)
- Higher MTTR → more spares needed, higher inventory cost
- Wear-out patterns (β > 1) → plan for lumpy CapEx at predictable intervals

---

## Example Scenarios

### Scenario 1: New Charger Technology (Pilot)
```yaml
charger_failure:
  distribution: weibull
  weibull_shape: 0.7  # Infant mortality
  mtbf_hours: 15000
  mttr_hours: 36
```
**Interpretation:** Expect higher failures early, stabilizing over time. Budget for more repairs in Year 1.

---

### Scenario 2: Mature Fleet (Proven Tech)
```yaml
pack_failure:
  mtbf_hours: 60000
  mttr_hours: 4

charger_failure:
  distribution: exponential
  mtbf_hours: 25000
  mttr_hours: 24
```
**Interpretation:** Stable, predictable failure rates. Standard maintenance schedule.

---

### Scenario 3: Aging Infrastructure (Wear-out)
```yaml
charger_failure:
  distribution: weibull
  weibull_shape: 2.2  # Wear-out
  mtbf_hours: 18000
  mttr_hours: 30
```
**Interpretation:** Failure rate accelerates with age. Plan for proactive replacements at ~15,000 hours.

---

## Integration with Monte Carlo

When running Monte Carlo simulations (multiple stochastic runs):
- Each run samples failure events from these distributions
- Results show P10/P50/P90 percentiles for financial metrics
- Captures the **uncertainty** in failure timing, not just the mean

**Example:**
- MTBF = 20,000 hours (mean)
- In one run, first failure at 5,000 hours (unlucky)
- In another run, first failure at 40,000 hours (lucky)
- Monte Carlo aggregates these scenarios → realistic risk profile

---

## Further Reading

- **Reliability Engineering:** "Practical Reliability Engineering" by Patrick O'Connor
- **Weibull Analysis:** "The New Weibull Handbook" by Robert Abernethy
- **Battery Reliability:** IEC 62619, UL 1973 standards for battery system safety and reliability
