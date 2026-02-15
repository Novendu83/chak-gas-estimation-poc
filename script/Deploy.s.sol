// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/MockUSDC.sol";
import "../src/ChakToken.sol";
import "../src/ChakSubscription.sol";

contract Deploy is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);

        MockUSDC usdc = new MockUSDC();
        ChakToken chak = new ChakToken();
        ChakSubscription sub = new ChakSubscription(address(usdc), address(chak));

        chak.setMinter(address(sub));

        vm.stopBroadcast();
    }
}
