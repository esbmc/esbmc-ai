#!/usr/bin/env sh

echo "Removing dist"
if [ -d "dist" ]; then
    rm -r dist
fi
