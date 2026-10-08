#!/bin/bash
# Starts Ollama for a fully local KIS and fetches the models KIS is tested with.
#
#   ./start-ollama.sh            start Ollama and pull the models
#   OLLAMA_BIN=/path/ollama ./start-ollama.sh   use a specific Ollama binary
#
# Ollama listens on all interfaces, otherwise the Docker containers cannot reach it.
# That also makes it reachable from your network, so keep the firewall on.

set -e

BIN="${OLLAMA_BIN:-}"
if [ -z "$BIN" ]; then
    for kandidat in /Applications/Ollama.app/Contents/Resources/ollama "$(command -v ollama)"; do
        if [ -n "$kandidat" ] && [ -x "$kandidat" ]; then BIN="$kandidat"; break; fi
    done
fi
if [ -z "$BIN" ]; then
    echo "Ollama not found. Install it from https://ollama.com/download"
    exit 1
fi

# The Homebrew build ships without structured output, KIS needs it for its JSON answers.
case "$(readlink -f "$BIN" 2>/dev/null || echo "$BIN")" in
    *Cellar*|*homebrew*)
        echo "Warning: $BIN is the Homebrew build, it lacks structured output."
        echo "Use the Ollama download from ollama.com or set OLLAMA_BIN."
        ;;
esac

if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    CHAT_MODEL="gemma4:31b-mlx"
else
    CHAT_MODEL="gemma4:31b"
fi
EMBED_MODEL="qwen3-embedding:4b"

if curl -s -o /dev/null http://127.0.0.1:11434/; then
    echo "Ollama is already running. Stop it first if it was not started by this script,"
    echo "it has to listen on 0.0.0.0 for the containers."
else
    echo "Note: Ollama has no login and now answers on every network interface."
    echo "Use it only on a trusted network with the firewall on."
    mkdir -p "$HOME/.ollama"
    # 32k context is what KIS was measured with, a longer keep alive spares reloading the model.
    OLLAMA_HOST=0.0.0.0:11434 OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_FLASH_ATTENTION=1 \
        OLLAMA_KEEP_ALIVE=30m nohup "$BIN" serve > "$HOME/.ollama/kis-serve.log" 2>&1 &
    for _ in $(seq 1 30); do
        curl -s -o /dev/null http://127.0.0.1:11434/ && break
        sleep 1
    done
fi

"$BIN" pull "$CHAT_MODEL"
"$BIN" pull "$EMBED_MODEL"

cat <<EOF

Ollama is ready. In KIS under Admin → AI:
  1. Add a provider with base URL http://host.docker.internal:11434/v1, no API key.
  2. Route chat and both translations to $CHAT_MODEL, embedding to $EMBED_MODEL.
KIS reads the context window from Ollama itself.
EOF
