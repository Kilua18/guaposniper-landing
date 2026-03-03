import asyncio
import base64
import struct

import httpx
from loguru import logger

# Adresses connues sur Solana
WSOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
RAYDIUM_AMM_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"


class SolanaClient:
    """Client Solana pour le trading DEX (Jupiter aggregator)."""

    def __init__(self, rpc_url: str, private_key: str = "", slippage_bps: int = 100):
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.slippage_bps = slippage_bps
        self._http = httpx.AsyncClient(timeout=30)
        self._jupiter_url = "https://quote-api.jup.ag/v6"
        self._connected = False

    async def connect(self):
        """Vérifie la connexion au RPC Solana."""
        try:
            resp = await self._rpc_call("getHealth")
            if resp.get("result") == "ok":
                self._connected = True
                logger.info("Solana RPC connecté")

                if self.private_key:
                    sol_balance = await self.get_sol_balance()
                    logger.info(f"Solde SOL: {sol_balance:.4f}")
                else:
                    logger.warning("Pas de clé privée Solana - mode lecture seule")
                return True
        except Exception as e:
            logger.error(f"Erreur connexion Solana: {e}")
        return False

    async def close(self):
        await self._http.aclose()

    async def _rpc_call(self, method: str, params: list = None) -> dict:
        """Appel JSON-RPC au noeud Solana."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }
        resp = await self._http.post(self.rpc_url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_sol_balance(self) -> float:
        """Retourne le solde SOL du wallet."""
        if not self.private_key:
            return 0.0
        try:
            from solders.keypair import Keypair
            kp = Keypair.from_base58_string(self.private_key)
            pubkey = str(kp.pubkey())
            resp = await self._rpc_call("getBalance", [pubkey])
            lamports = resp.get("result", {}).get("value", 0)
            return lamports / 1_000_000_000
        except ImportError:
            logger.warning("solders non installé - impossible de lire le solde SOL")
            return 0.0

    async def get_token_balance(self, token_mint: str) -> float:
        """Retourne le solde d'un token SPL."""
        if not self.private_key:
            return 0.0
        try:
            from solders.keypair import Keypair
            kp = Keypair.from_base58_string(self.private_key)
            pubkey = str(kp.pubkey())

            resp = await self._rpc_call("getTokenAccountsByOwner", [
                pubkey,
                {"mint": token_mint},
                {"encoding": "jsonParsed"},
            ])
            accounts = resp.get("result", {}).get("value", [])
            if not accounts:
                return 0.0

            info = accounts[0]["account"]["data"]["parsed"]["info"]
            return float(info["tokenAmount"]["uiAmount"])
        except Exception as e:
            logger.error(f"Erreur solde token {token_mint}: {e}")
            return 0.0

    async def get_token_price(self, token_mint: str) -> float | None:
        """Récupère le prix d'un token via Jupiter."""
        try:
            resp = await self._http.get(
                f"{self._jupiter_url}/quote",
                params={
                    "inputMint": token_mint,
                    "outputMint": USDC_MINT,
                    "amount": str(1_000_000),  # 1 token (6 decimals)
                    "slippageBps": 50,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                out_amount = int(data.get("outAmount", 0))
                return out_amount / 1_000_000  # USDC has 6 decimals
        except Exception as e:
            logger.error(f"Erreur prix token {token_mint}: {e}")
        return None

    async def swap_jupiter(self, input_mint: str, output_mint: str,
                           amount_lamports: int) -> dict | None:
        """Exécute un swap via Jupiter aggregator."""
        if not self.private_key:
            logger.error("Clé privée requise pour le swap")
            return None

        try:
            from solders.keypair import Keypair
            from solders.transaction import VersionedTransaction
            kp = Keypair.from_base58_string(self.private_key)
            pubkey = str(kp.pubkey())

            # 1. Obtenir la quote
            quote_resp = await self._http.get(
                f"{self._jupiter_url}/quote",
                params={
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": str(amount_lamports),
                    "slippageBps": self.slippage_bps,
                },
            )
            quote_resp.raise_for_status()
            quote = quote_resp.json()

            in_amount = int(quote["inAmount"])
            out_amount = int(quote["outAmount"])
            logger.info(
                f"Jupiter quote: {in_amount} {input_mint[:8]}... -> "
                f"{out_amount} {output_mint[:8]}..."
            )

            # 2. Obtenir la transaction de swap
            swap_resp = await self._http.post(
                f"{self._jupiter_url}/swap",
                json={
                    "quoteResponse": quote,
                    "userPublicKey": pubkey,
                    "wrapAndUnwrapSol": True,
                },
            )
            swap_resp.raise_for_status()
            swap_data = swap_resp.json()

            # 3. Signer et envoyer
            raw_tx = base64.b64decode(swap_data["swapTransaction"])
            tx = VersionedTransaction.from_bytes(raw_tx)
            signed_tx = VersionedTransaction(tx.message, [kp])

            tx_bytes = bytes(signed_tx)
            tx_b64 = base64.b64encode(tx_bytes).decode()

            send_resp = await self._rpc_call("sendTransaction", [
                tx_b64,
                {"encoding": "base64", "skipPreflight": False},
            ])

            tx_sig = send_resp.get("result")
            if tx_sig:
                logger.info(f"Swap exécuté ! TX: {tx_sig}")
                return {
                    "signature": tx_sig,
                    "input_mint": input_mint,
                    "output_mint": output_mint,
                    "in_amount": in_amount,
                    "out_amount": out_amount,
                }
            else:
                error = send_resp.get("error", "Erreur inconnue")
                logger.error(f"Échec swap: {error}")
                return None

        except ImportError:
            logger.error("solders non installé - pip install solders")
            return None
        except Exception as e:
            logger.error(f"Erreur swap Jupiter: {e}")
            return None

    async def buy_token(self, token_mint: str, sol_amount: float) -> dict | None:
        """Achète un token avec du SOL."""
        lamports = int(sol_amount * 1_000_000_000)
        return await self.swap_jupiter(WSOL_MINT, token_mint, lamports)

    async def sell_token(self, token_mint: str, token_amount: int) -> dict | None:
        """Vend un token contre du SOL."""
        return await self.swap_jupiter(token_mint, WSOL_MINT, token_amount)
