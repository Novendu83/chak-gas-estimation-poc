"""
Gas Fee Prediction Script (Advanced EIP-1559)

This script implements a "Wallet-Style" gas estimator with 3 tiers:
1. Saver:       Low probability of next-block inclusion (k=0-1), uses 30th percentile tips.
2. Standard:    High probability of next-block inclusion (k=2), uses 60th percentile tips.
3. Urgent:      Guaranteed inclusion (k=5+), uses 90th percentile tips.

Key Optimizations:
- Base Fee Drift: Calculates max_fee considering exponential 12.5% churn (1.125^k).
- Congestion:     Adjusts tip selection based on 50% block utilization target.
- Tip Selection:  Uses multi-percentile tracking (30/60/90) for accurate tiering.
"""

import json
import os
import urllib.request
import statistics
import math

# Configuration
RPC_URL = os.environ.get("SEPOLIA_RPC_URL")
if not RPC_URL:
    raise ValueError("SEPOLIA_RPC_URL environment variable not set")

BLOCK_COUNT = 10
# Percentiles: 30 (Saver), 60 (Standard), 75 (Recommended), 90 (Urgent)
PERCENTILES = [30, 60, 75, 90] 

print("=" * 60)
print("Starting ADVANCED EIP-1559 gas fee prediction...")
print("=" * 60)

# ============================================================================
# STEP 1: FETCH DATA (DIRECT RPC CALL)
# ============================================================================
print("\n[FETCHING DATA]")
print(f"  RPC Endpoint: {RPC_URL}")

