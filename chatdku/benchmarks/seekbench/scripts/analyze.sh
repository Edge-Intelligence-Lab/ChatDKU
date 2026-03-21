INPUTFILE=outputs/annotated_traces.jsonl


python analysis/grounded_reason.py --input $INPUTFILE --outdir outputs/groundness
python analysis/recovery.py $INPUTFILE outputs/recovery
python analysis/calibration.py --input $INPUTFILE --outdir outputs/calibration
