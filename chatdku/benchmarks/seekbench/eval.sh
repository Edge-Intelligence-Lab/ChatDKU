#!/bin/bash
set -e

bash scripts/create_dataset.sh
bash scripts/generate_traces.sh
bash scripts/import_traces.sh
bash scripts/parser.sh
bash scripts/annotation.sh
bash scripts/analyze.sh
