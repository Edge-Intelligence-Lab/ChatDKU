```bash
git submodule update --init --recursive
CUDA_VISIBLE_DEVICES=0 CMAKE_ARGS="-DLLAMA_CUDA=on" FORCE_CMAKE=1 pip install -e .
```
