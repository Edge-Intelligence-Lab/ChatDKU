echo "Annotating files...."

INPUTFILE=outputs/parsed_traces.jsonl
OUTPUTFILE=outputs/annotated_traces.jsonl 
ONTOLOGYFILE=annotation/ontology.json
MODEL=Qwen3.5-35B-A3B
CONCURRENCY=30


python annotation/main.py \
--input_file $INPUTFILE \
--output_file $OUTPUTFILE \
--ontology_file $ONTOLOGYFILE \
--model $MODEL \
--concurrency $CONCURRENCY