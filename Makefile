-include .env
export

build:
	forge build

deploy:
	forge script script/Deploy.s.sol:Deploy --rpc-url sepolia --broadcast -vvvv

seed:
	forge script script/SeedUsers.s.sol:SeedUsers --rpc-url sepolia --broadcast -vvvv

predict:
	python3 gas_model/predict_fees.py
