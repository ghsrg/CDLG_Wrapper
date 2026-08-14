#!/usr/bin/env sh
set -eu
cd "$2"
"$1" generate_collection_of_logs.py
