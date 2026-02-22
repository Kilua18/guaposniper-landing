#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# Setup script pour CryptoTrader IA sur Termux (Z Fold / Android)
# ============================================================
# Usage: bash setup_termux.sh
# ============================================================

set -e

echo "======================================"
echo " CryptoTrader IA - Setup Termux"
echo "======================================"
echo ""

# 1. Mise a jour de Termux
echo "[1/5] Mise a jour des paquets..."
pkg update -y && pkg upgrade -y

# 2. Installation des dependances systeme
echo "[2/5] Installation de Python et dependances..."
pkg install -y python python-pip git cmake ninja patchelf

# 3. Installer les bibliotheques de compilation pour ARM
echo "[3/5] Installation des bibliotheques de compilation..."
pkg install -y libopenblas libandroid-execinfo

# 4. Installation des paquets Python via pip
echo "[4/5] Installation des paquets Python (peut prendre quelques minutes)..."
# IMPORTANT: ne PAS faire "pip install --upgrade pip" sur Termux (casse le paquet)
pip install numpy pandas requests scikit-learn

# 5. Creation du dossier de donnees
echo "[5/5] Preparation..."
mkdir -p trader_data

echo ""
echo "======================================"
echo " Installation terminee !"
echo "======================================"
echo ""
echo " Pour lancer le bot:"
echo "   python crypto_trader.py"
echo ""
echo " Le bot demarre en mode PAPER TRADING"
echo " (simulation, pas d'argent reel)."
echo ""
echo " Appuyez sur Ctrl+C pour arreter."
echo "======================================"
