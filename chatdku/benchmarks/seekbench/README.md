# Evaluation: Seekbench

This project is based on the paper **Do LLM Agents Know How to Ground, Recover, and Assess? Evaluating Epistemic Competence in Information-Seeking Agents**. We have tried replicating the paper to adjust to ChatDKU scenario.

- You can find the original paper [here](https://openreview.net/forum?id=r0L9GwlnzP)
- You can find the github repo [here](https://github.com/SHAO-Jiaqi757/SeekBench/tree/main)

----

- [Evaluation: Seekbench](#evaluation-seekbench)
  - [Workflows](#workflows)
    - [A. Create Dataset](#a-create-dataset)
    - [B. Generate Traces](#b-generate-traces)
    - [C. Import Traces](#c-import-traces)
    - [D. Parse Traces](#d-parse-traces)
    - [E. Annotate Traces](#e-annotate-traces)
    - [F. Analyze Annotation](#f-analyze-annotation)
  - [Metadata](#metadata)
    - [Dataset](#dataset)
    - [Raw Traces (trace\_eval/import\_traces.py)](#raw-traces-trace_evalimport_tracespy)



## Workflows

>[!IMPORTANT]
> Make sure you are at the **root** i.e `chatdku/benchamrks/seekbench/`

### A. Create Dataset
You need to create the dataset to be evaluated on using your own corpus. This can be done by running.

**If you already have a dataset, you can skip this stage.** Dataset metadata can be found [here](#dataset) 

```bash
bash scripts/create_dataset.sh
```

> [!IMPORTANT]
Make sure to change the variables from the script.

### B. Generate Traces
Once the dataset is created, we can generate traces. ChatDKU uses its custom `Agent` for inference. Depending on other projects, the `agent` can be adjusted [here](trace_eval/generate_traces.py).

You can generate traces via

```bash
bash scripts/generate_traces.sh
```
### C. Import Traces
   
We are using OpenTelemetry and Arize Phoenix for telemetry. Based on this, we use the Phoenix API to import traces (future work can include bypassing the api layer and working directly with the agent.)

You can import traces via:

```bash
bash scripts/import_traces.sh
```

> [!Important]
> Make sure to setup `.env` using [.env.example](trace_eval/.env.example)

### D. Parse Traces
   
   This step is used to make the traces compatiable with `seekbench`. From this step, we will be following the seekbench pipeline. You can parse your traces via

   ```bash
    bash scripts/parse.sh
   ```

### E. Annotate Traces
   
This step involves attotating the traces using Judge LLM. You can proceed via

```bash
bash scripts/annotation.sh
```

> [!Important]
> Make sure to setup `.env` using [.env.example](annotation/.env.example)

### F. Analyze Annotation
You can analyze the annotations via

```bash
bash scripts/analyze.sh
```


## Metadata

### Dataset
Typical field includes:
- `question` : Questions in the dataset.
- `ground_truth` : Golden answer for the questions
- `max_iteration` : Max iteration required by the agent. If this field is missing, `default=5`

### Raw Traces ([trace_eval/import_traces.py](trace_eval/import_traces.py))
```bash
{

    'id': id_,
    'question': question,
    'sequences_str': parsed_trace,
    'ground_truth': ground_truth,
    'reward': score,
    'model': model,
    'dataset': "ChatDKU",
    'is_correct': score == 1.0
}
```



