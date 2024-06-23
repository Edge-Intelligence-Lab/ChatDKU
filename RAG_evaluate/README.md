## RAG Evaluate 

### 1. Preprocess documents
preprocess_documents.py:
- load documents from documents.pkl
- Filtering documents
- Store the filtered documents as json

### 2. Generate data with GPT
gen_data_from_gpt.py

### 3. Use our RAG system generate our answer for generated questions
DKU_LLM/RAG/get_answer.py

suggest use nohup: `nohup python3 -u get_answer.py > get_answer_log.txt &`

### 4. Use RAGAS to Evaluate
ragas_evaluate.py