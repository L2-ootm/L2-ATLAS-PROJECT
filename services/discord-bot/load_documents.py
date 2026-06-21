from sentence_transformers import SentenceTransformer
from bot.rag import RAGSystem
import os

# Initialize the RAG system
rag = RAGSystem()

# Path to the knowledge base directory
knowledge_base_path = "./knowledge_base"

# Iterate over all files in the knowledge base directory
for filename in os.listdir(knowledge_base_path):
    if filename.endswith(".txt"):
        file_path = os.path.join(knowledge_base_path, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Add the document to the ChromaDB collection
            rag.vectorstore.add_texts(
                texts=[content],
                metadatas=[{"source": filename}],
                ids=[filename]
            )
            print(f"Added document: {filename}")