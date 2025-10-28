#!/bin/bash
# Container entrypoint for ESBMC-AI
# Reads ESBMCAI_CONFIG_FILE (if set) and dynamically injects [extras.packages] via pipx
# Then executes the provided command (default: esbmc-ai)

# If config file is set and exists, parse it for extras
if [ -n "$ESBMCAI_CONFIG_FILE" ] && [ -f "$ESBMCAI_CONFIG_FILE" ]; then
    # Extract extra packages from config.toml (assume structure: [extras] packages = ["pkg1", "pkg2"])
    EXTRAS=$(python3 -c "
import tomllib
with open('$ESBMCAI_CONFIG_FILE', 'rb') as f:
    config = tomllib.load(f)
print(' '.join(config.get('extras', {}).get('packages', [])))
" 2>/dev/null)

    # If extras found, inject them (pipx inject is idempotent; won't reinstall if already present)
    if [ -n "$EXTRAS" ]; then
        echo "Injecting extra packages: $EXTRAS"
        pipx inject esbmc-ai $EXTRAS
    fi
fi

# Execute the user's command (e.g., bash or esbmc-ai)
exec "$@"