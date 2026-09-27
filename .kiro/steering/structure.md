# Project Structure

## Current layout
```
XENFT Claimer/
├── XENFTClaimer.py   # The entire bot: config, ABIs, helpers, main loop
├── pk2.txt           # Wallet private key (MUST exist at runtime; never commit)
└── .kiro/
    └── steering/     # These steering docs
```

`XENFTClaimer.py` is a single file with clearly marked sections:
1. **CONFIG START/END** — gas threshold, priority fee, consecutive-check count,
   poll interval, RPC URL, wallet address, private-key loading.
2. **Contract addresses + minimal ABIs** — only the XENFT/XEN functions used.
3. **HELPERS** — `get_timestamp`, `get_eth_usd_value`, `get_gas_price`,
   `get_base_fee_gwei`, `is_claimable` (dry run), `get_maturity_ts`,
   `format_next_claimable`.
4. **MAIN LOGIC** — the gas-watch loop that lists owned tokens, dry-runs each for
   claimability, submits claims, and reports the next maturity when idle.

## Runtime expectations
- Working directory must contain `pk2.txt` (script exits if missing/malformed).
- Network access to the Infura RPC endpoint and CoinGecko is required.
- Assumes the wallet already owns XENFTs (typically minted by the XENFT Minter
  project). If none are owned, it idles and re-checks later.

## Security & secret-handling rules (important)
- **Never commit `pk2.txt`.** It holds a raw private key controlling real funds.
- **Never print, log, or echo the private key** or its contents beyond the
  existing "loaded successfully" confirmation.
- The committed script ships with **placeholders**: `your_wallet_address = '0x'`
  and an RPC URL ending in `YOUR_PROJECT_ID_HERE`. Keep them as placeholders in
  git — never replace them with a real Infura project ID or wallet address in a
  committed version. Users supply their own locally per the `README.md`.
- Prefer moving the RPC URL and wallet address to environment variables or a
  local, git-ignored config file in future edits rather than hardcoding real
  values.
- Recommend a `.gitignore` excluding `pk2.txt`, any `pk*.txt`, and `.env`. If
  asked to initialize git here, create that `.gitignore` first.

## Coding conventions
- Keep tunables in the CONFIG block; avoid magic numbers in the main loop.
- Preserve timestamped `print` logging for every meaningful step (waiting, gas OK,
  scanning, per-token claimability, submitting, confirming, result, next maturity).
- Before any claim submission, preserve this guard order:
  1. Gas below threshold for the required consecutive checks.
  2. Dry-run `bulkClaimMintReward(...).call()` confirms the token is claimable.
  3. Live gas re-checked immediately before the individual claim.
  4. EIP-1559 fees computed with buffer and headroom vs. base fee; priority capped.
  5. Affordability check (balance ≥ gas × maxFeePerGas) — abort/skip if it fails.
- On transient errors, log with `traceback`, reset counters, back off, and
  continue; only `break` on unrecoverable conditions (e.g. insufficient ETH).

## Relationship to the XENFT Minter project
- Sibling project in the same parent folder. Same stack, wallet, contracts, and
  secret-handling model. The Minter creates tokens; this Claimer redeems them.
- The `bulkClaimMintReward` maturity/bit-offset logic here is bespoke to reward
  redemption and should be kept in sync with any XEN/XENFT ABI changes.

## When extending
- Keep the single obvious entry point. If it grows, factor helpers into small
  modules imported by `XENFTClaimer.py`.
- Any change touching submission must keep the dry-run check, live gas re-check,
  and affordability guard intact.
