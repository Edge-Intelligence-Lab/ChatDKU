# auto_retrieval.py

import logging
import sys
import os
import getpass
import chromadb
from llama_index import TextNode, AutoRetriever

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

# Set up OpenAI
os.environ["OPENAI_API_KEY"] = getpass.getpass("OpenAI API Key:")
import openai
openai.api_key = os.environ["OPENAI_API_KEY"]

# Initialize Chroma vector database
chroma_client = chromadb.EphemeralClient()
chroma_collection = chroma_client.create_collection("duke_kunshan")

# Define sample data
nodes = [
    TextNode(text="Duke Kunshan University (DKU) is a Sino-American partnership of Duke University and Wuhan University to create a world-class liberal arts and research university offering a range of academic programs.", metadata={"category": "University", "location": "China"}),
    TextNode(text="DKU's campus is located in Kunshan, Jiangsu province, near Shanghai, blending American liberal arts education with Chinese tradition.", metadata={"category": "University", "location": "Kunshan"}),
    TextNode(text="DKU offers undergraduate, graduate, and professional degree programs, with a focus on interdisciplinary education and research.", metadata={"category": "Programs", "focus": "Interdisciplinary"}),
    TextNode(text="The university emphasizes global learning, with students and faculty from around the world, fostering a diverse and inclusive environment.", metadata={"category": "Diversity", "focus": "Global Learning"}),
    TextNode(text="DKU's research initiatives cover a wide range of fields, including environmental science, global health, data science, and more.", metadata={"category": "Research", "fields": "Various"})
]

# Insert nodes into the Chroma vector database
for node in nodes:
    chroma_collection.insert(node)

# Define the auto-retrieval function
def auto_retrieval(query):
    # Initialize the auto retriever
    retriever = AutoRetriever(vector_store=chroma_collection)
    
    # Perform retrieval
    results = retriever.retrieve(query)
    
    # Print the results
    for result in results:
        print(f"Text: {result.text}")
        print(f"Metadata: {result.metadata}")
        print("-" * 50)

if __name__ == "__main__":
    query = "Find documents related to interdisciplinary programs at Duke Kunshan University"
    auto_retrieval(query)
