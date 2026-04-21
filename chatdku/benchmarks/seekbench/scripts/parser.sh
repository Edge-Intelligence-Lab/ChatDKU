
echo "Parsing traces..."

python annotation/parser.py outputs/raw_traces.jsonl -o outputs/parsed_traces.jsonl
