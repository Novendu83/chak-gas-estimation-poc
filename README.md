# Chak Token Gas Estimation POC

This project demonstrates:
- Mock USDC token
- Chak Stable Token (1:1 peg)
- Subscription contract
- Gas prediction using Infura feeHistory
- Foundry scripts and cast testing

## Setup

cp .env.example .env
forge build
make deploy

## Gas Prediction

make fee-data
make predict
