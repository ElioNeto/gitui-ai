# GitUI-AI 🌿

TUI (Terminal User Interface) para Git com integração de IA para geração automática de mensagens de commit baseadas em diffs e contexto do projeto.

## Instalação

```bash
pip install textual gitpython httpx python-dotenv
```

## Configuração da IA (escolha uma opção gratuita)

Crie um arquivo `.env` na raiz do seu projeto Git:

### ✅ Opção 1 — Groq (GRATUITO, recomendado)

Modelo **Llama 3.3 70B**, ultrarrápido, sem cartão de crédito.

1. Acesse [console.groq.com](https://console.groq.com)
2. Crie uma conta (pode usar Gmail ou GitHub)
3. Vá em **API Keys → Create API Key**
4. Cole no `.env`:

```env
GROQ_API_KEY=gsk_...
```

### ✅ Opção 2 — Google Gemini (GRATUITO, 1.500 req/dia)

Modelo **Gemini 2.0 Flash**, sem cartão de crédito.

1. Acesse [aistudio.google.com](https://aistudio.google.com)
2. Faça login com sua conta Google
3. Clique em **Get API Key → Create API Key**
4. Cole no `.env`:

```env
GEMINI_API_KEY=AIza...
```

### Opções pagas (opcional)

```env
OPENAI_API_KEY=sk-...          # GPT-4o-mini
ANTHROPIC_API_KEY=sk-ant-...   # Claude Haiku
```

> **Prioridade:** Groq → Gemini → OpenAI → Anthropic

## Como usar

```bash
# No diretório do projeto
python main.py

# Ou apontando para outro diretório
python main.py /caminho/do/repo
```

## Atalhos de Teclado

| Tecla | Ação |
|-------|------|
| `q` | Sair |
| `r` / `F5` | Refresh geral |
| `c` | Foco na aba Commit |
| `a` | Stage all (`git add -A`) |
| `s` | Gerar mensagem com IA |
| `p` | Push para origin |
| `u` | Pull de origin |
| `b` | Criar nova branch |
| `?` | Mostrar ajuda |

## Interface

```
┌───────────────────────────────────────────────────────────────────┐
│  GitUI-AI                          branch: main       [relógio] │
├──────────┬─────────────────────────────────────┬────────────────┤
│ 📁 REPO  │  📝 Staging │ 💬 Commit │ 📜 Log │ 🔍 Diff         │
│ nome     │                                     │ ⚡ AÇÕES       │
│ branch   │  UNSTAGED                           │ ⬆ Push         │
│          │  M arquivo.py                       │ ⬇ Pull         │
│ 🌿 BRANC │  ? novo.txt                         │ 🔀 Fetch       │
│ → main   │  [+ Stage All] [- Unstage All]      │ 🌿 Nova Branch │
│  feature │                                     │ 🔗 Add Remote  │
│          │  STAGED                             │ 📦 Stash       │
│ 🔗 REMOT │  A outro.py                         │               │
│ origin   │                                     │ 📊 STATUS      │
└──────────┴─────────────────────────────────────┴────────────────┘
```

## Como a IA funciona

1. Pressione `a` (Stage All) ou use o botão
2. Pressione `s` ou clique em **✨ Sugestão IA**
3. A IA lê o **diff staged** + contexto do projeto (README, package.json...)
4. Gera uma mensagem no padrão **Conventional Commits** (`feat:`, `fix:`...)
5. A mensagem aparece no editor — revise e edite à vontade
6. Clique em **✔ Commit** para confirmar
