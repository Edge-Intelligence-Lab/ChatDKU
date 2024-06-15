from llamaindex import SimpleDocumentStore, SimpleQueryEngine
from llamaindex.query.node_postprocessors import FilterNodePostprocessor

# Create a simple document store
doc_store = SimpleDocumentStore()

# Add some documents to the store
doc_store.add_documents([
    {"content": "Duke Kunshan University Student Handbook"},
    {"content": "Duke Kunshan University offers a variety of undergraduate and graduate programs."},
])

class UniversityFilterPostprocessor(FilterNodePostprocessor):
    def __init__(self, keyword):
        self.keyword = keyword

    def filter(self, node):
        return self.keyword.lower() in node["content"].lower()

# Instantiate the postprocessor
university_filter = UniversityFilterPostprocessor(keyword="Duke Kunshan University")

# Create a query engine
query_engine = SimpleQueryEngine(document_store=doc_store)

# Apply the postprocessor
query_engine.add_postprocessor(university_filter)

# Perform a query
result = query_engine.query("Find documents related to Duke Kunshan University")

# Output the result
print("Filtered Documents:")
for doc in result["documents"]:
    print(doc["content"])

