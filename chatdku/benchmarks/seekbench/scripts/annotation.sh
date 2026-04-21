echo "Annotating files...."

INPUTFILE=outputs/parsed_traces.jsonl
OUTPUTFILE=outputs/annotated_traces.jsonl 
ONTOLOGYFILE=annotation/ontology.json
MODEL=gpt-4.1-nano
CONCURRENCY=30
AGENT_MODEL=Qwen3-30B-A3B-Instruct-2507

python annotation/main.py \
--input_file $INPUTFILE \
--output_file $OUTPUTFILE \
--ontology_file $ONTOLOGYFILE \
--model $MODEL \
--agent_model $AGENT_MODEL \
--concurrency $CONCURRENCY