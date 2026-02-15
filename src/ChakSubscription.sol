// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20Like {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}

interface IChakToken {
    function mint(address to, uint256 amount) external;
    function burn(address from, uint256 amount) external;
}

contract ChakSubscription {
    address public immutable usdc;
    address public immutable chak;

    constructor(address _usdc, address _chak) {
        usdc = _usdc;
        chak = _chak;
    }

    function subscribe(uint256 amount) external {
        IERC20Like(usdc).transferFrom(msg.sender, address(this), amount);
        IChakToken(chak).mint(msg.sender, amount);
    }

    function redeem(uint256 amount) external {
        IChakToken(chak).burn(msg.sender, amount);
        IERC20Like(usdc).transfer(msg.sender, amount);
    }
}
