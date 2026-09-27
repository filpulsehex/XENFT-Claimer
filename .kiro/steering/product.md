# Product Overview

## What this is
A command-line automation bot that **claims (redeems) matured XENFTs** on Ethereum
mainnet when gas fees are low. It is the companion to the XENFT Minter: the minter
creates XENFTs; this claimer collects the XEN rewards once they mature.

## What it does
- Continuously polls the current gas price.
- When gas is below a configured threshold for a set number of consecutive checks,
  it lists all XENFTs owned by the wallet (`ownedTokens`).
- For each token it performs a **dry run** of `bulkClaimMintReward` via `eth_call`
  (no gas spent) to determine, definitively, whether the token is claimable
  (matured) right now.
- Submits `bulkClaimMintReward(tokenId, wallet)` for each claimable token,
  re-checking gas before every individual claim.
- When nothing is claimable, it reports the **soonest upcoming maturity** by
  reading maturity timestamps from the XEN contract / packed mint info.

## Why it exists
XENFT rewards can only be claimed after a token matures, and claiming is only
economical when gas is cheap. Manually tracking dozens of maturity dates and
watching gas is impractical. This bot automates both: it knows what is claimable,
waits for cheap gas, and redeems automatically while reporting cost.

## Who uses it
The wallet owner only. Single-wallet, terminal-only tool. It signs transactions
locally with a private key loaded from a file.

## Key characteristics
- **Live-funds tool.** Each successful claim spends real ETH on gas.
- **Non-destructive checks.** Uses `eth_call` dry runs and view functions to
  decide claimability — no gas spent determining what to do.
- **Gas-gated.** Claims only when gas is below threshold, re-verified per token.
- **Maturity-aware.** Surfaces the next upcoming claimable token and its date.

## Success criteria
- Only attempts claims that would actually succeed (verified by dry run first).
- Never submits a claim the wallet cannot afford, and never claims above the gas
  limit (checked again immediately before each claim).
- Clear, timestamped reporting of claimable tokens, submissions, costs, and the
  next maturity when idle.

## Explicit non-goals
- Not a trading bot, portfolio manager, or financial-advice tool.
- Not a hosted service or shared product.
- Does not mint XENFTs — that is the separate XENFT Minter project.
