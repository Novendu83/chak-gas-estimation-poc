// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./ERC20Mini.sol";

contract MockUSDC is ERC20Mini {
    address public owner;

    constructor() ERC20Mini("Mock USDC", "mUSDC", 6) {
        owner = msg.sender;
    }

    function mint(address to, uint256 amount) external {
        require(msg.sender == owner, "ONLY_OWNER");
        _mint(to, amount);
    }
}
