#----CONFIG----
OUTPUTPATH=data/bulletin_qa.parquet
MAX_ITERATION=3
CORPUS_PATH=data/ug_bulletin_2025-2026.pdf

echo "Creating Dataset"
python trace_eval/create_dataset.py \
--corpus_path $CORPUS_PATH \
--output_path $OUTPUTPATH \
--max_iteration $MAX_ITERATION

