import time
import datetime
import traceback
import requests
from pathlib import Path
from typing import Optional
from web3 import Web3
from pycoingecko import CoinGeckoAPI

# DISCLAIMER: Use at your own risk. This interacts with real Ethereum mainnet.
# Never share your private key. Test with small amounts first.

## ----------- CONFIG START ----------- ##

only_claim_if_gas_is_below       = 0.042   # max gas price in gwei to trigger a claim
max_priority_fee_per_gas         = 0.005   # EIP-1559 priority fee in gwei

claim_when_consecutive_count     = 2     # gas must be low this many checks in a row
how_many_seconds_between_checks  = 3

rpc_url = "https://mainnet.infura.io/v3/YOUR_PROJECT_ID_HERE"

web3 = Web3(Web3.HTTPProvider(rpc_url))

your_wallet_address = '0x'

# ─── Load private key ────────────────────────────────────────────
PK_FILE = "pk2.txt"

try:
    pk_content = Path(PK_FILE).read_text(encoding="utf-8").strip()
    if not pk_content.startswith("0x"):
        your_wallet_address_private_key = "0x" + pk_content
    else:
        your_wallet_address_private_key = pk_content
except FileNotFoundError:
    print(f"❌ Error: {PK_FILE} not found in the current directory!")
    exit(1)
except Exception as e:
    print(f"❌ Error reading {PK_FILE}: {e}")
    exit(1)

pk_hex = your_wallet_address_private_key.removeprefix("0x")
if len(pk_hex) != 64 or not all(c in "0123456789abcdefABCDEF" for c in pk_hex):
    print("❌ Private key looks invalid (should be 64 hex chars)")
    exit(1)

print("Private key loaded successfully ✓")

xenft_contract_address = web3.to_checksum_address('0x0a252663dbcc0b073063d6420a40319e438cfa59')
xen_contract_address   = web3.to_checksum_address('0x06450dEe7FD2Fb8E39061434BAbCFC05599a6Fb8')

xenft_abi = '''[
  {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"address","name":"to","type":"address"}],"name":"bulkClaimMintReward","outputs":[],"stateMutability":"nonpayable","type":"function"},
  {"inputs":[],"name":"ownedTokens","outputs":[{"internalType":"uint256[]","name":"","type":"uint256[]"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"mintInfo","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"vmuCount","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]'''

# Minimal XEN ABI — only userMints is needed
xen_abi = '''[
  {"inputs":[{"internalType":"address","name":"","type":"address"}],"name":"userMints","outputs":[{"components":[{"internalType":"address","name":"user","type":"address"},{"internalType":"uint256","name":"term","type":"uint256"},{"internalType":"uint256","name":"maturityTs","type":"uint256"},{"internalType":"uint256","name":"rank","type":"uint256"},{"internalType":"uint256","name":"amplifier","type":"uint256"},{"internalType":"uint256","name":"eaaRate","type":"uint256"}],"internalType":"struct XENCrypto.MintInfo","name":"","type":"tuple"}],"stateMutability":"view","type":"function"}
]'''

## ------------ CONFIG END ------------ ##

## ----------- HELPERS ----------- ##

def get_timestamp():
    now = datetime.datetime.now()
    return f"{now.year}-{now.month:02d}-{now.day:02d} {now.hour:02d}:{now.minute:02d}:{now.second:02d}"

def get_eth_usd_value():
    cg = CoinGeckoAPI()
    price = cg.get_price(ids=['ethereum'], vs_currencies='usd')
    return price['ethereum']['usd']

