import os
import requests
import json
import statistics

# Configuration
RPC_URL = os.getenv("SEPOLIA_RPC_URL")

if not RPC_URL:
    try:
        # Fallback to loading from .env file manually if not in environment
        # This is simple .env parsing for the script
        env_vars = {}
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Remove quotes if present
                    value = value.strip().strip("'").strip('"')
                    env_vars[key.strip()] = value
        
        RPC_URL = env_vars.get("SEPOLIA_RPC_URL")
    except Exception:
        pass

if not RPC_URL:
    print("Error: SEPOLIA_RPC_URL environment variable not set.")
    exit(1)

def get_fee_history(block_count=10, reward_percentile=[30, 50, 70]):
    """
    Fetches fee history from the Ethereum network using eth_feeHistory.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_feeHistory",
        "params": [
            hex(block_count),
            "latest",
            reward_percentile
        ],
        "id": 1
    }
    
    try:
        response = requests.post(RPC_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise Exception(f"RPC Error: {data['error']}")
            
        return data["result"]
    except Exception as e:
        print(f"Error fetching fee history: {e}")
        return None

def calculate_fees(history):
    """
    Calculates optimized gas fees based on history.
    """
    # 1. Base Fee
    # eth_feeHistory returns limits for block_count + 1 blocks (the last one is the next block's base fee)
    base_fees = [int(x, 16) for x in history["baseFeePerGas"]]
    next_block_base_fee = base_fees[-1]
    
    # Analyze trend (last 5 blocks)
    recent_base_fees = base_fees[-6:-1]
    is_increasing = recent_base_fees[-1] > recent_base_fees[0]
    
    # 2. Priority Fee (Tip)
    # history["reward"] is a list of lists: [ [30th, 50th, 70th], ... ] for each block
    # We want to smooth out the volatility.
    
    # Extract the 50th percentile (median) from each block in history
    # reward_history is arrays of [percentile_1, percentile_2, ...]
    # We requested [30, 50, 70], so index 1 is the 50th percentile.
    recent_priority_fees = [int(r[1], 16) for r in history["reward"]]
    
    # Calculate a smoothed priority fee (Exponential Moving Average could be used, but median of medians is robust)
    # Using the median of the last 10 block medians avoids outliers.
    suggested_priority_fee = int(statistics.median(recent_priority_fees))
    
    # 3. Dynamic Buffer based on Congestion (Gas Used Ratio)
    gas_used_ratios = history["gasUsedRatio"]
    avg_congestion = sum(gas_used_ratios) / len(gas_used_ratios)
    
    # If congestion is high (> 80%), we might want to increase priority fee slightly to ensure inclusion
    if avg_congestion > 0.8:
        suggested_priority_fee = int(suggested_priority_fee * 1.2)
    elif avg_congestion < 0.3:
        # If network is empty, we can pay less, but never below a safe minimum (e.g. 1 gwei or lower for testnet)
        suggested_priority_fee = int(suggested_priority_fee * 0.9)

    # 4. Max Fee Calculation (EIP-1559)
    # Standard recommendation: (2 * Base Fee) + Priority Fee
    # This ensures transaction remains valid even if base fee doubles (6 consecutive full blocks)
    # For "optimized" savings, we can reduce the multiplier if the trend is stable/decreasing.
    
    base_fee_multiplier = 2.0
    if not is_increasing and avg_congestion < 0.5:
        base_fee_multiplier = 1.5  # Safe enough if network is not congested
        
    max_fee_per_gas = int((next_block_base_fee * base_fee_multiplier) + suggested_priority_fee)

    return {
        "base_fee_next": next_block_base_fee,
        "priority_fee_suggested": suggested_priority_fee,
        "max_fee_per_gas": max_fee_per_gas,
        "congestion": avg_congestion
    }

def main():
    print("Fetching gas fee history...")
    # Fetch last 10 blocks, requesting 30th, 50th, and 70th percentiles
    history = get_fee_history(block_count=10, reward_percentile=[30, 50, 70])
    
    if history:
        estimates = calculate_fees(history)
        
        print("\n=== Optimized Gas Estimation ===")
        print(f"Congestion (Avg Gas Used): {estimates['congestion']:.1%}")
        print(f"Base Fee (Next Block):     {estimates['base_fee_next'] / 1e9:.4f} Gwei")
        print(f"Priority Fee (Tip):        {estimates['priority_fee_suggested'] / 1e9:.4f} Gwei (Smoothed 50th percentile)")
        print(f"Max Fee (Cap):             {estimates['max_fee_per_gas'] / 1e9:.4f} Gwei ({(estimates['max_fee_per_gas']/estimates['base_fee_next']):.1f}x Base + Tip)")
        
        print("\n[Recommendation]")
        print(f"maxPriorityFeePerGas: {estimates['priority_fee_suggested']}")
        print(f"maxFeePerGas:         {estimates['max_fee_per_gas']}")

if __name__ == "__main__":
    main()
