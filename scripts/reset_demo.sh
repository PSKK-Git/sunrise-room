#!/usr/bin/env bash
# Put the shop and the memory back to the start of the demo.
set -euo pipefail
cd "$(dirname "$0")/.."
cp shop/data.seed.json shop/data.json
rm -f memory.db
python3 -m scribe.seed
echo "demo reset: shop data restored, memory seeded"
