#----CONFIG----
CONCURRENCY=30
MAX_ITERATION=3
OUTPUT_PATH="data/chatdku_dataset.parquet"
NUM_SAMPLES=60
MODEL="gpt-4.1-mini"

echo "Creating Dataset"

python trace_eval/create_dataset.py --concurrency $CONCURRENCY --output_path  $OUTPUT_PATH --num_samples $NUM_SAMPLES --model $MODEL
