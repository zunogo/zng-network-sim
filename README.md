# Product Requirements Document (PRD)
## BSN Digital Twin & Financial Simulator

- **Project name**: Commercial 2W ZNG Battery Swap Network (BSN) Simulator  
- **Version**: 2.0  
- **Status**: Living document  
- **Primary goal**: A **bankable** digital twin + financial simulator for commercial battery swapping, capturing real-world stochastic behavior (demand volatility, degradation, equipment reliability, failures/sabotage) to produce investor- and lender-grade outputs **and** answer the charger-selection question and compute fully-loaded cost-per-cycle economics.

---

## Table of contents

- [1. Overview](#1-overview)
- [2. Stakeholders & users](#2-stakeholders--users)
- [3. Product scope](#3-product-scope)
- [4. Assumptions & definitions](#4-assumptions--definitions)
- [5. Inputs (data dictionary)](#5-inputs-data-dictionary)
  - [5.1 Vehicle configuration](#51-vehicle-configuration)
  - [5.2 Battery pack specification](#52-battery-pack-specification)
  - [5.3 Charger variants & reliability](#53-charger-variants--reliability)
  - [5.4 Station & infrastructure CapEx](#54-station--infrastructure-capex)
  - [5.5 Operating expenditure (OpEx)](#55-operating-expenditure-opex)
  - [5.6 Revenue & pricing](#56-revenue--pricing)
  - [5.7 Chaos & indirect variables](#57-chaos--indirect-variables)
- [6. Core simulation engine](#6-core-simulation-engine)
  - [6.1 Derived operational parameters](#61-derived-operational-parameters)
  - [6.2 Battery degradation model](#62-battery-degradation-model)
  - [6.3 Charger reliability & TCO model](#63-charger-reliability--tco-model)
  - [6.4 Fully-loaded cost per cycle](#64-fully-loaded-cost-per-cycle)
  - [6.5 Demand modeling & SLA](#65-demand-modeling--sla)
  - [6.6 Scale effects](#66-scale-effects)
- [7. Financial module ("CFO suite")](#7-financial-module-cfo-suite)
- [8. Decision-support outputs](#8-decision-support-outputs)
- [9. Field data integration ("ground-truthing")](#9-field-data-integration-ground-truthing)
- [10. KPIs & outputs](#10-kpis--outputs)
- [11. Non-functional requirements](#11-non-functional-requirements)
- [12. Software architecture](#12-software-architecture)
  - [12.1 Tech stack](#121-tech-stack)
  - [12.2 Design principles](#122-design-principles)
  - [12.3 Phase 1 scope boundary](#123-phase-1-scope-boundary)
  - [12.4 Module structure & data flow](#124-module-structure--data-flow)
  - [12.5 Key types (Pydantic models)](#125-key-types-pydantic-models)
  - [12.6 UI specification (Phase 1)](#126-ui-specification-phase-1)
  - [12.7 Project layout](#127-project-layout-phase-1--what-actually-gets-built)
- [13. Phased roadmap & acceptance criteria](#13-phased-roadmap--acceptance-criteria)

---

## 1. Overview

### Problem
Planning a battery swapping network today relies on spreadsheets with deterministic inputs. Two critical gaps exist:

1. **Charger selection**: A low-MTBF charger is cheap to buy but expensive to own (downtime, repairs, lost revenue). The break-even is non-obvious and changes under discounting.
2. **True cost per cycle**: Nobody knows the *real*, all-in cost of one charge-discharge cycle once you amortize battery degradation, charger wear, electricity, real estate, insurance, sabotage, and logistics. Without this number, pricing is guesswork.

### Vision
Build a software "digital twin" that:
- simulates network operations and asset health over time for a given vehicle + pack configuration,
- evaluates competing charger options head-to-head (MTBF economics in NPV terms), and
- produces finance outputs investors and banks can underwrite (unit economics, burn vs earn, DCF/NPV/IRR, DSCR, SLB leaseability).

### Primary outcomes
- **Fully-loaded cost per cycle**: the single most important unit-economic number, decomposed into a waterfall of cost drivers.
- **Charger selection**: quantified comparison of charger variants by lifetime TCO in NPV terms.
- **Pilot sizing**: minimum viable scale to reach positive operating cash flow under uncertainty.
- **Bankability**: DSCR, cashflow stability, asset residual value.

---

## 2. Stakeholders & users

- **Founder/CEO**: validate unit economics; determine funding required (Seed/Series A).
- **Operations manager**: optimize battery-to-vehicle ratio; select chargers; manage SLA; plan docks/stations.
- **Investors (VC/PE)**: evaluate IRR/NPV and "burn vs earn" scenarios.
- **Infrastructure funds / banks**: evaluate DSCR and SLB feasibility for asset-heavy financing.

---

## 3. Product scope

### In scope (MVP → v1)
- Configurable inputs for vehicle configuration, pack specification, charger variants, CapEx, OpEx, demand, degradation, and chaos variables.
- **Charger TCO comparison**: evaluate charger options by MTBF, lifetime cost, and NPV impact.
- **Fully-loaded cost-per-cycle engine**: waterfall decomposition of every cost driver per cycle.
- Time-based simulation (monthly reporting; internal daily/hourly resolution as needed).
- Station-level and network-level service modeling (failure to serve, wait times).
- Financial statements and valuation metrics (cash flow, DCF, IRR/NPV, DSCR).
- Scenario analysis (base / pessimistic / optimistic; parameter sweeps).

### Explicitly out of scope (for now)
- Real-time station control systems (SMS) and driver app development (only cost modeled).
- Live dispatch/operations tooling (fleet routing, staffing schedules).

---

## 4. Assumptions & definitions

- **Battery pack**: swappable energy asset with state-of-health (SOH) that degrades over time and cycles.
- **Dock / charger slot**: individual charging channel at a station; charging efficiency can decay; subject to failure per its MTBF curve.
- **Failure to serve**: a driver arrives and **no charged battery** is available within SLA constraints.
- **Range anxiety buffer**: drivers swap at SoC threshold (e.g., 20–30%) rather than 0%.
- **MTBF**: mean time between failures — expected operating hours before a charger module fails.
- **MTTR**: mean time to repair — hours of downtime per failure event (includes logistics of getting a spare).
- **C-rate**: charging current relative to pack capacity. A 1.28 kWh pack charged by a 1 kW charger → C-rate ≈ 0.78C → ~77 min to full. At 2C → ~30 min. Determines dock throughput.
- **Cost per cycle**: the fully-loaded cost of one battery charge-discharge cycle, inclusive of *all* cost categories amortized to the cycle level.
- **Vehicle configuration**: the chosen combination of vehicle class + number of packs + pack capacity that is fixed as an input to each simulation run.
- **Time step**: simulation supports at least daily demand modeling, rolled up to monthly financial reporting.

---

## 5. Inputs (data dictionary)

### 5.1 Vehicle configuration

The user selects **one vehicle configuration** as input to each simulation run. This defines how demand translates into swap events, dock occupancy, and pack inventory requirements.

| Parameter | Description | Example values |
|---|---|---|
| Vehicle name | Human label | "Light 2W", "Heavy 2W", "Cargo 2W" |
| Packs per vehicle | Number of swappable packs carried | 1 or 2 |
| Pack capacity (kWh) | Capacity of each pack in this config | 1.28, 1.5, 2.0, 2.56 |
| Total energy per vehicle (kWh) | `packs_per_vehicle × pack_capacity` (derived) | 1.28, 2.56 |
| Usable energy (kWh) | Accounting for range-anxiety buffer and min SoC | 0.90 – 1.02 (for 1.28 kWh at 70–80% usable) |
| Avg daily km | Expected daily distance traveled | 80–150 km |
| Energy consumption (Wh/km) | Vehicle efficiency | 25–40 Wh/km |
| Swaps per vehicle per day | Derived: `(daily_km × Wh_per_km) / usable_energy` | 1.5–4.0 |
| Revenue model | Per-swap fee, per-km fee, or subscription | ₹X per swap, ₹Y/km |
| Swap time (minutes) | Time for one pack swap (affects throughput) | 1–3 min per pack |

> **Tip — comparing vehicle configs**: To evaluate different vehicle architectures (e.g., 1 × 1.28 kWh vs 2 × 1.28 kWh vs 1 × 2.56 kWh), run separate simulations with each configuration and compare the resulting cost-per-cycle, cash flows, and break-even outputs side by side. The simulator does not automate this comparison — the vehicle + pack choice is a fixed input per run.

### 5.2 Battery pack specification

The user selects **one pack variant** as input to each simulation run. This determines degradation behavior, replacement timing, and the battery's contribution to cost per cycle.

| Parameter | Description | Example values |
|---|---|---|
| Variant name | Label | "1.28 kWh NMC", "2.56 kWh LFP" |
| Nominal capacity (kWh) | Nameplate energy | 1.28, 2.0, 2.56 |
| Chemistry | Cell chemistry (affects cycle life, calendar life, thermal) | NMC, LFP |
| Unit cost (₹) | Purchase price per pack (incl. BMS, casing) | ₹15,000 – ₹45,000 |
| Cycle life (to 80% SOH) | Rated cycles before reaching retirement threshold | 800–3,000 |
| Cycle degradation rate (β) | SOH loss per cycle | 0.025%–0.10% |
| Calendar aging rate | SOH loss per month when idle | 0.1%–0.3%/month |
| Depth of discharge (DoD) | Typical DoD per cycle (affects cycle life) | 70–90% |
| Retirement SOH threshold | SOH at which pack exits swap network | 70–80% |
| Second-life salvage value (₹) | Resale value at retirement SOH (stationary storage) | ₹2,000 – ₹10,000 |
| Weight (kg) | Affects handling, swap mechanism design | 5–12 kg |
| Aggressiveness multiplier sensitivity | How much faster this chemistry degrades under aggressive use | 1.0–2.0× |

### 5.3 Charger variants & reliability

**This is a first-class input category.** The simulator must support defining **multiple charger options** and comparing their total cost of ownership (TCO). The vehicle and pack are fixed; charger selection is the design decision the tool helps you make.

| Parameter | Description | Example values |
|---|---|---|
| Charger name | Label | "Budget-1kW", "Premium-1kW", "Fast-3kW" |
| Purchase cost per slot (₹) | Unit CapEx | ₹8,000 – ₹35,000 |
| Rated power (W) | Charging power per slot | 500 W, 1 kW, 3 kW |
| Effective C-rate | Derived: `rated_power / pack_capacity` — determines charge time | 0.4C – 2.3C |
| Charge time (minutes) | Derived: `pack_capacity / (rated_power × efficiency) × 60` | 26 – 154 min |
| Charging efficiency (%) | Wall-to-pack efficiency at start of life | 88–95% |
| Efficiency decay rate (%/year) | Annual efficiency loss from thermal stress | 0.3–1.0% |
| MTBF (hours) | Mean operating hours between failures | 5,000 – 50,000 hrs |
| MTTR (hours) | Mean hours to restore a failed slot (incl. spare logistics) | 4 – 72 hrs |
| Repair cost per event (₹) | Parts + labor per failure | ₹500 – ₹5,000 |
| Replacement threshold | Number of repairs before full unit replacement | 2–5 repairs |
| Full replacement cost (₹) | Cost of swapping in a new unit (may differ from purchase) | ₹7,000 – ₹30,000 |
| Spare inventory cost (₹/unit) | Capital tied up in spares per N deployed slots | ₹5,000 – ₹25,000 |
| Expected useful life (years) | Calendar life even without failure | 5–10 years |

**Key insight — the MTBF economics**:
A "Budget-1kW" charger at ₹8,000 with MTBF of 8,000 hours may look cheap. But if a station slot runs ~18 hrs/day:
- Failure every ~15 months
- Each failure: MTTR downtime (lost revenue) + repair cost + eventually replacement
- Over 5 years: 3–4 failures, potential 1–2 full replacements

A "Premium-1kW" charger at ₹25,000 with MTBF of 40,000 hours:
- Failure every ~6 years → likely zero failures in a 5-year horizon
- Minimal repair/replacement costs
- Higher uptime → more swaps served → more revenue

The simulator must compute the **NPV of each charger option** over the project horizon, including:
\[
TCO_{charger} = CapEx + PV(\text{repairs}) + PV(\text{replacements}) + PV(\text{lost revenue from downtime}) - PV(\text{salvage})
\]

### 5.4 Station & infrastructure CapEx

| Category | Item | Description |
|---|---|---|
| Energy assets | Station cabinet | Physical housing, cooling fans, HMI. |
| Infrastructure | One-time site prep | Civil works, earthing, concrete pads, mounting. |
| Infrastructure | Grid connection | Transformer upgrades, cabling, utility security deposits. |
| Soft assets | Software development | Custom SMS and driver app (cost line item). |
| Real estate | Security deposit | Initial deposits for station locations. |

> **Note**: Battery pack cost and charger dock cost are defined in sections 5.2 and 5.3 respectively, as variant-level inputs rather than single line items.

### 5.5 Operating expenditure (OpEx)

- **Electricity**:
  - base tariff (₹/kWh) + peak / off-peak schedule
  - demand charges (₹/kVA, fixed monthly)
  - the simulator must compute electricity cost *per cycle* (see §6.4)
- **Auxiliary power**: cooling systems + standby electronics consumption.
- **Real estate**: monthly rent/lease (with zone-dependent escalations).
- **Maintenance**:
  - preventative: scheduled cleaning / inspection (station-level, monthly)
  - corrective: driven by charger MTBF model (see §6.3) + other wear items (fans, plugs, screens)
- **Insurance**: base premium + risk multiplier (sabotage escalation factor).
- **Logistics / rebalancing**: cost of moving packs between stations to balance inventory.
  - *This cost is affected by packs-per-vehicle*: dual-pack configs move twice as many packs per swap.
- **Pack handling labor**: if swaps are manual — labor cost per swap event.

### 5.6 Revenue & pricing

| Parameter | Description |
|---|---|
| Pricing model | Per-swap, per-kWh delivered, per-km, or monthly subscription |
| Base price per swap (₹) | Gross price charged to driver |
| Price differentiation | Peak / off-peak pricing, loyalty discounts |
| Vehicles on network | Total fleet size (ramps over time) |
| Fleet growth curve | Monthly additions of vehicles (step or linear) |

### 5.7 Chaos & indirect variables

- **Sabotage percentage**: monthly rate of theft / vandalism / orphaned packs.
- **Aggressiveness index**: multiplier on driver behavior → faster battery degradation.
- **Range anxiety buffer**: SoC threshold (%) at which drivers swap (20–30%).
- **Thermal throttling**: charging power de-rating at high ambient temperatures (reduces throughput).
- **Charger infant mortality**: elevated early-life failure rate for cheap chargers (bath-tub curve).

---

## 6. Core simulation engine

### 6.1 Derived operational parameters

Given the chosen vehicle configuration (§5.1) and pack specification (§5.2), the engine first computes the **operational parameters** that drive the rest of the simulation:

| Derived metric | How it's computed |
|---|---|
| Swaps/day/vehicle | `(avg_daily_km × Wh_per_km) / usable_energy_per_pack` |
| Swaps/day (network) | `swaps_per_day_per_vehicle × fleet_size` |
| Dock-minutes per swap visit | `packs_per_vehicle × swap_time_per_pack` |
| Charge time per pack | `pack_capacity / (charger_rated_power × charger_efficiency) × 60` min |
| Effective C-rate | `charger_rated_power / pack_capacity` |
| Cycles/day/dock | `(operating_hours × 60) / charge_time_minutes` — throughput ceiling per slot |
| Dock slots required | From queuing model (§6.5), constrained by throughput |
| Pack inventory required | `(packs_per_vehicle × fleet_size) + charging_buffer + rebalancing_float` |
| Revenue per swap visit | `price × packs_per_vehicle` (or per-kWh pricing × energy) |

These derived values feed into the degradation model (§6.2), charger TCO model (§6.3), cost-per-cycle waterfall (§6.4), and demand/SLA model (§6.5).

### 6.2 Battery degradation model

The simulator must model chemical + mechanical decay for the selected pack variant:

- **Cycle aging**:
  \[
  SOH_{new} = SOH_{old} - (\beta \times \Delta Cycles)
  \]
  where \(\beta\) is variant-specific and modulated by aggressiveness index and DoD.

- **Calendar aging**: time-based decay even when idle (chemistry-dependent).

- **Temperature effects**: elevated degradation at high ambient temps (parametric multiplier).

- **Depth of discharge impact**: deeper cycles = faster aging (configurable curve per chemistry — LFP is more tolerant than NMC).

**Outputs (minimum)**:
- per-pack (or per-cohort) SOH trajectory over time
- expected cycle count at retirement SOH
- cohort retirement schedule → triggers replacement CapEx and second-life salvage
- **cost of degradation per cycle** (see §6.4) — this is the battery's contribution to cost per cycle

### 6.3 Charger reliability & TCO model

**Purpose**: answer "Which charger is cheapest to own over the project life in NPV terms?"

For each charger variant the engine must simulate:

1. **Failure events**: generated stochastically from MTBF (exponential or Weibull distribution; Weibull to model infant mortality / wear-out).
2. **Downtime per failure**: sampled from MTTR distribution → slot is unavailable.
3. **Repair vs replace decision**: after N repairs, unit is fully replaced.
4. **Revenue impact of downtime**: `downtime_hours × swaps_per_hour_per_slot × revenue_per_swap` = lost revenue.
5. **Spare inventory carrying cost**: capital tied up in reserve units.

**Charger TCO (per slot, over horizon T)**:
\[
TCO = C_{purchase} + \sum_{i=1}^{F} \frac{C_{repair,i}}{(1+r)^{t_i}} + \sum_{j=1}^{R} \frac{C_{replace,j}}{(1+r)^{t_j}} + \sum_{k=1}^{T} \frac{C_{lost\_revenue,k}}{(1+r)^{k}} + C_{spare\_inventory} - \frac{C_{salvage}}{(1+r)^{T}}
\]

where \(F\) = number of failure events, \(R\) = number of full replacements, \(r\) = discount rate, \(t_i\) = time of event.

**Outputs (minimum)**:
- per-charger-variant: NPV of TCO, undiscounted TCO, TCO per cycle served
- comparison table ranking chargers by NPV
- sensitivity: how does the ranking change if MTBF is 20% better/worse than spec?
- uptime %: expected availability per charger variant

### 6.4 Fully-loaded cost per cycle

**This is the single most important KPI.** It answers: *"What does it really cost us every time a battery goes through one charge-discharge cycle?"*

The cost per cycle is a **waterfall** — every cost category in the business amortized to the cycle level:

\[
CPC_{total} = CPC_{battery} + CPC_{charger} + CPC_{electricity} + CPC_{realestate} + CPC_{maintenance} + CPC_{insurance} + CPC_{sabotage} + CPC_{logistics} + CPC_{overhead}
\]

| Component | Formula | Notes |
|---|---|---|
| \(CPC_{battery}\) | \(\frac{Pack\ Cost - Second\text{-}Life\ Salvage}{Lifetime\ Cycles\ to\ Retirement}\) | Discounted: use PV of salvage and spread CapEx. Chemistry & DoD dependent. |
| \(CPC_{charger}\) | \(\frac{Charger\ TCO\ (§6.3)}{Total\ Cycles\ Served\ over\ Life}\) | Includes purchase, repairs, replacements, downtime, spares. |
| \(CPC_{electricity}\) | \(\frac{Pack\ Capacity\ (kWh)}{Charging\ Efficiency} \times Blended\ Tariff\) | Must use efficiency that degrades over time. Peak/off-peak blend. |
| \(CPC_{realestate}\) | \(\frac{Monthly\ Rent}{Cycles\ Served\ per\ Month\ at\ Station}\) | Allocated per cycle based on station throughput. |
| \(CPC_{maintenance}\) | \(\frac{Monthly\ Preventive + Corrective}{Cycles\ per\ Month}\) | Corrective partially captured in charger TCO; remainder here. |
| \(CPC_{insurance}\) | \(\frac{Monthly\ Premium}{Cycles\ per\ Month}\) | Including sabotage escalation. |
| \(CPC_{sabotage}\) | \(\frac{Expected\ Monthly\ Loss\ (packs × sabotage\%)}{Cycles\ per\ Month}\) | Expected value of asset loss. |
| \(CPC_{logistics}\) | \(\frac{Rebalancing\ Cost\ per\ Month}{Cycles\ per\ Month}\) | Higher for dual-pack configs (2× pack movements). |
| \(CPC_{overhead}\) | \(\frac{Software + Admin + Other}{Cycles\ per\ Month}\) | Fixed overhead spread across volume. |

**Critical**: the simulator must produce this waterfall **for each charger variant** so the user can see exactly where money goes and which charger minimizes the total.

**Discounted cost per cycle**: in addition to the nominal CPC, compute the present-value-equivalent CPC by discounting all future cost streams at the WACC and dividing by discounted cycle volume. This makes charger MTBF economics and battery replacement timing visible in DCF terms.

### 6.5 Demand modeling & SLA

- **Demand distribution**: configurable daily swaps driven by a stochastic model (Poisson or Gamma) capturing 24-hour cycles (can be simplified initially but must be parameterized).
- **SLA compliance tracking**:
  - log "failure to serve" events (considering dock downtime from charger failures)
  - compute SLA breach rate over time
- **Queuing / wait time**:
  - model station congestion using M/M/c-style approximation (or simulation)
  - determine minimum docks required to keep wait times below target
  - account for packs-per-vehicle: a dual-pack swap visit occupies a dock for 2× the single-pack time (or 2 docks simultaneously)

### 6.6 Scale effects

- **Procurement step-down**: CapEx discounts at scale milestones (e.g., 100 / 500 / 1,000 units) — applies to both packs and chargers.
- **Maintenance density**: OpEx per station reduces as network density increases (reduced travel distance, better technician utilization, shared spare inventory).
- **Pack inventory efficiency**: at scale, a smaller ratio of float inventory to fleet is needed (law of large numbers smooths demand variance).

---

## 7. Financial module ("CFO suite")

### 7.1 Financial statements (monthly)

- **Cash flow statement**: inflows (swap revenue) vs outflows (OpEx + CapEx).
- **Funds flow statement**: sources (equity/debt) vs applications (asset purchases/burn).
- **DCF analysis**: NPV and IRR with user-defined WACC / discount rate.
- **Marginal costing**: contribution margin for the \(N+1\) vehicle (and/or station).

### 7.2 Funding & SLB (sale-and-leaseback)

- **Pilot sizing logic**: search for minimum scale that reaches positive operating cash flow under specified confidence (e.g., median / p90).
- **DSCR**:
  \[
  DSCR = \frac{Net\ Operating\ Income}{Total\ Debt\ Service}
  \]
- **Asset residual value**:
  - estimate second-life value of batteries (using pack variant salvage values from §5.2)
  - incorporate into terminal value or asset sale proceeds

### 7.3 Charger decision economics

This sub-module produces the **comparative financial view** across charger variants (vehicle + pack are fixed inputs):

| Output | Description |
|---|---|
| Charger NPV comparison | NPV of network using each charger variant (holding vehicle/pack/demand constant) |
| Cost-per-cycle waterfall (per charger) | Full breakdown showing where each ₹ goes for each charger option |
| Sensitivity matrix | How does NPV/CPC change as MTBF varies ±20%? As pack price changes ±15%? |
| Break-even: budget vs premium charger | Month at which the premium charger's lower lifetime cost overtakes its higher CapEx |
| Discounted CPC trajectory | How CPC (in PV terms) evolves month-by-month as degradation, failures, and scale effects compound |

---

## 8. Decision-support outputs

Beyond financial statements, the simulator must produce **actionable decision artifacts**:

### 8.1 Charger selection recommendation
- Rank charger variants by: NPV of TCO, CPC contribution, uptime %.
- Highlight: "Premium charger has 3× CapEx but saves ₹Y over 5 years in NPV terms. Break-even vs Budget charger at month Z."

### 8.2 What-if scenario reports
- Run user-defined parameter sweeps (e.g., "What if MTBF is 50% of spec?" or "What if pack cost drops 20% at month 18?").
- Present results as tornado charts / sensitivity tables.

---

## 9. Field data integration ("ground-truthing")

### 9.1 Ingestion
- Upload CSVs and/or integrate APIs from BMS systems (format to be defined).
- Charger failure logs (timestamp, slot ID, failure type, repair duration).

### 9.2 Variance analysis
- Compare projected degradation vs actual field degradation.
- Compare projected charger MTBF vs actual field MTBF.
- Highlight drift by battery cohort, charger batch, geography, temperature bands, and usage intensity.

### 9.3 Parameter auto-tuning
- Update model parameters (e.g., \(\beta\), MTBF, throttling curves, sabotage rates) based on historical performance.
- Flag when field data materially changes a charger recommendation (e.g., "Field MTBF of Budget charger is 40% below spec — Premium charger is now NPV-positive to switch to").

---

## 10. KPIs & outputs

### Primary KPIs

| KPI | Formula / definition |
|---|---|
| **Fully-loaded cost per cycle** | See §6.4 waterfall. The headline number. |
| **Cost per swap visit** | CPC × packs_per_vehicle (accounts for dual-pack visits) |
| **Cost per kWh delivered** | CPC / pack_capacity_kWh |
| **Gross margin per swap** | Revenue per swap − cost per swap |
| **Contribution margin per vehicle-month** | (Swaps/month × gross margin) − allocated fixed costs |
| **Utilization rate** | % of time a dock is serving a swap or charging a pack (vs idle or down) |
| **Dock uptime %** | 1 − (downtime hours / total hours); driven by charger MTBF |
| **Asset turn** | Revenue per ₹1 of CapEx invested |
| **Break-even point** | In vehicles and months of operation |
| **SLA metrics** | Failure-to-serve rate, mean wait time, p95 wait time |
| **DSCR** | Net operating income / total debt service |
| **Battery fleet SOH distribution** | Histogram of pack health across the network at any point in time |

### Output artifacts

- Monthly network dashboard dataset (CSV/JSON)
- **Charger comparison report** (variant X vs Y vs Z)
- **Cost-per-cycle waterfall chart data** (per charger variant)
- Scenario comparison report (base vs variants)
- Investor/bank view: cashflows, IRR/NPV, DSCR, sensitivities
- Sensitivity / tornado chart data

---

## 11. Non-functional requirements

- **Reproducibility**: simulations must be repeatable via random seed control.
- **Explainability**: every KPI should trace back to underlying drivers (demand, SOH, charger uptime, tariffs).
- **Performance**: must support multi-year simulations (e.g., 36–120 months) with reasonable runtime for scenario sweeps across charger variants.
- **Auditability**: persist inputs, versions, and outputs per run so results are defensible.
- **Composability**: charger and pack definitions should be modular — easy to add new options without restructuring the model.

---

## 12. Software architecture

### 12.1 Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Ecosystem, speed of iteration, Pydantic, Streamlit |
| Input validation | Pydantic v2 | Typed configs with defaults, serialization to/from YAML |
| UI | Streamlit | Rapid prototyping; no frontend build step; widgets map directly to Pydantic fields |
| Testing | pytest | Standard; property-based tests via hypothesis later |
| Packaging | `pyproject.toml` + `hatch` (or `pip install -e .`) | Single dependency file, editable installs |

Phase 1 has **zero** heavy dependencies — no numpy, scipy, pandas. Pure Python + Pydantic + Streamlit. Heavy libraries are added only when Phase 2 needs them.

### 12.2 Design principles

1. **"Show the math"** — every computed number in the UI is displayed alongside the formula and the substituted input values. No black boxes. This is the single most important UI principle.
2. **Contracts first, extend never rewrite** — all Pydantic input models and result types are defined in Phase 1 with their full schema. Later phases populate more fields but never change the shape.
3. **Engine is a pure function** — `Scenario` in → `SimulationResult` out. No side effects, no state. Dashboard is a thin shell.
4. **One run = one charger** — the engine runs once per charger variant. Charger comparison is achieved by collecting results and displaying them side by side.

### 12.3 Phase 1 scope boundary

**What Phase 1 computes (deterministic)**:
- Derived operational parameters from vehicle + pack + charger inputs
- Battery cost per cycle: `(pack_cost − salvage) / lifetime_cycles` — simple linear amortization, no dynamic SOH trajectory
- Charger cost per cycle: deterministic expected-value calculation from MTBF (expected failures/year = `operating_hours / MTBF`, not stochastic simulation)
- Electricity, real estate, maintenance, insurance, sabotage, logistics, overhead per cycle — all from monthly inputs ÷ monthly cycles
- Monthly cash flow: revenue − OpEx − CapEx for each month over the horizon
- Charger comparison: side-by-side CPC waterfall and cash flow across variants

**What Phase 1 does NOT compute** (deferred to Phase 2+):
- Stochastic demand (Phase 1 uses flat daily demand × fleet ramp)
- Dynamic SOH trajectory / cohort-based degradation curves
- Stochastic charger failure events (Phase 1 uses expected-value MTBF math)
- SLA / queuing / failure-to-serve modeling
- DCF / NPV / IRR / DSCR (Phase 3)
- Scale effects (procurement step-down, maintenance density)
- Charts or graphs of any kind

### 12.4 Module structure & data flow

```
┌──────────────┐       ┌──────────────┐       ┌──────────────────┐
│   Scenario    │──────▶│    Engine     │──────▶│ SimulationResult  │
│   (config/)   │       │  (engine/)   │       │   (models/)       │
│               │       │              │       │                   │
│ vehicle       │       │ For each     │       │ One result per    │
│ pack          │       │ charger in   │       │ charger variant   │
│ charger[]     │       │ scenario:    │       │                   │
│ station       │       │  → derive    │       │ monthly snapshots │
│ opex          │       │  → CPC       │       │ + summary KPIs    │
│ revenue       │       │  → cashflow  │       │                   │
│ chaos         │       │              │       │                   │
│ simulation    │       │              │       │                   │
└──────────────┘       └──────────────┘       └──────────────────┘
                                                       │
                                                       ▼
                                              ┌──────────────────┐
                                              │    Dashboard      │
                                              │  (dashboard/)     │
                                              │                   │
                                              │  Renders inputs,  │
                                              │  derived params,  │
                                              │  CPC waterfall,   │
                                              │  cash flow table, │
                                              │  charger compare  │
                                              │                   │
                                              │  ALL with formulas│
                                              └──────────────────┘
```

**Module dependency rules:**
```
config/     ← depends on nothing (pure Pydantic models)
models/     ← depends on nothing (pure Pydantic models)
engine/     ← depends on config/, models/
dashboard/  ← depends on config/, engine/, models/ (thin orchestration)
```

> **Note**: `finance/` and `compare/` modules from the full roadmap are not built in Phase 1. Their logic (basic cash flow, charger side-by-side) lives directly in `engine/static.py` and `dashboard/app.py` for now. They get extracted into separate modules when Phase 3 adds DCF/DSCR complexity.

### 12.5 Key types (Pydantic models)

**Input models (`config/`):**

```python
class VehicleConfig(BaseModel):
    name: str                        # "Heavy 2W"
    packs_per_vehicle: int           # 1 or 2
    pack_capacity_kwh: float         # 1.28
    avg_daily_km: float              # 100
    energy_consumption_wh_per_km: float  # 30
    swap_time_minutes: float         # 2.0
    range_anxiety_buffer_pct: float  # 0.20  (20% — usable = capacity × (1 - buffer))

class PackSpec(BaseModel):
    name: str                        # "1.28 kWh NMC"
    nominal_capacity_kwh: float      # 1.28
    chemistry: str                   # "NMC" | "LFP"
    unit_cost: float                 # ₹15,000
    cycle_life_to_retirement: int    # 1,200 cycles (to retirement SOH)
    cycle_degradation_rate_pct: float  # 0.05 (β — SOH loss per cycle, %)
    calendar_aging_rate_pct_per_month: float  # 0.15
    depth_of_discharge_pct: float    # 0.80
    retirement_soh_pct: float        # 0.70
    second_life_salvage_value: float # ₹3,000
    weight_kg: float                 # 6.5
    aggressiveness_multiplier: float # 1.0 (1.0 = normal, 1.5 = aggressive)

class ChargerVariant(BaseModel):
    name: str                        # "Budget-1kW"
    purchase_cost_per_slot: float    # ₹8,000
    rated_power_w: float             # 1,000
    charging_efficiency_pct: float   # 0.90
    efficiency_decay_pct_per_year: float  # 0.005
    mtbf_hours: float                # 8,000
    mttr_hours: float                # 24
    repair_cost_per_event: float     # ₹1,500
    replacement_threshold: int       # 3 (replace after N repairs)
    full_replacement_cost: float     # ₹7,500
    spare_inventory_cost: float      # ₹8,000
    expected_useful_life_years: float  # 7

class StationConfig(BaseModel):
    cabinet_cost: float              # ₹50,000
    site_prep_cost: float            # ₹30,000
    grid_connection_cost: float      # ₹25,000
    software_cost: float             # ₹100,000 (one-time)
    security_deposit: float          # ₹20,000
    num_stations: int                # 5
    docks_per_station: int           # 8
    operating_hours_per_day: float   # 18

class OpExConfig(BaseModel):
    electricity_tariff_per_kwh: float   # ₹8.0
    auxiliary_power_per_month: float    # ₹2,000 per station
    rent_per_month_per_station: float   # ₹15,000
    preventive_maintenance_per_month_per_station: float  # ₹3,000
    corrective_maintenance_per_month_per_station: float  # ₹1,000
    insurance_per_month_per_station: float  # ₹2,000
    logistics_per_month_per_station: float  # ₹5,000
    pack_handling_labor_per_swap: float  # ₹2.0
    overhead_per_month: float           # ₹50,000 (network-wide)

class RevenueConfig(BaseModel):
    price_per_swap: float            # ₹40
    initial_fleet_size: int          # 200
    monthly_fleet_additions: int     # 50

class ChaosConfig(BaseModel):
    sabotage_pct_per_month: float    # 0.005 (0.5% of packs lost/month)
    aggressiveness_index: float      # 1.0
    thermal_throttling_factor: float # 1.0 (1.0 = no throttling)

class SimulationConfig(BaseModel):
    horizon_months: int              # 60
    discount_rate_annual: float      # 0.12 (for future phases)

class Scenario(BaseModel):
    vehicle: VehicleConfig
    pack: PackSpec
    charger_variants: list[ChargerVariant]
    station: StationConfig
    opex: OpExConfig
    revenue: RevenueConfig
    chaos: ChaosConfig
    simulation: SimulationConfig
```

**Result models (`models/`):**

```python
class DerivedParams(BaseModel):
    """Computed once from vehicle + pack + charger inputs."""
    usable_energy_kwh: float         # pack_capacity × (1 - range_anxiety_buffer)
    swaps_per_vehicle_per_day: float # (daily_km × Wh_per_km) / usable_energy
    total_energy_per_vehicle_kwh: float  # packs_per_vehicle × pack_capacity
    charge_time_minutes: float       # pack_capacity / (rated_power × efficiency) × 60
    effective_c_rate: float          # rated_power / pack_capacity
    cycles_per_day_per_dock: float   # (operating_hours × 60) / charge_time
    pack_lifetime_cycles: int        # (1.0 - retirement_soh) / β  (adjusted for DoD, aggressiveness)

class CostPerCycleWaterfall(BaseModel):
    """The 9-component CPC breakdown — each field is ₹/cycle."""
    battery: float
    charger: float
    electricity: float
    real_estate: float
    maintenance: float
    insurance: float
    sabotage: float
    logistics: float
    overhead: float
    total: float                     # sum of above

class MonthlySnapshot(BaseModel):
    month: int
    fleet_size: int
    total_swaps: int
    total_cycles: int
    revenue: float
    opex_total: float
    capex_this_month: float          # pack replacements, charger replacements
    net_cash_flow: float
    cumulative_cash_flow: float
    cost_per_cycle: CostPerCycleWaterfall

class RunSummary(BaseModel):
    charger_variant_name: str
    total_revenue: float
    total_opex: float
    total_capex: float
    total_net_cash_flow: float
    avg_cost_per_cycle: float
    break_even_month: int | None     # None if never breaks even

class SimulationResult(BaseModel):
    scenario_id: str
    charger_variant_id: str
    engine_type: str                 # "static" for Phase 1
    months: list[MonthlySnapshot]
    summary: RunSummary
    derived: DerivedParams
    cpc_waterfall: CostPerCycleWaterfall  # steady-state waterfall
```

### 12.6 UI specification (Phase 1)

#### 12.6.1 Core principle: "Show the math"

Every computed value in the UI is displayed as a **three-part block**:

```
┌─────────────────────────────────────────────────────┐
│  Swaps per vehicle per day                    3.33  │
│  ─────────────────────────────────────────────────  │
│  Formula: (daily_km × Wh_per_km) / usable_energy   │
│  = (100 km × 30 Wh/km) / (1,280 Wh × 0.80)        │
│  = 3,000 / 1,024 = 2.93                            │
└─────────────────────────────────────────────────────┘
```

1. **Label + result** — the metric name and its value, prominent.
2. **Formula** — the symbolic formula.
3. **Substitution** — the actual input values plugged in, showing the arithmetic.

No number appears without its derivation. This is what makes the tool trustworthy for investor decks and board discussions.

#### 12.6.2 Layout: sidebar inputs → main area outputs

```
┌──────────────────┬──────────────────────────────────────────────────┐
│                  │                                                  │
│    SIDEBAR       │              MAIN AREA                           │
│    (inputs)      │              (outputs)                           │
│                  │                                                  │
│  ┌────────────┐  │  ┌────────────────────────────────────────────┐  │
│  │ Vehicle    │  │  │  Section 1: Derived Operational Parameters │  │
│  │ Config     │  │  │  (table with formulas)                    │  │
│  └────────────┘  │  └────────────────────────────────────────────┘  │
│  ┌────────────┐  │                                                  │
│  │ Pack       │  │  ┌────────────────────────────────────────────┐  │
│  │ Spec       │  │  │  Section 2: Cost Per Cycle Waterfall       │  │
│  └────────────┘  │  │  (one table per charger variant)           │  │
│  ┌────────────┐  │  └────────────────────────────────────────────┘  │
│  │ Charger    │  │                                                  │
│  │ Variant 1  │  │  ┌────────────────────────────────────────────┐  │
│  │ Variant 2  │  │  │  Section 3: Monthly Cash Flow              │  │
│  │ + Add      │  │  │  (one table per charger variant)           │  │
│  └────────────┘  │  └────────────────────────────────────────────┘  │
│  ┌────────────┐  │                                                  │
│  │ Station    │  │  ┌────────────────────────────────────────────┐  │
│  │ CapEx      │  │  │  Section 4: Charger Comparison Summary     │  │
│  └────────────┘  │  │  (single table ranking all variants)       │  │
│  ┌────────────┐  │  └────────────────────────────────────────────┘  │
│  │ OpEx       │  │                                                  │
│  └────────────┘  │                                                  │
│  ┌────────────┐  │                                                  │
│  │ Revenue    │  │                                                  │
│  └────────────┘  │                                                  │
│  ┌────────────┐  │                                                  │
│  │ Chaos      │  │                                                  │
│  └────────────┘  │                                                  │
│  ┌────────────┐  │                                                  │
│  │ Simulation │  │                                                  │
│  │ Settings   │  │                                                  │
│  └────────────┘  │                                                  │
│                  │                                                  │
│  [▶ Run]         │                                                  │
│                  │                                                  │
└──────────────────┴──────────────────────────────────────────────────┘
```

Inputs are entered in the sidebar via Streamlit expanders (one per category). Each input field has a sensible default from the Pydantic model. Outputs render instantly on the main area when "Run" is clicked. No page reloads — Streamlit re-renders in place.

#### 12.6.3 Section 1 — Derived operational parameters

A single table showing how vehicle + pack + charger inputs combine into the numbers that drive everything else:

| Metric | Formula | Calculation | Value |
|---|---|---|---|
| Usable energy per pack | `capacity × (1 − buffer)` | `1.28 kWh × (1 − 0.20)` | 1.024 kWh |
| Total energy per vehicle | `packs × capacity` | `2 × 1.28 kWh` | 2.56 kWh |
| Daily energy need | `daily_km × Wh_per_km` | `100 km × 30 Wh/km` | 3,000 Wh |
| Swaps/day/vehicle | `energy_need / usable_energy` | `3,000 / 1,024` | 2.93 |
| Charge time (per pack) | `capacity / (power × eff) × 60` | `1.28 / (1.0 × 0.90) × 60` | 85.3 min |
| Effective C-rate | `power / capacity` | `1.0 / 1.28` | 0.78 C |
| Cycles/day/dock | `(op_hours × 60) / charge_time` | `(18 × 60) / 85.3` | 12.7 |
| Pack lifetime cycles | `(1.0 − retirement_soh) / β` | `(1.0 − 0.70) / 0.0005` | 600 |

This table updates whenever inputs change. The "Formula" column is always visible — never hidden.

#### 12.6.4 Section 2 — Cost per cycle waterfall

One table **per charger variant**, each showing the 9-component CPC breakdown:

**▸ Charger: "Budget-1kW" (₹8,000, MTBF 8,000 hrs)**

| Component | Formula | Calculation | ₹/cycle |
|---|---|---|---|
| Battery | `(pack_cost − salvage) / lifetime_cycles` | `(15,000 − 3,000) / 600` | 20.00 |
| Charger | `charger_TCO / cycles_served` | *(see charger TCO sub-table)* | 4.20 |
| Electricity | `(capacity / efficiency) × tariff` | `(1.28 / 0.90) × 8.0` | 11.38 |
| Real estate | `rent / cycles_per_month` | `15,000 / 3,048` | 4.92 |
| Maintenance | `(preventive + corrective) / cycles_per_month` | `4,000 / 3,048` | 1.31 |
| Insurance | `premium / cycles_per_month` | `2,000 / 3,048` | 0.66 |
| Sabotage | `(packs × sabotage% × pack_cost) / cycles_per_month` | `...` | 0.74 |
| Logistics | `logistics_cost / cycles_per_month` | `5,000 / 3,048` | 1.64 |
| Overhead | `overhead / total_network_cycles_per_month` | `50,000 / 15,240` | 3.28 |
| **Total CPC** | | | **₹48.13** |
| **Cost per swap visit** | `CPC × packs_per_vehicle` | `48.13 × 2` | **₹96.26** |
| **Revenue per swap visit** | `price × packs_per_vehicle` | `40 × 2` | **₹80.00** |
| **Gross margin per swap** | `revenue − cost` | `80.00 − 96.26` | **−₹16.26** |

Below the CPC table, a **charger TCO sub-table** is shown (expandable):

| Charger TCO line | Formula | Calculation | ₹/slot |
|---|---|---|---|
| Purchase cost | — | — | 8,000 |
| Expected failures (over horizon) | `(op_hours/yr × horizon_yrs) / MTBF` | `(6,570 × 5) / 8,000` | 4.1 events |
| Total repair cost | `failures × repair_cost` | `4.1 × 1,500` | 6,150 |
| Replacements | `floor(failures / threshold)` | `floor(4.1 / 3)` | 1 unit |
| Replacement cost | `replacements × replacement_cost` | `1 × 7,500` | 7,500 |
| Downtime hours | `failures × MTTR` | `4.1 × 24` | 98.4 hrs |
| Lost revenue (downtime) | `hours × (swaps/hr × price × packs)` | *(derived)* | ... |
| Spare inventory | — | — | 8,000 |
| **Total charger TCO** | | | **₹...** |
| Cycles served over horizon | `cycles/day/dock × 365 × horizon_yrs` | ... | ... |
| **Charger cost per cycle** | `TCO / cycles_served` | | **₹4.20** |

#### 12.6.5 Section 3 — Monthly cash flow table

One table per charger variant (or tabs). Columns:

| Month | Fleet size | Swaps/month | Revenue (₹) | OpEx (₹) | CapEx (₹) | Net CF (₹) | Cumulative CF (₹) |
|---|---|---|---|---|---|---|---|
| 1 | 200 | 17,580 | 702,000 | ... | ... | ... | ... |
| 2 | 250 | 21,975 | 879,000 | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... | ... | ... |
| **→ 18** | **1,050** | **→ break-even** | ... | ... | ... | **+12,400** | **−234,000** |

- The **break-even month** row is highlighted (bold or colored background).
- Below the table: "Break-even at month 18 with 1,050 vehicles on network."

#### 12.6.6 Section 4 — Charger comparison summary

A single side-by-side table ranking all charger variants:

| Metric | Budget-1kW | Premium-1kW | Fast-3kW |
|---|---|---|---|
| Purchase cost/slot | ₹8,000 | ₹25,000 | ₹35,000 |
| MTBF (hours) | 8,000 | 40,000 | 30,000 |
| Charge time (min) | 85.3 | 85.3 | 28.4 |
| Effective C-rate | 0.78C | 0.78C | 2.34C |
| Charger TCO/slot (5yr) | ₹29,650 | ₹26,200 | ₹38,100 |
| **CPC — total (₹/cycle)** | **48.13** | **44.87** | **51.20** |
| CPC — charger component | 4.20 | 1.85 | 5.40 |
| Cost per swap visit | ₹96.26 | ₹89.74 | ₹102.40 |
| Gross margin per swap | −₹16.26 | −₹9.74 | −₹22.40 |
| Break-even month | 18 | 15 | 22 |
| 5yr cumulative CF | −₹1.2M | +₹0.4M | −₹2.1M |
| **Verdict** | — | **✓ Lowest CPC** | — |

This is the table that answers the charger question. No chart needed — the numbers speak.

### 12.7 Project layout (Phase 1 — what actually gets built)

```
zng-network-simulator/
├── README.md                           # This PRD
├── pyproject.toml                      # pydantic, streamlit, pyyaml, pytest
│
├── src/zng_simulator/
│   ├── __init__.py
│   │
│   ├── config/                         # Pydantic input models (§5)
│   │   ├── __init__.py                 # Re-exports all models
│   │   ├── vehicle.py                  # VehicleConfig
│   │   ├── battery.py                  # PackSpec
│   │   ├── charger.py                  # ChargerVariant
│   │   ├── station.py                  # StationConfig
│   │   ├── opex.py                     # OpExConfig
│   │   ├── revenue.py                  # RevenueConfig
│   │   ├── chaos.py                    # ChaosConfig
│   │   └── scenario.py                # Scenario (bundles everything)
│   │
│   ├── models/                         # Result types
│   │   ├── __init__.py
│   │   └── results.py                  # DerivedParams, CostPerCycleWaterfall,
│   │                                   # MonthlySnapshot, RunSummary,
│   │                                   # SimulationResult
│   │
│   ├── engine/                         # Computation logic
│   │   ├── __init__.py
│   │   ├── derived.py                  # compute_derived_params(vehicle, pack, charger, station)
│   │   ├── cost_per_cycle.py           # compute_cpc_waterfall(derived, pack, charger, opex, ...)
│   │   ├── charger_tco.py              # compute_charger_tco(charger, derived, revenue, horizon)
│   │   └── cashflow.py                 # compute_monthly_cashflow(scenario, charger) → SimulationResult
│   │
│   └── dashboard/
│       └── app.py                      # Single-file Streamlit app
│
├── scenarios/                          # Example YAML configs
│   └── base_case.yaml
│
└── tests/
    ├── conftest.py                     # Shared fixtures (sample Scenario)
    ├── test_derived.py                 # Unit tests for derived params
    ├── test_cpc.py                     # Unit tests for CPC waterfall
    ├── test_charger_tco.py             # Unit tests for charger TCO
    └── test_cashflow.py                # Unit tests for monthly cash flow
```

**What each engine module does (Phase 1):**

| Module | Input | Output | Logic |
|---|---|---|---|
| `derived.py` | `VehicleConfig`, `PackSpec`, `ChargerVariant`, `StationConfig` | `DerivedParams` | Pure arithmetic: usable energy, swaps/day, charge time, C-rate, cycles/day/dock, lifetime cycles |
| `charger_tco.py` | `ChargerVariant`, `DerivedParams`, `RevenueConfig`, `SimulationConfig` | charger TCO breakdown (dict) | Expected failures from MTBF, repair/replace costs, downtime lost revenue, spare inventory. All deterministic expected-value math. |
| `cost_per_cycle.py` | `DerivedParams`, `PackSpec`, `ChargerVariant`, `OpExConfig`, `ChaosConfig`, charger TCO | `CostPerCycleWaterfall` | Computes each of the 9 CPC components. Pure division: monthly cost ÷ monthly cycles. |
| `cashflow.py` | `Scenario`, specific `ChargerVariant` | `SimulationResult` | Loops over months: fleet ramps → swaps → revenue; OpEx from config; CapEx in month 0 (and pack/charger replacements). Produces `MonthlySnapshot` list + `RunSummary`. |

---

## 13. Phased roadmap & acceptance criteria

### Phase 1 — MVP (static economics + charger comparison)

**Goal**: deterministic calculator — enter inputs, see derived values with formulas, see cost-per-cycle waterfall, see monthly cash flow, compare chargers. No charts. No stochastic. Just correct, auditable, formula-visible numbers.

**What gets built:**

| Item | Files | Test coverage |
|---|---|---|
| Input models | `config/*.py` | Pydantic validation tests |
| Result models | `models/results.py` | Serialization round-trip |
| Derived params | `engine/derived.py` | Hand-calculated fixtures |
| Charger TCO | `engine/charger_tco.py` | MTBF → expected failures math |
| CPC waterfall | `engine/cost_per_cycle.py` | Each component individually |
| Monthly cash flow | `engine/cashflow.py` | Multi-month sequence, break-even |
| UI | `dashboard/app.py` | Manual (run and inspect) |
| Example scenario | `scenarios/base_case.yaml` | Loads without error |

**Acceptance criteria:**

1. User can enter all §5 inputs via Streamlit sidebar (vehicle, pack, 1+ charger variants, station, OpEx, revenue, chaos, horizon).
2. Clicking "Run" produces all four output sections on the main area.
3. **Section 1** (Derived params): every row shows metric name, symbolic formula, substituted calculation, and result value.
4. **Section 2** (CPC waterfall): for each charger variant, a table with 9 cost components + total, each with formula and calculation shown. Charger TCO sub-table is expandable.
5. **Section 3** (Monthly cash flow): month-by-month table with fleet size, swaps, revenue, OpEx, CapEx, net CF, cumulative CF. Break-even month flagged.
6. **Section 4** (Charger comparison): single summary table ranking charger variants by CPC, break-even, 5-year cumulative CF.
7. All engine functions have unit tests with hand-verified expected values.
8. A `base_case.yaml` scenario file loads and produces valid output.
9. **No charts, no graphs** — tables and numbers only.

### Phase 2 — The engine (reliability + uncertainty)
**Goal**: stochastic demand + battery degradation + charger failure simulation.

**What gets built**: `engine/degradation.py`, `engine/charger_reliability.py`, `engine/demand.py`, `engine/stochastic.py`. Existing modules untouched.

**Acceptance criteria**
- `StochasticEngine` implements same interface as Phase 1 static engine
- Demand modeled via Poisson/Gamma (configurable parameters)
- Battery SOH degrades by cycle + calendar (per pack spec parameters)
- Charger failures generated stochastically from MTBF (exponential or Weibull)
- Charger downtime reduces station throughput → affects SLA
- Produces failure-to-serve counts and wait-time estimates
- Cost per cycle now reflects **dynamic** degradation and failure rates

### Phase 3 — Financials (bankability + DCF decision-making)

**Goal**: full DCF, funds flow, SLB metrics, **and** discounted charger comparison. This is the phase that transforms the simulator from an operational tool into a **bankable financial model** — the kind of output that goes into an investor deck, a board memo, or a term-sheet negotiation.

**Pre-requisites**: Phase 1 (static engine) + Phase 2 (stochastic engine, Monte Carlo, cohort degradation, charger reliability) are complete. Phase 3 layers financial logic on top of the existing `MonthlySnapshot` and `RunSummary` outputs — it does not modify the simulation engines.

---

#### Phase 3 Implementation Plan

##### Step 3A — Config: Debt & Financial Inputs (`config/finance.py`)

**New file** — Pydantic model for debt structure and financial assumptions.

| Field | Type | Default | Description |
|---|---|---|---|
| `debt_pct_of_capex` | float | 0.70 | Portion of initial CapEx funded by debt (0–1) |
| `interest_rate_annual` | float | 0.12 | Annual interest rate on debt |
| `loan_tenor_months` | int | 60 | Loan repayment period |
| `grace_period_months` | int | 6 | Interest-only period before principal repayment starts |
| `depreciation_method` | Literal["straight_line", "wdv"] | "straight_line" | Depreciation method for assets |
| `asset_useful_life_months` | int | 60 | Accounting useful life of battery+charger assets |
| `tax_rate` | float | 0.25 | Corporate tax rate (for after-tax DCF) |
| `terminal_value_method` | Literal["salvage", "gordon_growth", "none"] | "salvage" | How to value the business at horizon end |
| `terminal_growth_rate` | float | 0.02 | For Gordon growth model (ignored if method != "gordon_growth") |

Also add `finance: FinanceConfig = Field(default_factory=FinanceConfig)` to `Scenario`.

**Deliverables**: `config/finance.py`, updated `config/scenario.py`, sidebar UI for debt inputs, validation tests.

---

##### Step 3B — Core DCF Engine (`finance/dcf.py`)

**New module** — takes monthly cash flows from any engine run and applies time-value-of-money.

**Functions**:

| Function | Input | Output | Logic |
|---|---|---|---|
| `compute_npv(cash_flows, rate)` | list[float], annual discount rate | float | Standard NPV: Σ CF_t / (1+r)^t |
| `compute_irr(cash_flows)` | list[float] | float \| None | Newton-Raphson or bisection search for rate where NPV=0. None if no real root. |
| `compute_discounted_payback(cash_flows, rate)` | list[float], annual rate | int \| None | First month where cumulative discounted CF ≥ 0 |
| `compute_terminal_value(config, last_year_ncf, total_salvage)` | FinanceConfig, float, float | float | Salvage method: sum of battery 2nd-life + charger residual. Gordon: NCF × (1+g) / (r−g). |
| `build_dcf_table(months, finance_cfg)` | list[MonthlySnapshot], FinanceConfig | DCFResult | Full month-by-month DCF table with discount factors, PV of each CF, cumulative PV, plus NPV/IRR/payback. |

**New result model** — `DCFResult(BaseModel)`:
- `npv: float` — Net Present Value
- `irr: float | None` — Internal Rate of Return
- `discounted_payback_month: int | None`
- `terminal_value: float`
- `monthly_dcf: list[MonthlyDCFRow]` — per-month: discount_factor, pv_revenue, pv_opex, pv_capex, pv_net_cf, cumulative_pv

**Tests**: Hand-calculated NPV/IRR for known cash flow streams, edge cases (all-negative CF → no IRR, zero discount rate = undiscounted sum).

---

##### Step 3C — Charger TCO in NPV Terms (`finance/charger_npv.py`)

**New module** — re-computes charger economics with discounting.

Current `charger_tco.py` uses undiscounted expected-value math. Phase 3 overlays discounting:

| Metric | Formula |
|---|---|
| **PV of repairs** | Σ repair_cost / (1+r)^t_i, with failures distributed uniformly across horizon |
| **PV of replacements** | Σ replacement_cost / (1+r)^t_j |
| **PV of lost revenue** | Σ downtime_revenue_loss / (1+r)^t_k |
| **NPV of charger TCO** | CapEx_0 + PV(repairs) + PV(replacements) + PV(lost_revenue) + PV(spare) − PV(salvage) |
| **Discounted CPC** | NPV_TCO / Σ (cycles_t / (1+r)^t) — PV-weighted cost per cycle |

**Discounted CPC trajectory**: month-by-month running PV-CPC that shows how the discounted unit economics evolve as degradation, failures, and fleet growth compound.

**Charger NPV comparison table**: ranks variants by NPV of full-network cash flows (not just charger TCO).

**Sensitivity matrix** (§7.3): vary MTBF ±20%, pack cost ±15%, electricity ±10% — show how NPV ranking changes. Stored as a dict[param_name, list[SensitivityPoint]].

**New result models**:
- `ChargerNPVComparison` — per-variant: npv_tco, discounted_cpc, npv_of_network, ranking
- `DiscountedCPCTrajectory` — list of (month, cumulative_discounted_cpc)

**Tests**: Verify NPV of charger TCO < undiscounted TCO (discount rate > 0), verify discounted CPC converges to a stable value.

---

##### Step 3D — Debt Schedule & DSCR (`finance/dscr.py`)

**New module** — models the debt side of the capital structure.

**Functions**:

| Function | Output |
|---|---|
| `build_debt_schedule(capex, finance_cfg)` | `DebtSchedule` — month-by-month: principal, interest, total payment, outstanding balance |
| `compute_dscr(months, debt_schedule)` | `DSCRResult` — monthly DSCR + average DSCR + min DSCR + covenant breach months |

**Debt schedule logic**:
1. `loan_amount = total_initial_capex × debt_pct_of_capex`
2. During grace period: interest-only payments (`loan_amount × monthly_rate`)
3. After grace period: equal monthly installment (EMI) amortization
4. EMI = `P × r × (1+r)^n / ((1+r)^n − 1)` where n = tenor − grace

**DSCR**:
- `DSCR_m = NOI_m / Debt_Service_m`
- `NOI_m = Revenue_m − OpEx_m` (operating income before CapEx and debt)
- Flag months where DSCR < 1.2 (typical SLB covenant threshold)

**SLB feasibility indicators**:
- Average DSCR over horizon
- Minimum DSCR and its month
- Months in covenant breach (DSCR < threshold)
- Asset cover ratio = (remaining battery value + charger value) / outstanding loan

**New result models**:
- `DebtScheduleRow` — month, opening_balance, interest, principal, emi, closing_balance
- `DebtSchedule` — list[DebtScheduleRow] + total_interest_paid
- `DSCRResult` — monthly_dscr: list[float], avg_dscr, min_dscr, min_dscr_month, breach_months: list[int], asset_cover_ratio

**Tests**: Verify EMI matches standard finance formula, verify DSCR = infinity when debt = 0, verify breach detection.

---

##### Step 3E — Financial Statements (`finance/statements.py`)

**New module** — generates investor-grade monthly financial statements.

| Statement | Rows |
|---|---|
| **P&L** | Revenue, (−) Electricity, (−) Station OpEx, (−) Labor, (−) Overhead, (−) Sabotage = **EBITDA**, (−) Depreciation = **EBIT**, (−) Interest = **EBT**, (−) Tax = **Net Income** |
| **Cash Flow Statement** | Operating CF (revenue − cash OpEx), Investing CF (−CapEx − pack replacements), Financing CF (debt drawdown − repayments), **Net CF**, Cumulative CF |
| **Balance Sheet** (simplified) | Assets: Gross assets − accumulated depreciation + cash. Liabilities: outstanding loan. Equity: retained earnings. |

**Depreciation**:
- Straight-line: `(asset_cost − salvage) / useful_life_months` per month
- WDV (Written Down Value): `rate × book_value` per year, spread monthly

**New result models**:
- `MonthlyPnL` — revenue, cogs (electricity + labor), gross_profit, station_opex, ebitda, depreciation, ebit, interest, ebt, tax, net_income
- `MonthlyCashFlowStatement` — operating_cf, investing_cf, financing_cf, net_cf, cumulative_cf
- `FinancialStatements` — pnl: list[MonthlyPnL], cashflow: list[MonthlyCashFlowStatement]

**Tests**: Verify EBITDA = Revenue − OpEx (no depreciation), verify Net CF = Operating + Investing + Financing.

---

##### Step 3F — Sensitivity / Tornado Analysis (`finance/sensitivity.py`)

**New module** — automated parameter sweeps for investor-grade what-if analysis.

**Logic**:
1. Define sweep parameters: `[(param_path, low_pct, high_pct)]` e.g. `[("pack.unit_cost", -0.15, +0.15), ("charger.mtbf_hours", -0.20, +0.20)]`
2. For each param, run the full engine at low and high values
3. Record `ΔNPV`, `ΔIRR`, `ΔCPC` at each extreme
4. Sort by |ΔNPV| descending → tornado chart data

**Output**: `SensitivityResult` — list of `TornadoBar(param_name, base_value, low_value, high_value, npv_at_low, npv_at_high, delta_npv)`, sorted by impact.

**Default sweep set** (user can customize):
- `pack.unit_cost` ± 15%
- `charger.mtbf_hours` ± 20%
- `opex.electricity_tariff_per_kwh` ± 10%
- `revenue.price_per_swap` ± 10%
- `pack.cycle_degradation_rate_pct` ± 20%
- `revenue.initial_fleet_size` ± 25%

**Tests**: Verify that increasing revenue increases NPV (sanity), verify symmetry check.

---

##### Step 3G — Dashboard Integration

**Updated `dashboard/app.py`** — new sections added after existing Phase 2 sections:

| Section | Content |
|---|---|
| **NPV & IRR** | Hero cards: NPV, IRR, discounted payback. Monthly DCF table (expandable). Terminal value breakdown. |
| **Discounted CPC** | Line chart: nominal CPC vs. discounted CPC over time. Per-charger variant if multiple. |
| **Charger NPV Comparison** | Table ranking chargers by NPV (replaces/augments the undiscounted Phase 1 comparison). Sensitivity matrix below. |
| **Debt & DSCR** | Debt schedule table. DSCR timeline chart with covenant threshold line. SLB feasibility card. |
| **P&L Summary** | Monthly P&L table. EBITDA margin trend. |
| **Sensitivity** | Tornado chart (horizontal bar chart sorted by NPV impact). |

All sections follow the "Show the Math" principle — formulas in expanders.

Finance sidebar inputs: debt %, interest rate, tenor, grace period, depreciation method, tax rate.

---

#### Phase 3 Dependency Graph

```
Step 3A (config)
  ├── Step 3B (DCF engine) ──────┐
  ├── Step 3C (charger NPV) ─────┼── Step 3G (dashboard)
  ├── Step 3D (debt/DSCR) ───────┤
  ├── Step 3E (statements) ──────┤
  └── Step 3F (sensitivity) ─────┘
```

Steps 3B–3F can be built in **parallel** after 3A. Step 3G integrates them all into the dashboard.

---

#### Phase 3 File Changes Summary

| Action | File | Description |
|---|---|---|
| **New** | `src/zng_simulator/config/finance.py` | FinanceConfig Pydantic model |
| **Edit** | `src/zng_simulator/config/scenario.py` | Add `finance: FinanceConfig` field |
| **Edit** | `src/zng_simulator/config/__init__.py` | Export FinanceConfig |
| **New** | `src/zng_simulator/finance/__init__.py` | Package init |
| **New** | `src/zng_simulator/finance/dcf.py` | NPV, IRR, terminal value, DCF table |
| **New** | `src/zng_simulator/finance/charger_npv.py` | Discounted charger TCO, NPV comparison |
| **New** | `src/zng_simulator/finance/dscr.py` | Debt schedule, DSCR, SLB metrics |
| **New** | `src/zng_simulator/finance/statements.py` | P&L, Cash Flow Statement, Balance Sheet |
| **New** | `src/zng_simulator/finance/sensitivity.py` | Parameter sweep, tornado data |
| **Edit** | `src/zng_simulator/models/results.py` | Add DCFResult, DSCRResult, etc. |
| **Edit** | `src/zng_simulator/dashboard/app.py` | New Phase 3 sections |
| **Edit** | `scenarios/base_case.yaml` | Add finance section |
| **New** | `tests/test_dcf.py` | DCF unit tests |
| **New** | `tests/test_dscr.py` | DSCR unit tests |
| **New** | `tests/test_charger_npv.py` | Charger NPV tests |
| **New** | `tests/test_statements.py` | Financial statement tests |
| **New** | `tests/test_sensitivity.py` | Sensitivity engine tests |

---

#### Phase 3 Acceptance Criteria (updated)

1. ✅ Computes **NPV and IRR** from simulated cash flows (static or stochastic)
2. ✅ Computes **charger TCO in NPV terms** (§6.3) and ranks charger variants by discounted TCO
3. ✅ Computes **discounted cost per cycle** across the project life — month-by-month trajectory
4. ✅ Computes **DSCR** with configurable debt schedule (amount, rate, tenor, grace period)
5. ✅ Computes **SLB feasibility** indicators (avg DSCR, min DSCR, covenant breach months, asset cover)
6. ✅ Includes **terminal value** from battery second-life salvage + charger residual
7. ✅ Produces **P&L, Cash Flow Statement** with operating/investing/financing separation
8. ✅ **Sensitivity / tornado** analysis for key parameters → NPV impact ranking
9. ✅ Dashboard shows all financial outputs with "Show the Math" formulas
10. ✅ All finance functions have unit tests with hand-verified expected values
11. ✅ Monte Carlo P10/P50/P90 carries through to NPV/IRR confidence intervals

### Phase 4 — Intelligence (optimization + field sync)
**Goal**: pilot sizing optimization, field-data parameter tuning, and auto-recommendations.

**What gets built**: `engine/field_data.py`, `engine/optimizer.py`, `models/field_data.py`. Existing modules untouched.

**Acceptance criteria**
- Pilot sizing search returns recommended scale under defined confidence level
- CSV ingestion for BMS data **and charger failure logs**
- Variance reports: projected vs actual for degradation and MTBF
- Model parameters auto-tuned from historical data
- System flags when field data changes a charger recommendation
