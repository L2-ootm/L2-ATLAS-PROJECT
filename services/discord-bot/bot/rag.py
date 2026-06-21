import chromadb
from openai import AsyncOpenAI
from sentence_transformers import SentenceTransformer
import os
import random
from dotenv import load_dotenv

load_dotenv()

class KeyManager:
    def __init__(self):
        self.keys = self._load_keys()
        self.current_key_index = 0
        
    def _load_keys(self):
        keys = []
        key1 = os.getenv("OPENROUTER_API_KEY_1")
        key2 = os.getenv("OPENROUTER_API_KEY_2")
        
        if key1: keys.append(key1)
        if key2: keys.append(key2)
        
        if not keys:
            print("Warning: No OPENROUTER_API_KEY_1 or _2 found in environment.")
            legacy_key = os.getenv("OPENROUTER_API_KEY")
            if legacy_key:
                keys.append(legacy_key)
                
        print(f"Loaded {len(keys)} keys from environment.")
        return keys

    def get_current_key(self):
        if not self.keys:
            return None
        return self.keys[self.current_key_index]

    def switch_key(self):
        if not self.keys:
            return None
        
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        print(f"Switched to key index {self.current_key_index}")
        return self.keys[self.current_key_index]

class RAGSystem:
    def __init__(self, path="./chroma_db", supabase_client=None):
        self.key_manager = KeyManager()
        # Initialize embedding model directly
        try:
            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            print("Embedding model loaded.")
        except Exception as e:
            print(f"Failed to load embedding model: {e}")
            self.embedding_model = None

        # Initialize Chroma client directly
        try:
            self.chroma_client = chromadb.PersistentClient(path="chroma_db")
            self.collection = self.chroma_client.get_or_create_collection(name="l2_docs")
            print("ChromaDB client initialized.")
        except Exception as e:
            print(f"Failed to initialize ChromaDB: {e}")
            self.collection = None
        self.supabase_client = supabase_client

    def _get_embedding(self, text):
        if self.embedding_model:
            return self.embedding_model.encode(text).tolist()
        return []

    async def query(self, query_text):
        print(f"RAGSystem.query called with: {query_text}")
        
        # 1. Retrieve context (optional, if embeddings work)
        context = ""
        if self.collection and self.embedding_model:
            try:
                query_embedding = self._get_embedding(query_text)
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=3
                )
                if results['documents']:
                    context = "\n".join(results['documents'][0])
                    print(f"Retrieved {len(results['documents'][0])} documents.")
            except Exception as e:
                print(f"Error retrieving documents: {e}")

        # 2. Call LLM
        current_key = self.key_manager.get_current_key()
        if not current_key:
            return "Error: No API key configured."

        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=current_key,
        )

        # Load system prompt from file
        try:
            with open("bot/system_context.md", "r", encoding="utf-8") as f:
                base_system_prompt = f.read().strip()
        except Exception as e:
            print(f"Error loading system_context.md: {e}")
            base_system_prompt = "You are a helpful AI assistant for the L2 BOT server."

        system_prompt = base_system_prompt
        
        # Inject Local Database Logs if relevant
        # Expanded keywords to catch natural language queries about system state
        triggers = ["log", "audit", "status", "recent", "latest", "last", "happened", "flagged", "ip", "user", "error", "warning", "fail", "success", "who", "what"]
        if any(keyword in query_text.lower() for keyword in triggers):
            try:
                from database.database import DatabaseManager
                logs = await DatabaseManager.get_recent_logs(limit=5)
                if isinstance(logs, list) and logs:
                    log_context = "\n".join([str(log) for log in logs])
                    system_prompt += f"\n\n[SYSTEM LOGS - RECENT ACTIVITY]\n{log_context}\n"
            except Exception as e:
                print(f"Failed to fetch logs for context: {e}")

        if context:
            system_prompt += f"\n\nContext information is below:\n{context}\n\nUse the context to answer the user's question if relevant."

        try:
            print("Sending request to OpenRouter...")
            completion = await client.chat.completions.create(
                model="mistralai/devstral-2512:free",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query_text},
                ],
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Error calling OpenRouter: {e}")
            # Simple retry logic with key switch
            print("Switching key and retrying...")
            new_key = self.key_manager.switch_key()
            if not new_key:
                return f"Error: API call failed and no other keys available. ({e})"
            
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=new_key,
            )
            try:
                completion = await client.chat.completions.create(
                    model="mistralai/devstral-2512:free",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query_text},
                    ],
                )
                return completion.choices[0].message.content
            except Exception as e2:
                return f"Error processing request after retry: {e2}"