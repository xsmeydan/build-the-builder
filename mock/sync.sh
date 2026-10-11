#!/bin/zsh
# Copy the latest test data from the case folder, deploy the Worker, check every answer.
cd "$(dirname "$0")"
cp "../final/Build the Builder - Final Case/test-environment/test-customers.json" data/test-customers.json
npx --yes wrangler deploy 2>&1 | grep -E "Uploaded|rror"
sleep 10; python3 check_mock.py | tail -3
