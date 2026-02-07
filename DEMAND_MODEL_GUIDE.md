# Demand Model Guide

## Distribution Options

### 1. Poisson Distribution
**Best for:** Simple count data, independent events
- **Characteristics:** Variance = mean, integer-valued
- **Use case:** Basic demand modeling when you don't have detailed usage patterns
- **Parameters:** None (variance is automatically determined by mean)

### 2. Gamma Distribution
**Best for:** Aggregated demand with configurable variance
- **Characteristics:** Heavier tails, flexible variance
- **Use case:** When demand has "memory" effects or you need to model higher variability
- **Parameters:**
  - **Volatility (CoV)**: 0.15 = mild, 0.3 = moderate, 0.5+ = high variability

### 3. Bimodal Distribution (NEW)
**Best for:** Dual-peak demand patterns
- **Characteristics:** Mixture of two Gaussian distributions
- **Use cases:**
  - Morning/evening commute rushes
  - Personal vs commercial user segments
  - Different vehicle types with distinct usage patterns
  - Peak/off-peak demand separation
- **Parameters:**
  - **Peak 1 weight** (0.1–0.9): Relative weight of first peak
    - 0.6 = 60% of demand from first peak, 40% from second
  - **Peak separation** (0.1–2.0): Distance between peaks (× mean)
    - 0.5 = peaks are 50% of mean demand apart
  - **Peak width** (0.05–0.5): Standard deviation of each peak (× mean)
    - 0.15 = each peak has σ = 15% of mean

## Temporal Patterns (All Distributions)

### Weekend Factor
- **Range:** 0.0–2.0
- **Default:** 0.6 (40% drop on weekends)
- **Examples:**
  - 1.0 = same demand on weekends
  - 0.6 = 40% lower (typical for commercial fleets)
  - 1.2 = 20% higher (leisure/tourism use)

### Seasonal Amplitude
- **Range:** 0.0–1.0
- **Default:** 0.0 (no seasonality)
- **Examples:**
  - 0.0 = flat demand year-round
  - 0.2 = ±20% annual swing
  - 0.4 = ±40% swing (monsoon, festivals, temperature effects)

## Example Configurations

### Configuration 1: Stable Commercial Fleet
```yaml
distribution: poisson
weekend_factor: 0.6
seasonal_amplitude: 0.1
```
Low variability, predictable weekday-heavy demand.

### Configuration 2: High-Variability Urban Mobility
```yaml
distribution: gamma
volatility: 0.35
weekend_factor: 0.8
seasonal_amplitude: 0.25
```
Higher variance, moderate weekend drop, seasonal effects.

### Configuration 3: Dual-Segment Fleet (Personal + Commercial)
```yaml
distribution: bimodal
bimodal_peak_ratio: 0.65
bimodal_peak_separation: 0.6
bimodal_std_ratio: 0.18
weekend_factor: 0.7
seasonal_amplitude: 0.15
```
65% commercial users (morning peak), 35% personal users (evening peak).

## Visualization

Enable **"Show demand preview"** in the sidebar to see:
1. **Distribution histogram** (1,000 simulated samples)
2. **90-day temporal pattern** with weekend shading
3. **Key statistics** (mean, std dev, CoV, peak/trough ratio)

This helps you understand exactly what demand pattern you're configuring before running the full simulation.
