#!/bin/bash
# ============================================
# GuapoTrader - Installation Raspberry Pi
# ============================================

set -e

echo "╔══════════════════════════════════════╗"
echo "║   INSTALLATION GUAPO TRADER          ║"
echo "║   Raspberry Pi Setup                 ║"
echo "╚══════════════════════════════════════╝"

INSTALL_DIR="$HOME/guapo-trader"
VENV_DIR="$INSTALL_DIR/venv"

# 1. Mise à jour système
echo ""
echo "[1/6] Mise à jour du système..."
sudo apt update && sudo apt upgrade -y

# 2. Dépendances système
echo ""
echo "[2/6] Installation des dépendances système..."
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    libatlas-base-dev libffi-dev libssl-dev git

# 3. Environnement virtuel Python
echo ""
echo "[3/6] Création de l'environnement virtuel..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# 4. Installation des packages Python
echo ""
echo "[4/6] Installation des packages Python..."
pip install --upgrade pip setuptools wheel
pip install -r "$INSTALL_DIR/requirements.txt"

# 5. Configuration
echo ""
echo "[5/6] Configuration..."
mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/logs"

if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
    cp "$INSTALL_DIR/config.example.yaml" "$INSTALL_DIR/config.yaml"
    echo "   config.yaml créé - REMPLIS TES CLÉS API !"
    echo "   nano $INSTALL_DIR/config.yaml"
else
    echo "   config.yaml existe déjà"
fi

# 6. Service systemd
echo ""
echo "[6/6] Installation du service systemd..."
SERVICE_FILE="/etc/systemd/system/guapo-trader.service"
sudo cp "$INSTALL_DIR/systemd/guapo-trader.service" "$SERVICE_FILE"
sudo sed -i "s|/home/pi/guapo-trader|$INSTALL_DIR|g" "$SERVICE_FILE"
sudo sed -i "s|User=pi|User=$USER|g" "$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable guapo-trader

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   INSTALLATION TERMINÉE !            ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Prochaines étapes:"
echo "  1. Configure tes clés API:"
echo "     nano $INSTALL_DIR/config.yaml"
echo ""
echo "  2. Test du bot (mode manuel):"
echo "     cd $INSTALL_DIR"
echo "     source venv/bin/activate"
echo "     python -m guapo_trader.main"
echo ""
echo "  3. Lancer en service (24/7):"
echo "     sudo systemctl start guapo-trader"
echo "     sudo systemctl status guapo-trader"
echo ""
echo "  4. Voir les logs:"
echo "     journalctl -u guapo-trader -f"
echo "     cat $INSTALL_DIR/logs/guapo-trader.log"
echo ""
