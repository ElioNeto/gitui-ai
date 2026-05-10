#!/usr/bin/env bash
# GitUI-AI — Setup rápido (Pop!OS / Ubuntu / Debian)
set -e

echo "🌿 GitUI-AI — Setup"
echo "==================="

# Cria venv se não existir
if [ ! -d ".venv" ]; then
  echo "📦 Criando ambiente virtual..."
  python3 -m venv .venv
fi

# Instala dependências
echo "⬇  Instalando dependências..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# Cria .env se não existir
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  Configure sua API key gratuita em .env:"
  echo "   GROQ_API_KEY=gsk_...   → console.groq.com"
  echo "   GEMINI_API_KEY=AIza... → aistudio.google.com"
fi

# Cria launcher
cat > gitui << 'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/.venv/bin/python" "$DIR/main.py" "${1:-$PWD}"
EOF
chmod +x gitui

echo ""
echo "✅ Pronto! Para rodar:"
echo "   ./gitui                  # repositório atual"
echo "   ./gitui /outro/repo      # outro repositório"
echo ""
echo "💡 Dica — alias global:"
echo "   echo \"alias gitui=\$(pwd)/gitui\" >> ~/.bashrc && source ~/.bashrc"
