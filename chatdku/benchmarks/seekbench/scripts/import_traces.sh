FILEPATH="data/bulletin_qa.parquet"
OUTPUTPATH="outputs/raw_traces.jsonl"
MODEL="Qwen3-30B-A3B"
DATASET="ChatDKU_dataset"

echo "Importing Traces..."

python trace_eval/import_traces.py \
--file_path $FILEPATH \
--output_path $OUTPUTPATH \
--model $MODEL \
--dataset $DATASET


