#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NOCTA_HOME="$HOME/.nocta"
VERSION="0.1.0"
REPO="https://raw.githubusercontent.com/nossa-y/nocta/main"

echo ""
echo "${BLUE}╔══════════════════════════════════╗${NC}"
echo "${BLUE}║     Installing Nocta v${VERSION}      ║${NC}"
echo "${BLUE}║   Your AI agents get eyes.       ║${NC}"
echo "${BLUE}╚══════════════════════════════════╝${NC}"
echo ""

# ── Check OS ──
OS=$(uname -s)
if [ "$OS" != "Darwin" ]; then
    echo "${RED}Error: macOS only for now.${NC}"
    exit 1
fi
echo "${GREEN}✓${NC} macOS $(uname -m) detected"

# ── Check Python ──
PYTHON=""
for p in python3 /usr/bin/python3 /opt/homebrew/bin/python3; do
    if command -v "$p" &>/dev/null; then
        PY_VER=$("$p" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$PY_MAJOR" -ge 3 ] 2>/dev/null && [ "$PY_MINOR" -ge 9 ] 2>/dev/null; then
            PYTHON="$p"
            break
        fi
    fi
done
if [ -z "$PYTHON" ]; then
    echo "${RED}Error: Python 3.9+ required. Install with: brew install python@3.12${NC}"
    exit 1
fi
echo "${GREEN}✓${NC} Python: $PYTHON ($PY_VER)"

# ── Install screen recorder if missing ──
if ! command -v screenpipe &>/dev/null; then
    echo "  Installing screen recorder..."
    if command -v npm &>/dev/null; then
        npm install -g screenpipe >/dev/null 2>&1
    elif command -v brew &>/dev/null; then
        brew install node >/dev/null 2>&1 && npm install -g screenpipe >/dev/null 2>&1
    else
        echo "${RED}Error: npm or brew required. Install Node.js from https://nodejs.org${NC}"
        exit 1
    fi
    echo "${GREEN}✓${NC} Screen recorder installed"
else
    echo "${GREEN}✓${NC} Screen recorder found"
fi

# ── Create directories ──
mkdir -p "$NOCTA_HOME"/{bin,lib,logs,cache,integrations}

# ── Download files ──
echo "  Downloading Nocta..."
curl -fsSL "$REPO/daemon.py" -o "$NOCTA_HOME/lib/daemon.py"
curl -fsSL "$REPO/nocta-cli" -o "$NOCTA_HOME/bin/nocta"
curl -fsSL "$REPO/hermes-skill.md" -o "$NOCTA_HOME/integrations/hermes-skill.md"
curl -fsSL "$REPO/CLAUDE.md" -o "$NOCTA_HOME/integrations/CLAUDE.md"
chmod +x "$NOCTA_HOME/bin/nocta"
echo "${GREEN}✓${NC} Downloaded"

# ── Add to PATH ──
SHELL_RC=""
case "$(basename "$SHELL")" in
    zsh)  SHELL_RC="$HOME/.zshrc" ;;
    bash) SHELL_RC="$HOME/.bashrc" ;;
esac
if [ -n "$SHELL_RC" ] && ! grep -q ".nocta/bin" "$SHELL_RC" 2>/dev/null; then
    echo '' >> "$SHELL_RC"
    echo '# Nocta' >> "$SHELL_RC"
    echo 'export PATH="$HOME/.nocta/bin:$PATH"' >> "$SHELL_RC"
fi
export PATH="$NOCTA_HOME/bin:$PATH"
echo "${GREEN}✓${NC} Added to PATH"

# ── Screen recording permission ──
echo ""
echo "${YELLOW}⚠ Screen recording permission needed${NC}"
echo "  Opening System Settings..."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture" 2>/dev/null || true
echo ""
echo "  ${BLUE}→ Toggle ON for Terminal (or your terminal app)${NC}"
echo "  ${BLUE}→ Press Enter when done${NC}"
read -r
echo "${GREEN}✓${NC} Permission configured"

# ── Install LaunchAgent + start ──
"$NOCTA_HOME/bin/nocta" install
"$NOCTA_HOME/bin/nocta" start

# ── Auto-detect and configure agents ──
echo ""
if command -v claude &>/dev/null; then
    # Add global CLAUDE.md context instruction
    mkdir -p "$HOME/.claude"
    if [ -f "$HOME/.claude/CLAUDE.md" ]; then
        if ! grep -q "Nocta" "$HOME/.claude/CLAUDE.md" 2>/dev/null; then
            echo "" >> "$HOME/.claude/CLAUDE.md"
            cat "$NOCTA_HOME/integrations/CLAUDE.md" >> "$HOME/.claude/CLAUDE.md"
        fi
    else
        cp "$NOCTA_HOME/integrations/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
    fi
    echo "${GREEN}✓${NC} Claude Code configured"
fi

if [ -d "$HOME/.hermes/skills" ]; then
    mkdir -p "$HOME/.hermes/skills/nocta-context"
    cp "$NOCTA_HOME/integrations/hermes-skill.md" "$HOME/.hermes/skills/nocta-context/SKILL.md"
    echo "${GREEN}✓${NC} Hermes configured"
fi

echo ""
echo "${GREEN}╔══════════════════════════════════╗${NC}"
echo "${GREEN}║        Nocta installed! 🎉       ║${NC}"
echo "${GREEN}╚══════════════════════════════════╝${NC}"
echo ""
echo "  Context API: ${BLUE}http://127.0.0.1:7676/context${NC}"
echo ""
echo "  Commands:"
echo "    nocta status    Show what Nocta sees"
echo "    nocta context   View current context"
echo "    nocta logs      View logs"
echo "    nocta stop      Stop the service"
echo ""
echo "  Your AI agents now have eyes."
echo ""
