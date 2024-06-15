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
    TextNode(text="DKU's research initiatives cover a wide range of fields, including environmental science, global health, data science, and more.", metadata={"category": "Research", "fields": "Various"}),
    TextNode(text="DKU's strategic location in Kunshan offers students opportunities to engage with China's rapidly growing economy and cultural heritage.", metadata={"category": "Location Benefits", "benefits": ["Economic Opportunities", "Cultural Engagement"]}),
    TextNode(text="The university promotes experiential learning through internships, fieldwork, and community service, enhancing students' practical skills and global perspectives.", metadata={"category": "Experiential Learning", "methods": ["Internships", "Fieldwork", "Community Service"]}),
    TextNode(text="DKU collaborates with leading corporations, research institutions, and government entities to advance knowledge and innovation in key sectors.", metadata={"category": "Partnerships", "collaborators": ["Corporations", "Research Institutions", "Government Entities"]}),
    TextNode(text="DKU's commitment to sustainability is reflected in its campus practices and research efforts aimed at addressing global environmental challenges.", metadata={"category": "Sustainability", "initiatives": ["Campus Practices", "Environmental Research"]}),
    TextNode(text="The university supports entrepreneurship and innovation through dedicated programs that encourage students and faculty to develop new ventures and solutions.", metadata={"category": "Entrepreneurship", "programs": ["Startup Incubators", "Innovation Challenges"]}),
    TextNode(text="DKU offers robust support services for international students, including language programs, cultural integration activities, and visa assistance.", metadata={"category": "International Support", "services": ["Language Programs", "Cultural Integration", "Visa Assistance"]}),
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
