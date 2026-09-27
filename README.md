# XENFT Claimer

A command-line bot that automatically **claims (redeems) matured XENFTs** on Ethereum mainnet when gas fees are low. It's the companion to the [XENFT Minter](../XENFT%20Minter): the minter creates XENFTs, and this claimer collects the XEN rewards once they mature.

It watches the gas price, lists the XENFTs your wallet owns, checks which ones are ready to claim (using a free "dry run" so no gas is wasted testing), and then submits claim transactions when gas is cheap. When nothing is claimable yet, it tells you the soonest upcoming maturity date.

> ⚠️ **This tool spends real ETH on Ethereum mainnet.** Every successful claim costs gas. Read the whole README before running it, and test with a wallet that holds only a small amount of ETH first.

---

## What you need before you start

You must supply **three things of your own**. The script will not work without them, and you should never use someone else's:

1. **Your own Infura RPC URL** — your connection to the Ethereum network.
2. **Your own wallet address** — the Ethereum address that owns the XENFTs and pays the gas.
3. **Your own wallet private key** — required to sign transactions. This is placed in a file called `pk2.txt`.

These three are covered in detail in **[Configuration](#configuration)** below.

---

## Prerequisites

- **Python 3.9 or newer** — check with `python --version`.
- **pip** (comes with Python).
- A **funded Ethereum wallet** that **already owns XENFTs** (typically minted with the XENFT Minter). If it owns none, the claimer will simply idle.
- An **Infura account** (free tier is fine).

---

## Installation

1. **Get the code** (clone the repo or download `XENFTClaimer.py`):
   ```bash
   git clone https://github.com/<your-username>/<your-repo>.git
   cd <your-repo>/"XENFT Claimer"
   ```

2. **Install the Python dependencies:**
   ```bash
   pip install web3 requests pycoingecko
   ```
   (Optional but recommended: use a virtual environment first — `python -m venv venv` then activate it.)

---

## Configuration

Open `XENFTClaimer.py` in a text editor. All the settings live in the `CONFIG START` / `CONFIG END` block near the top.

### 1. Infura RPC URL (required — use your own)

Sign up for a free account at [infura.io](https://www.infura.io/), create a new API key/project, and copy your **Ethereum Mainnet** HTTPS endpoint. It looks like:

```
https://mainnet.infura.io/v3/YOUR_PROJECT_ID_HERE
```

Set it in the script:
```python
rpc_url = "https://mainnet.infura.io/v3/YOUR_PROJECT_ID_HERE"
```

> Do **not** reuse the endpoint that ships in the file. Use your own — it's tied to your account and rate limits.

### 2. Wallet address (required — use your own)

```python
your_wallet_address = '0xYourWalletAddressHere'
```
This must be the wallet that **owns the XENFTs** you want to claim, and it pays the gas.

### 3. Private key (required — use your own, keep it secret)

The script reads your private key from a file named **`pk2.txt`** in the same folder as `XENFTClaimer.py`.

1. Copy the provided `pk2.txt.example` to a new file called `pk2.txt` in the `XENFT Claimer` folder (or just create `pk2.txt` from scratch).
2. Paste **only** your wallet's private key into it (a 64-character hex string). A leading `0x` is optional.
3. Save it. Nothing else should be in the file.

> 🔐 **Never share your private key, commit it to git, or paste it anywhere online.** Anyone with it can drain your wallet. See [Security](#security) below.

### 4. Claim settings (tune to taste)

| Setting | Default | What it does |
|---|---|---|
| `only_claim_if_gas_is_below` | `0.042` | Only claim when gas (gwei) is below this. Lower = cheaper but less frequent. |
| `max_priority_fee_per_gas` | `0.005` | EIP-1559 priority (tip) fee in gwei. |
| `claim_when_consecutive_count` | `2` | Gas must be low this many checks in a row before claiming. |
| `how_many_seconds_between_checks` | `3` | Seconds between gas checks. |

---

## Running it

From the `XENFT Claimer` folder (with `pk2.txt` present):

```bash
python XENFTClaimer.py
```

Here's what happens:

- The bot watches gas. While it's too high, it prints `Waiting...`.
- Once gas is low enough, it fetches all XENFTs owned by your wallet.
- For each token it does a **dry run** (a free simulated call, no gas) to see if it's actually claimable (matured). Claimable tokens are marked ✅; not-yet-matured ones are marked ⏳.
- It then submits a claim for each claimable token, **re-checking gas before every single claim**, and reports the tx hash, an Etherscan link, and the actual gas cost.
- If nothing is claimable right now, it prints the **next upcoming maturity date(s)** so you know when to expect the next claim, then waits and checks again later.

To stop it at any time, press **Ctrl+C**.

---

## Safety features built in

- **Dry-run first:** claimability is tested with a free simulated call, so no gas is spent finding out what's ready.
- **Gas gating:** nothing is submitted unless gas is below your threshold for the required consecutive checks, and gas is re-checked right before each individual claim.
- **Affordability check:** the script skips/aborts a claim if your wallet can't cover the gas, so it won't strand a failed transaction.
- **Maturity insight:** when idle, it reports the soonest token(s) coming up for claim and their dates.

---

## Security

- **`pk2.txt` holds your private key. Treat it like the keys to your house.**
- Add a `.gitignore` so you never commit it. At minimum:
  ```
  pk2.txt
  pk*.txt
  .env
  __pycache__/
  ```
- Consider using a **dedicated "hot" wallet** that holds only what you need for gas, rather than your main wallet.
- Never paste your private key into a website, chat, or support ticket. No legitimate tool or person will ask for it.
- The Infura URL and wallet address are less sensitive than the private key, but still personal to you — keep them out of public commits where practical.

---

## Troubleshooting

| Symptom | Likely fix |
|---|---|
| `pk2.txt not found` | Create `pk2.txt` in the same folder as `XENFTClaimer.py`. |
| `Private key looks invalid` | It must be 64 hex characters (0x optional). No spaces or quotes. |
| `No XENFTs owned by this wallet` | This wallet holds no XENFTs to claim — check you set the right address, or mint some first. |
| Tokens always show ⏳ Not claimable | They haven't matured yet. The script prints the upcoming maturity dates. |
| Never claims | Your `only_claim_if_gas_is_below` may be lower than current gas — raise it, or wait for cheaper gas. |
| RPC / connection errors | Check your Infura URL is correct and your project is active. |
| `ModuleNotFoundError` | Run `pip install web3 requests pycoingecko`. |

---

## Disclaimer

This software is provided as-is, for educational purposes, with no warranty. It interacts with real funds on Ethereum mainnet. You are solely responsible for any transactions it makes and any ETH it spends. Use at your own risk, and always test with a small amount first.
