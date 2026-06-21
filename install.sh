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

MACOS_VER=$(sw_vers -productVersion)
MACOS_MAJOR=$(echo "$MACOS_VER" | cut -d. -f1)
MACOS_MINOR=$(echo "$MACOS_VER" | cut -d. -f2)
MACOS_PATCH=$(echo "$MACOS_VER" | cut -d. -f3)

echo "${GREEN}✓${NC} macOS $(uname -m) — $MACOS_VER detected"

# Warn about Ventura SCKit issues
if [ "$MACOS_MAJOR" -eq 13 ]; then
    if [ -n "$MACOS_PATCH" ] && [ "$MACOS_PATCH" -lt 8 ] 2>/dev/null; then
        echo "${YELLOW}⚠ macOS Ventura $MACOS_VER has a known ScreenCaptureKit bug.${NC}"
        echo "  Update to 13.7.8+: Software Update → Upgrade Now"
    else
        echo "${YELLOW}⚠ macOS Ventura 13.x note: screenpipe binaries target macOS 15.5 SDK.${NC}"
        echo "  Screen capture may not work. See TROUBLESHOOTING.md if recording fails."
    fi
fi

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

# ── Install agent-browser if missing ──
if ! command -v agent-browser &>/dev/null; then
    echo "  Installing agent-browser..."
    npm install -g agent-browser >/dev/null 2>&1
    echo "${GREEN}✓${NC} agent-browser installed"
else
    echo "${GREEN}✓${NC} agent-browser found"
fi

# ── Create directories ──
mkdir -p "$NOCTA_HOME"/{bin,lib,logs,cache,integrations,docs/screenpipe-use,actions}

# ── Download files ──
echo "  Downloading Nocta..."
curl -fsSL "$REPO/daemon.py" -o "$NOCTA_HOME/lib/daemon.py"
curl -fsSL "$REPO/nocta-cli" -o "$NOCTA_HOME/bin/nocta"
curl -fsSL "$REPO/cookie-import.py" -o "$NOCTA_HOME/bin/cookie-import.py"
curl -fsSL "$REPO/hermes-skill.md" -o "$NOCTA_HOME/integrations/hermes-skill.md"
curl -fsSL "$REPO/CLAUDE.md" -o "$NOCTA_HOME/integrations/CLAUDE.md"
curl -fsSL "$REPO/opencode.md" -o "$NOCTA_HOME/integrations/opencode.md"
curl -fsSL "$REPO/AGENTS.md" -o "$NOCTA_HOME/integrations/AGENTS.md"
chmod +x "$NOCTA_HOME/bin/nocta"
echo "${GREEN}✓${NC} Downloaded"

# ── Deploy skills to Claude Code ──
if command -v claude &>/dev/null; then
    echo "  Deploying skills..."
    for skill in screenpipe-research nocta-execute; do
        mkdir -p "$HOME/.claude/skills/$skill"
        curl -fsSL "$REPO/skills/$skill/SKILL.md" -o "$HOME/.claude/skills/$skill/SKILL.md"
    done
    echo "${GREEN}✓${NC} Skills deployed to ~/.claude/skills/"
fi

# ── Deploy docs and action patterns ──
echo "  Downloading docs and actions..."
for doc in inference-strategy cast-wide-then-narrow intent-signals linkedin-message-detection ocr-and-ui-events; do
    curl -fsSL "$REPO/docs/screenpipe-use/$doc.md" -o "$NOCTA_HOME/docs/screenpipe-use/$doc.md" 2>/dev/null || true
done
# Download action patterns (list from repo)
for action in browser-real-chrome-profile gmail-send-email linkedin-connect-profile linkedin-send-message linkedin-withdraw-invitations; do
    curl -fsSL "$REPO/actions/$action.md" -o "$NOCTA_HOME/actions/$action.md" 2>/dev/null || true
done
echo "${GREEN}✓${NC} Docs and actions deployed"

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
echo "  ${BLUE}→ Find your terminal app (Terminal, iTerm2, Warp, etc.)${NC}"
echo "  ${BLUE}→ Toggle it ON${NC}"
echo "  ${BLUE}→ You may need to restart your terminal after granting${NC}"
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

# OpenCode — needs opencode.md in each project root (no global config)
# Create a git template so new repos get it automatically, and offer a command for existing repos
if command -v opencode &>/dev/null; then
    # Set up git template directory so every new repo gets opencode.md
    GIT_TEMPLATE_DIR="$HOME/.git-templates/hooks"
    mkdir -p "$GIT_TEMPLATE_DIR"
    mkdir -p "$HOME/.git-templates"
    
    # Create a post-checkout hook that symlinks opencode.md
    cat > "$HOME/.git-templates/hooks/post-checkout" << 'HOOK'
#!/bin/bash
# Nocta: auto-link context file for OpenCode
NOCTA_CONTEXT="$HOME/.nocta/integrations/opencode.md"
if [ -f "$NOCTA_CONTEXT" ] && [ ! -f "./opencode.md" ]; then
    ln -sf "$NOCTA_CONTEXT" ./opencode.md 2>/dev/null
fi
HOOK
    chmod +x "$HOME/.git-templates/hooks/post-checkout"
    git config --global init.templateDir "$HOME/.git-templates"
    
    # For existing repos: add a `nocta link` command and link the current dir
    echo "${GREEN}✓${NC} OpenCode configured (new repos get context automatically)"
    echo "    For existing repos, run: nocta link"
fi

# Codex — uses AGENTS.md globally at ~/.codex/AGENTS.md
if command -v codex &>/dev/null; then
    mkdir -p "$HOME/.codex"
    if [ -f "$HOME/.codex/AGENTS.md" ]; then
        if ! grep -q "Nocta" "$HOME/.codex/AGENTS.md" 2>/dev/null; then
            echo "" >> "$HOME/.codex/AGENTS.md"
            cat "$NOCTA_HOME/integrations/AGENTS.md" >> "$HOME/.codex/AGENTS.md"
        fi
    else
        cp "$NOCTA_HOME/integrations/AGENTS.md" "$HOME/.codex/AGENTS.md"
    fi
    echo "${GREEN}✓${NC} Codex configured"
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
