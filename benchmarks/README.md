# Benchmarks

## Backend Benchmark With k6

First, acquire the `question.json` dataset from the Box folder `ChatDKU Materials/Datasets`.
Then place it in the `ChatDKU/benchmarks` folder.

Install k6 according to [the documentation](https://grafana.com/docs/k6/latest/set-up/install-k6/).

Run the benchmark with
```bash
k6 run --vus [# of virtual users] --duration [benchmark duration, e.g. 600s] -e PORT=[backend port] backend.js
```
Note that during the execution of `backend.js`, [k6-reporter](https://github.com/benc-uk/k6-reporter) will be loaded from GitHub, which might require proxy to access.

The benchmark report will be saved to `summary.html`.

## Visualization of vLLM benchmark data

```bash
python visualize_vllm.py path-to-vllm-benchmarks-output-folder
```