def get_gas_price():
    """Returns current gas price in gwei with a 5% buffer."""
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    resp = session.post(
        url=rpc_url,
        json={"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1}
    )
    gas_price_gwei = int(resp.json()['result'], 16) / 1e9
    return round(gas_price_gwei * 1.05, 3)

def get_base_fee_gwei():
    """Returns the latest block's baseFeePerGas in gwei."""
    latest = web3.eth.get_block('latest')
    base_fee = latest.get('baseFeePerGas', 0)
    return base_fee / 1e9  # wei → gwei

def is_claimable(contract, token_id: int, wallet: str) -> tuple[bool, str]:
    """
    Dry-run bulkClaimMintReward via eth_call (no gas spent).
    Returns (True, "") if the call would succeed, or (False, reason) if it would revert.
    This is the definitive maturity check — no bit-twiddling required.
    """
    try:
        contract.functions.bulkClaimMintReward(token_id, wallet).call(
            {'from': wallet}
        )
        return True, ""
    except Exception as e:
        msg = str(e)
        return False, msg

def get_maturity_ts(contract, xen_contract, token_id: int) -> Optional[int]:
    """
    Gets the true maturityTs for a XENFT token by querying the XEN contract's
    userMints mapping for the token's proxy address.

    The XENFT mintInfo uint256 stores the proxy contract address in the lower
    160 bits. Each proxy called claimRank on XEN, so XEN's userMints[proxy]
    holds the full MintInfo struct including the real maturityTs.
    """
    try:
        packed = contract.functions.mintInfo(token_id).call()
        if packed == 0:
            return None

        # Extract proxy address from lower 160 bits
        proxy_address = web3.to_checksum_address(
            '0x' + hex(packed & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)[2:].zfill(40)
        )

        # Query XEN contract for this proxy's mint info
        mint_info = xen_contract.functions.userMints(proxy_address).call()
        # userMints returns: (user, term, maturityTs, rank, amplifier, eaaRate)
        maturity_ts = mint_info[2]

        if maturity_ts == 0:
            return None  # already claimed or never minted

        return maturity_ts

    except Exception:
        return None

def format_next_claimable(contract, xen_contract, owned: list) -> str:
    """
    Scans all owned tokens for their maturity timestamps and returns
    a message about the soonest upcoming claimable token.

    From live on-chain debug data, token #135865 packed value:
      0x015e000000006b950d7b0000000000000000000000000000377b73d06c600000200
    The term is 0x15e = 350 days. The maturityTs 0x6b950d7b = 1804984699
    (2027-03-12 UTC) which is a valid future timestamp.
    We scan bit offsets to find where this 32-bit value sits.
    """
    now_ts = int(time.time())
    MIN_TS = 1700000000  # Nov 2023 — earliest plausible XENFT maturity

    # Auto-detect the correct bit offset on the first token
    # Strategy: the maturityTs must be > now and < 5 years from now (realistic term lengths)
    # This excludes rank values which are huge numbers that also pass a simple MIN_TS check
    detected_offset = None
    MAX_TS = now_ts + (5 * 365 * 86400)  # 5 years out max

    for token_id in owned[:6]:
        try:
            packed = contract.functions.mintInfo(token_id).call()
            if packed == 0:
                continue
            for offset in range(0, 224, 8):
                candidate = (packed >> offset) & 0xFFFFFFFF
                if MIN_TS < candidate < MAX_TS:
                    detected_offset = offset
                    break
            if detected_offset is not None:
                break
        except Exception:
            continue

    if detected_offset is None:
        return "  (Could not determine next maturity date)"

    upcoming = []
    for token_id in owned:
        try:
            packed = contract.functions.mintInfo(token_id).call()
            if packed == 0:
                continue
            maturity_ts = (packed >> detected_offset) & 0xFFFFFFFF
            if maturity_ts > MIN_TS and now_ts < maturity_ts < MAX_TS:
                upcoming.append((maturity_ts, token_id))
        except Exception:
            continue

    if not upcoming:
        return "  (Could not determine next maturity date)"

    upcoming.sort()
    lines = []
    next_ts, next_id = upcoming[0]
    delta_secs = next_ts - now_ts
    mat_str = datetime.datetime.utcfromtimestamp(next_ts).strftime('%Y-%m-%d %H:%M UTC')
    timing = f"{delta_secs/3600:.1f} hours" if delta_secs < 86400 else f"{delta_secs/86400:.1f} days"
    lines.append(f"  Next claimable: Token #{next_id} in {timing} (matures {mat_str})")

    if len(upcoming) > 1:
        lines.append(f"  All upcoming ({len(upcoming)} tokens):")
        for ts, tid in upcoming[:8]:
            d = ts - now_ts
            s = datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M UTC')
            t = f"{d/3600:.1f}h" if d < 86400 else f"{d/86400:.1f}d"
            lines.append(f"    Token #{tid}: {t} ({s})")
        if len(upcoming) > 8:
            lines.append(f"    ... and {len(upcoming) - 8} more")

    return "\n".join(lines)

## ----------- MAIN LOGIC ----------- ##

print("─" * 70)
print("XENFT CLAIM SCRIPT")
print(f"Wallet:          {your_wallet_address}")
print(f"Max gas:         {only_claim_if_gas_is_below} gwei")
print(f"Priority fee:    {max_priority_fee_per_gas} gwei")
print(f"Consecutive req: {claim_when_consecutive_count} checks")
print("─" * 70)

contract     = web3.eth.contract(address=xenft_contract_address, abi=xenft_abi)
xen_contract = web3.eth.contract(address=xen_contract_address,   abi=xen_abi)

consecutive_count = 0

while True:
    try:
        # ── Gas check ──────────────────────────────────────────────────────
        current_gas = get_gas_price()

        if current_gas > only_claim_if_gas_is_below:
            consecutive_count = 0
            print(f"{get_timestamp()} - Waiting... Gas: {current_gas} gwei (limit: {only_claim_if_gas_is_below})")
            time.sleep(how_many_seconds_between_checks)
            continue

        consecutive_count += 1
        print(f"{get_timestamp()} - Gas OK: {current_gas} gwei  ({consecutive_count}/{claim_when_consecutive_count})")

        if consecutive_count < claim_when_consecutive_count:
            time.sleep(how_many_seconds_between_checks)
            continue

        # ── Gas is low enough — scan for claimable tokens ──────────────────
        print(f"{get_timestamp()} - Gas low enough. Scanning owned tokens...")

        owned = contract.functions.ownedTokens().call({'from': your_wallet_address})

        if not owned:
            print(f"{get_timestamp()} - No XENFTs owned by this wallet. Nothing to claim.")
            consecutive_count = 0
            time.sleep(how_many_seconds_between_checks * 60)
            continue

        print(f"{get_timestamp()} - Found {len(owned)} XENFT(s). Dry-running each to check claimability...")

        claimable_tokens = []

        for token_id in owned:
            ok, reason = is_claimable(contract, token_id, your_wallet_address)
            if ok:
                print(f"  Token #{token_id}: ✅ Claimable")
                claimable_tokens.append(token_id)
            else:
                # Condense the revert reason to one line
                short = reason.splitlines()[0][:120] if reason else "unknown reason"
                print(f"  Token #{token_id}: ⏳ Not claimable — {short}")

        if not claimable_tokens:
            next_msg = format_next_claimable(contract, xen_contract, owned)
            print(f"{get_timestamp()} - No claimable tokens right now.")
            print(next_msg)
            consecutive_count = 0
            time.sleep(how_many_seconds_between_checks * 60)
            continue

        print(f"\n{get_timestamp()} - {len(claimable_tokens)} token(s) ready to claim: {claimable_tokens}")

        eth_usd       = get_eth_usd_value()
        claimed_count = 0
        skipped_count = 0

        for token_id in claimable_tokens:

            # ── Re-check gas before EVERY individual claim ─────────────────
            live_gas = get_gas_price()
            if live_gas > only_claim_if_gas_is_below:
                print(f"\n{get_timestamp()} - Gas rose to {live_gas} gwei — pausing batch, will retry next window.")
                consecutive_count = 0
                break

            # ── Also verify against actual base fee to avoid "maxFee < baseFee" errors
            base_fee = get_base_fee_gwei()
            max_fee  = live_gas   # our maxFeePerGas = current gas price (already includes 5% buffer)

            if max_fee < base_fee * 1.05:
                # Add headroom: bump maxFeePerGas to base_fee * 1.15
                max_fee = round(base_fee * 1.15, 3)
                print(f"  ⚠️  maxFee ({live_gas}) was close to baseFee ({base_fee:.3f}) — bumped to {max_fee} gwei")

            try:
                print(f"\n{get_timestamp()} - Claiming token #{token_id}...")

                balance_before = round(float(web3.from_wei(web3.eth.get_balance(your_wallet_address), 'ether')), 6)

                effective_priority = min(max_priority_fee_per_gas, max_fee * 0.9)

                tx = contract.functions.bulkClaimMintReward(
                    token_id,
                    your_wallet_address
                ).build_transaction({
                    'from': your_wallet_address,
                    'nonce': web3.eth.get_transaction_count(your_wallet_address, 'pending'),
                    'maxFeePerGas': web3.to_wei(max_fee, 'gwei'),
                    'maxPriorityFeePerGas': web3.to_wei(effective_priority, 'gwei'),
                    'chainId': web3.eth.chain_id,
                })

                gas_estimate = web3.eth.estimate_gas(tx)
                tx['gas'] = min(int(gas_estimate * 1.20), 15_000_000)

                required_eth = tx['gas'] * tx['maxFeePerGas']
                if web3.eth.get_balance(your_wallet_address) < required_eth:
                    min_eth = float(web3.from_wei(required_eth, 'ether'))
                    print(f"  CRITICAL: Insufficient ETH. Need {min_eth:.6f} ETH. Stopping.")
                    break

                est_cost_eth = round(float(web3.from_wei(tx['gas'] * tx['maxFeePerGas'], 'ether')), 6)
                print(f"  Balance before: {balance_before} ETH  |  Est. gas: {est_cost_eth} ETH (~${round(est_cost_eth * eth_usd, 2)})")

                signed_tx = web3.eth.account.sign_transaction(tx, your_wallet_address_private_key)
                tx_hash   = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hex    = web3.to_hex(tx_hash)

                print(f"  Tx submitted: {tx_hex}")
                print(f"  Etherscan:    https://etherscan.io/tx/{tx_hex}")

                # Wait for balance change (confirmation)
                test_count = 0
                confirmed  = False
                while test_count <= 60:
                    test_count += 1
                    current_balance = round(float(web3.from_wei(web3.eth.get_balance(your_wallet_address), 'ether')), 6)
                    if current_balance != balance_before:
                        confirmed = True
                        break
                    print(f"  Waiting for confirmation... #{test_count}")
                    time.sleep(how_many_seconds_between_checks + 10)

                if not confirmed:
                    print(f"  ⚠️  No balance change after ~5 min — tx may have failed or been dropped")
                    skipped_count += 1
                    continue

                balance_after   = round(float(web3.from_wei(web3.eth.get_balance(your_wallet_address), 'ether')), 6)
                actual_cost     = round(balance_before - balance_after, 6)
                actual_cost_usd = round(actual_cost * eth_usd, 2)

                if actual_cost > 0:
                    print(f"  ✅ Token #{token_id} claimed!")
                    print(f"  Actual gas: {actual_cost} ETH (~${actual_cost_usd})")
                    claimed_count += 1
                else:
                    print(f"  ⚠️  No ETH spent — transaction likely reverted for token #{token_id}")
                    skipped_count += 1

                print(f"  New balance: {balance_after} ETH (${round(eth_usd * balance_after, 2)})")
                print("  " + "─" * 60)

                time.sleep(how_many_seconds_between_checks)

            except Exception as e:
                print(f"  ❌ Error claiming token #{token_id}: {e}")
                traceback.print_exc()
                skipped_count += 1
                time.sleep(how_many_seconds_between_checks * 3)

        print(f"\n{get_timestamp()} - Batch done. Claimed: {claimed_count}  |  Skipped/Failed: {skipped_count}")
        print("─" * 70)

        consecutive_count = 0
        time.sleep(how_many_seconds_between_checks * 20)

    except Exception as e:
        print(f"{get_timestamp()} - ERROR in main loop: {e}")
        traceback.print_exc()
        consecutive_count = 0
        time.sleep(how_many_seconds_between_checks * 3)
