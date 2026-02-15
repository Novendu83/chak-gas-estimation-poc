// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./ERC20Mini.sol";

contract ChakToken is ERC20Mini {
    address public minter;

    constructor() ERC20Mini("Chak Stable Token", "CHAK", 6) {
        minter = msg.sender;
    }

    function setMinter(address m) external {
        require(msg.sender == minter, "ONLY_ADMIN");
        minter = m;
    }

    function mint(address to, uint256 amount) external {
        require(msg.sender == minter, "ONLY_MINTER");
        _mint(to, amount);
    }

    function burn(address from, uint256 amount) external {
        require(msg.sender == minter, "ONLY_MINTER");
        _burn(from, amount);
    }
}