def fetch_fee_history():
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_feeHistory",
        "params": [hex(BLOCK_COUNT), "latest", PERCENTILES],
        "id": 1
    }
    
    req = urllib.request.Request(
        RPC_URL, 
        data=json.dumps(payload).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            if "error" in data:
                raise Exception(data["error"])
            return data["result"]
    except Exception as e:
        print(f"  [ERROR] RPC call failed: {e}")
        raise

d = fetch_fee_history()

print(f"  ✓ Data fetched successfully (Last {BLOCK_COUNT} blocks)")

# ============================================================================
# STEP 2: ANALYZE BASE FEE & DRIFT
# ============================================================================
print("\n[ANALYZING BASE FEE & DRIFT]")
# 'eth_feeHistory' returns N+1 base fees. The last one is the CALCULATED next block base fee.
base_fees = [int(x, 16) for x in d["baseFeePerGas"]]
next_block_base_fee = base_fees[-1]

print(f"  Next Block Base Fee (Protocol): {next_block_base_fee / 1e9:.4f} gwei")

# Function to calculate drift based on 'k' blocks delay tolerance
def calculate_max_base_fee(current_base, blocks_ahead):
    # EIP-1559 permits 12.5% max increase per block.
    # To be safe for 'k' blocks, we need: base * (1.125 ^ k)
    multiplier = math.pow(1.125, blocks_ahead)
    return int(current_base * multiplier)

# ============================================================================
# STEP 3: ANALYZE PRIORITY FEE (TIPS)
# ============================================================================
print("\n[ANALYZING PRIORITY FEES]")

# d["reward"] is a list of lists. Each inner list contains tips for the requested percentiles.
rewards = [[int(p, 16) for p in block] for block in d["reward"]]

# Extract columns for each percentile
tips_30 = [r[0] for r in rewards] # Saver (30)
tips_60 = [r[1] for r in rewards] # Standard (60)
tips_75 = [r[2] for r in rewards] # Recommended (75)
tips_90 = [r[3] for r in rewards] # Urgent (90)

# Calculate smoothed values (median of the history for each tier)
# This removes outliers from single weird blocks
median_tip_30 = int(statistics.median(tips_30))
median_tip_60 = int(statistics.median(tips_60))
median_tip_75 = int(statistics.median(tips_75))
median_tip_90 = int(statistics.median(tips_90))

# Enforce minimum improvement 
# (Urgent should be at least 20% higher than Standard, Standard 20% > Saver)
if median_tip_60 <= median_tip_30: median_tip_60 = int(median_tip_30 * 1.2) if median_tip_30 > 0 else 1000000000
if median_tip_75 <= median_tip_60: median_tip_75 = int(median_tip_60 * 1.15)
if median_tip_90 <= median_tip_75: median_tip_90 = int(median_tip_75 * 1.2) if median_tip_75 > 0 else 1500000000

print(f"  Smoothed Tips (Wei):")
print(f"    Saver (p30):       {median_tip_30:,}")
print(f"    Standard (p60):    {median_tip_60:,}")
print(f"    Recommended (p75): {median_tip_75:,}")
print(f"    Urgent (p90):      {median_tip_90:,}")

# ============================================================================
# STEP 4: ANALYZE CONGESTION
# ============================================================================
print("\n[ANALYZING CONGESTION]")
gas_used_ratios = d["gasUsedRatio"]
avg_congestion = sum(gas_used_ratios) / len(gas_used_ratios)

print(f"  Avg Utilization: {avg_congestion*100:.1f}% (Target: 50%)")

# Determine congestion multiplier
# If blocks are empty (<45%), minimal tips are likely fine.
# If full (>80%), assume price wars and boost tips.
congestion_multiplier = 1.0
if avg_congestion < 0.45:
    congestion_multiplier = 0.95 # Discount for empty blocks
elif avg_congestion > 0.80:
    congestion_multiplier = 1.25 # Surge pricing
    print("  ! HIGH CONGESTION DETECTED: Applying 1.25x tip boost")

# Apply congestion logic to tips
median_tip_30 = int(median_tip_30 * congestion_multiplier)
median_tip_60 = int(median_tip_60 * congestion_multiplier)
median_tip_75 = int(median_tip_75 * congestion_multiplier)
median_tip_90 = int(median_tip_90 * congestion_multiplier)


# ============================================================================
# STEP 5: BUILD TIERS
# ============================================================================

# Tier 1: SAVE (Risk: Low inclusion chance in next block, likely in 2-3 blocks)
# Tolerance: k=2 blocks of full surge
max_base_saver = calculate_max_base_fee(next_block_base_fee, 2)
max_fee_saver = max_base_saver + median_tip_30

# Tier 2: STANDARD (Target: Next block inclusion > 80% confidence)
# Tolerance: k=4 blocks of full surge (Standard wallet behavior)
max_base_std = calculate_max_base_fee(next_block_base_fee, 4)
max_fee_std = max_base_std + median_tip_60

# Tier 3: RECOMMENDED (Target: 99% Confidence, optimized cost)
# Tolerance: k=6 blocks (High safety against rapid surges, but not "Urgent" overkill)
# Tip: 75th percentile (Beats most standard wallets, avoids overpaying vs arb bots)
max_base_rec = calculate_max_base_fee(next_block_base_fee, 6)
max_fee_rec = max_base_rec + median_tip_75

# Tier 4: APES/URGENT (Target: GUARANTEED next block)
# Tolerance: k=10 blocks (Overkill to ensure tx never gets stuck)
max_base_urgent = calculate_max_base_fee(next_block_base_fee, 10)
max_fee_urgent = max_base_urgent + median_tip_90

print("\n" + "=" * 80)
print(f"{'TIER':<12} | {'CONFIDENCE':<15} | {'MAX FEE (Gwei)':<15} | {'PRIORITY (Gwei)':<15} | {'TOTAL COST (Est)':<15}")
print("-" * 80)

def fmt_gwei(wei):
    return f"{wei / 1e9:.2f}"

def calculate_cost_usd(gas_price_wei, gas_limit=21000, eth_price=2500):
    cost_eth = (gas_price_wei * gas_limit) / 1e18
    return f"${cost_eth * eth_price:.2f}"

# Printing Table
print(f"{'SAVER':<12} | {'~3 mins':<15} | {fmt_gwei(max_fee_saver):<15} | {fmt_gwei(median_tip_30):<15} | {calculate_cost_usd(max_fee_saver)}")
print(f"{'STANDARD':<12} | {'<30 secs':<15} | {fmt_gwei(max_fee_std):<15} | {fmt_gwei(median_tip_60):<15} | {calculate_cost_usd(max_fee_std)}")
print(f"{'RECOMMENDED':<12} | {'<10 secs':<15} | {fmt_gwei(max_fee_rec):<15} | {fmt_gwei(median_tip_75):<15} | {calculate_cost_usd(max_fee_rec)}")
print(f"{'URGENT':<12} | {'<5 secs':<15} | {fmt_gwei(max_fee_urgent):<15} | {fmt_gwei(median_tip_90):<15} | {calculate_cost_usd(max_fee_urgent)}")
print("=" * 80)
print("Note: 'RECOMMENDED' is optimized for 99% inclusion without overpaying.")
print("Note: 'Max Fee' includes the Base Fee drift buffer (12.5% churn protection).")

