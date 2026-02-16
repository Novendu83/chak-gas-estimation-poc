# Gas Estimation Problem & Solution

## 1. Problem Statement

Accurate gas estimation is a critical challenge in Ethereum and EVM-compatible blockchain development. Users and applications face significant issues due to the volatile nature of gas fees:

*   **Transaction Reliability vs. Cost:** Users often have to choose between "fast" (expensive) and "slow" (risky). Standard estimators frequently provide a "average" price that doesn't guarantee inclusion during sudden traffic spikes, leading to **stuck transactions** (pending for hours/days).
*   **Overpayment:** To avoid stuck transactions, many wallets and dApps default to overestimating fees significantly (often by 20-50%), causing users to waste money on "priority fees" that aren't necessary for inclusion.
*   **Reactive, Not Proactive:** Most simple gas estimators look at the *past* average gas price. They fail to account for the *current* trend (e.g., is the base fee rising or falling?).
*   **Dependency Risks:** Relying on centralized third-party gas oracles (like Etherscan's API or GasStation) introduces a single point of failure and potential latency.
*   **Congestion Blindness:** Simple models often ignore block utilization (`gasUsedRatio`). A block that is 90% full signals rising fees, while a 10% full block signals falling fees. Ignoring this leads to poor estimates.

## 2. Our Approach

We have implemented a **dynamic, EIP-1559 native gas estimation model** that queries the blockchain node directly.

### **Core Components:**

1.  **Direct RPC Data (`eth_feeHistory`)**:
    *   We bypass third-party APIs and use the standard JSON-RPC method `eth_feeHistory`.
    *   This provides raw, granular data on the last `N` blocks, including:
        *   **Base Fee Per Gas:** The mandatory burn fee for each block.
        *   **Reward (Priority Fee) Percentiles:** The precise tips paid by transactions at different percentiles (e.g., 30th, 60th, 90th) within those blocks.
        *   **Gas Used Ratio:** How full each block was.

2.  **Predictive Modeling Logic:**
    *   **Base Fee Prediction:** We take the *next* block's base fee (calculated by the protocol) and apply a **volatility buffer**. Since the base fee can increase by up to 12.5% per block, we calculate a `MaxFee` that protects the user against `K` blocks of consecutive surges (e.g., protecting against 6 blocks of full surge for "Recommended" transactions).
    *   **Priority Fee Targeting:** Instead of a single "average," we calculate specific percentiles from the reward history:
        *   **Saver (30th %):** For non-urgent tasks (approvals).
        *   **Standard (60th %):** For typical usage.
        *   **Urgent (90th %):** For time-critical actions (mints, liquidations).
    *   **Congestion Multiplier:** We calculate the moving average of `gasUsedRatio`.
        *   If blocks are >80% full, we apply a **Surge Multiplier** (e.g., 1.25x) to the Priority Fee.
        *   If blocks are <45% full, we apply a **Discount** (e.g., 0.95x).

## 3. How This Solution Helps

| Feature | Benefit |
| :--- | :--- |
| **Forward-Looking MaxFee** | **Prevents Stuck Transactions.** By calculating the *potential* base fee rise over the next few blocks ($1.125^k$), we ensure the transaction remains valid even if the network suddenly becomes congested *after* the user signs. |
| **Percentile-Based Tips** | **Reduces Overpayment.** The "Recommended" tier (75th percentile) statistically beats the median transaction without competing with MEV bots (99th percentile), saving users money while maintaining speed. |
| **Congestion Awareness** | **Adapts to Traffic.** During NFT mints or market volatility, the model detects full blocks immediately and boosts the fee suggestion, ensuring the user's transaction isn't dropped. |
| **Zero External Dependency** | **High Availability.** The solution works with *any* standard Ethereum node (Infura, Alchemy, local node), removing reliance on specialized gas oracle services. |

## 4. Gaps & Future Improvements

While this POC provides a robust estimation model, the following gaps exist:

1.  **Private Mempool Visibility (MEV)**
    *   **Gap:** The `eth_feeHistory` API only sees confirmed blocks. It cannot see pending transactions in the public mempool or private bundles (Flashbots).
    *   **Impact:** In highly competitive scenarios (e.g., a "gas war" for a popular mint), the historical data might lag behind real-time demand driven by private bots.
    *   **Mitigation:** The "Urgent" tier helps, but integration with a mempool scanning service could improve accuracy for "sniping."

2.  **L2-Specific Cost Vectors**
    *   **Gap:** This model focuses on L1 EIP-1559 fees. Layer 2 networks (Optimism, Arbitrum, Base) have an additional cost component: **L1 Data Availability Fee**.
    *   **Impact:** On L2s, simply estimating the execution gas price isn't enough; the total cost must include the calldata cost posted to Ethereum L1.
    *   **Solution:** Future iterations need to query the L2-specific "L1 Fee/Scalar" oracles to provide a complete "Total Cost" estimate.

3.  **Production Infrastructure**
    *   **Gap:** Currently, the logic resides in Python scripts (`gas_model/`).
    *   **Solution:** To be used by a dApp, this logic needs to be:
        *   Ported to a backend API (FastAPI/Node.js) to serve the frontend.
        *   Or, implemented as a TypeScript client-side library to run directly in the user's browser (querying their connected wallet's RPC).

4.  **"Black Swan" Latency**
    *   **Gap:** In extreme events (e.g., 100+ block full surge), historical averages can lag.
    *   **Solution:** Implement a "Panic Mode" trigger if `baseFee` increases by >10% for 3 consecutive blocks, automatically shifting recommendation to the 95th percentile.
