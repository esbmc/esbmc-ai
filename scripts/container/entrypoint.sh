#!/bin/bash
# Container entrypoint for ESBMC-AI
# Reads ESBMCAI_CONFIG_FILE (if set) and dynamically injects [extras.packages] via pipx
# Then executes the provided command

# If config file is set and exists, parse it for extra packages
if [ -n "$ESBMCAI_CONFIG_FILE" ] && [ -f "$ESBMCAI_CONFIG_FILE" ]; then
    # Extract extra packages from config.toml [extras.packages]
    EXTRAS=$(python3 -c "
import tomllib
with open('$ESBMCAI_CONFIG_FILE', 'rb') as f:
    config = tomllib.load(f)
print(' '.join(config.get('extras', {}).get('packages', [])))
" 2>/dev/null)

    # Inject extra packages if found (pipx inject is idempotent)
    if [ -n "$EXTRAS" ]; then
        echo "Injecting extra packages: $EXTRAS"
        pipx inject esbmc-ai $EXTRAS
    fi
fi

# Execute the user's command
exec "$@"