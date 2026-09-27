# Technology Stack

## Language & runtime
- **Python 3** (uses 3.9+ syntax and typing such as `tuple[bool, str]`,
  `Optional`, `str.removeprefix`).
- Single-file script: `XENFTClaimer.py`. Run with `python XENFTClaimer.py`.

## Key libraries
- **web3.py** (`web3`) — Ethereum RPC, contract view calls, `eth_call` dry runs,
  EIP-1559 transaction building, local signing.
- **requests** — direct JSON-RPC `eth_gasPrice` polling.
- **pycoingecko** (`CoinGeckoAPI`) — live ETH/USD price for cost reporting.
- Standard library: `time`, `datetime`, `traceback`, `pathlib`, `typing`.

## External services
- **Ethereum mainnet** via an **Infura** HTTPS RPC endpoint.
- **CoinGecko API** for ETH price (no key required).

## On-chain contracts
- **XENFT** contract: `0x0a252663dbcc0b073063d6420a40319e438cfa59`
  - `ownedTokens()` — list token IDs held by the wallet.
  - `bulkClaimMintReward(tokenId, to)` — redeem a matured token (also dry-run via
    `.call()` to test claimability).
  - `mintInfo(tokenId)` — packed uint256 containing the mint proxy address / data.
  - `vmuCount(tokenId)` — VMUs for a token.
- **XEN Crypto** contract: `0x06450dEe7FD2Fb8E39061434BAbCFC05599a6Fb8`
  - `userMints(proxyAddress)` — returns the MintInfo struct (incl. `maturityTs`)
    for a token's proxy, used to compute true maturity.
- Both use **minimal, purpose-built ABIs** embedded as JSON strings (only the
  functions this script needs), unlike the Minter's full ABIs.

## How claimability & maturity are determined
- **Claimable now:** dry-run `bulkClaimMintReward(...).call()`; success ⇒
  claimable, revert ⇒ not yet (definitive, no gas).
- **True maturity:** extract the proxy address from the lower 160 bits of
  `mintInfo`, then read `XEN.userMints(proxy).maturityTs`.
- **Next-maturity display:** a heuristic that auto-detects the bit offset of the
  32-bit maturity timestamp inside the packed `mintInfo` value (validated to be a
  plausible future timestamp within ~5 years), then sorts upcoming tokens.

## Transaction model
- **EIP-1559**: `maxFeePerGas` from polled gas (×1.05 buffer); priority fee capped
  below max; extra headroom vs. live `baseFeePerGas` to avoid "maxFee < baseFee".
- Gas limit = `estimate_gas × 1.20`, hard-capped at 15,000,000.
- Affordability check before each claim; confirmation via balance-change polling
  (~5 min max), not receipt lookup.

## Configuration (constants at top of file)
- `only_claim_if_gas_is_below` — gas threshold in gwei (default 0.042).
- `max_priority_fee_per_gas` — priority fee in gwei.
- `claim_when_consecutive_count` — required consecutive low-gas checks.
- `how_many_seconds_between_checks` — poll interval.

## Secrets & credentials
- Wallet **private key** read from a local file named **`pk2.txt`** (64 hex chars,
  `0x` optional; script exits if missing/invalid).
- `your_wallet_address` and `rpc_url` are **placeholders** in the committed
  script: `your_wallet_address = '0x'` and the RPC URL ends in
  `YOUR_PROJECT_ID_HERE`. Each user fills in their own Infura project ID and
  wallet address before running (see `README.md`).
- Keep these as placeholders in anything committed to git — never commit a real
  Infura project ID, wallet address, or the `pk2.txt` private key (see
  `structure.md`).

## Running
- Prerequisites: `pip install web3 requests pycoingecko`.
- Ensure `pk2.txt` exists in the working directory.
- `python XENFTClaimer.py` — runs an infinite gas-watch/claim loop.

## Conventions for future changes
- Keep it a dependency-light, single-file script.
- Always decide claimability with a dry run before spending gas.
- Preserve the "re-check gas immediately before each individual claim" pattern and
  the affordability guard.
