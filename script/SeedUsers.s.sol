// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MockUSDC.sol";

contract SeedUsers is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        address usdc = vm.envAddress("USDC_ADDRESS");
        address u1 = vm.envAddress("USER1");

        vm.startBroadcast(pk);
        MockUSDC(usdc).mint(u1, 1000 * 1e6);
        vm.stopBroadcast();
    }
}
