# CONFIGS
FILE_PATH=data/chatdku_dataset.parquet

echo "Generating Traces..."

python trace_eval/generate_traces.py \
--file_path $FILE_PATH