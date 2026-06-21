"""
L2 SYSTEMS // Memory Manager
Persistent memory storage for the AI agent using ChromaDB.
"""

import chromadb
from datetime import datetime
from typing import List, Dict, Optional
import json
import logging
import uuid

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Manages persistent memory storage for the AI agent.
    Uses ChromaDB for vector storage and retrieval.
    """
    
    def __init__(self, persist_path: str = "chroma_db"):
        try:
            self.client = chromadb.PersistentClient(path=persist_path)
            self.memories = self.client.get_or_create_collection(
                name="l2_memories",
                metadata={"description": "Persistent AI agent memories"}
            )
            self.facts = self.client.get_or_create_collection(
                name="l2_facts",
                metadata={"description": "Important facts and information"}
            )
            logger.info("Memory Manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Memory Manager: {e}")
            self.client = None
            self.memories = None
            self.facts = None
    
    def save_memory(
        self,
        content: str,
        category: str = "general",
        user_id: int = None,
        guild_id: int = None,
        metadata: dict = None
    ) -> str:
        """
        Save a memory to persistent storage.
        
        Args:
            content: The memory content to save
            category: Category (conversation, fact, task, decision, etc.)
            user_id: Discord user ID who created this
            guild_id: Discord guild ID
            metadata: Additional metadata
            
        Returns:
            Memory ID
        """
        if not self.memories:
            return "Error: Memory system not initialized"
        
        memory_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().isoformat()
        
        meta = {
            "category": category,
            "timestamp": timestamp,
            "user_id": str(user_id) if user_id else "system",
            "guild_id": str(guild_id) if guild_id else "global"
        }
        
        if metadata:
            meta.update(metadata)
        
        try:
            self.memories.add(
                ids=[memory_id],
                documents=[content],
                metadatas=[meta]
            )
            logger.info(f"Saved memory {memory_id}: {content[:50]}...")
            return memory_id
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            return f"Error: {e}"
    
    def save_fact(
        self,
        fact: str,
        category: str = "general",
        source: str = None
    ) -> str:
        """
        Save an important fact for permanent retrieval.
        Facts are high-priority memories always retrieved.
        """
        if not self.facts:
            return "Error: Facts collection not initialized"
        
        fact_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().isoformat()
        
        meta = {
            "category": category,
            "timestamp": timestamp,
            "source": source or "user"
        }
        
        try:
            self.facts.add(
                ids=[fact_id],
                documents=[fact],
                metadatas=[meta]
            )
            logger.info(f"Saved fact {fact_id}: {fact[:50]}...")
            return fact_id
        except Exception as e:
            logger.error(f"Failed to save fact: {e}")
            return f"Error: {e}"
    
    def recall(
        self,
        query: str,
        n_results: int = 5,
        category: str = None
    ) -> List[Dict]:
        """
        Recall memories relevant to a query.
        
        Args:
            query: Search query
            n_results: Max results to return
            category: Optional category filter
            
        Returns:
            List of matching memories with content and metadata
        """
        if not self.memories:
            return []
        
        try:
            where_filter = {"category": category} if category else None
            
            results = self.memories.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            
            memories = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i] if results['metadatas'] else {}
                    distance = results['distances'][0][i] if results.get('distances') else 0
                    memories.append({
                        "content": doc,
                        "metadata": meta,
                        "relevance": 1 - distance  # Convert distance to similarity
                    })
            
            return memories
        except Exception as e:
            logger.error(f"Failed to recall memories: {e}")
            return []
    
    def recall_facts(self, query: str, n_results: int = 3) -> List[str]:
        """Recall important facts relevant to query."""
        if not self.facts:
            return []
        
        try:
            results = self.facts.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if results['documents'] and results['documents'][0]:
                return results['documents'][0]
            return []
        except Exception as e:
            logger.error(f"Failed to recall facts: {e}")
            return []
    
    def get_recent_memories(self, limit: int = 10) -> List[Dict]:
        """Get the most recent memories."""
        if not self.memories:
            return []
        
        try:
            # Get all and sort by timestamp
            results = self.memories.get(
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            memories = []
            if results['documents']:
                for i, doc in enumerate(results['documents']):
                    meta = results['metadatas'][i] if results['metadatas'] else {}
                    memories.append({
                        "id": results['ids'][i],
                        "content": doc,
                        "metadata": meta
                    })
            
            # Sort by timestamp descending
            memories.sort(
                key=lambda x: x['metadata'].get('timestamp', ''),
                reverse=True
            )
            
            return memories[:limit]
        except Exception as e:
            logger.error(f"Failed to get recent memories: {e}")
            return []
    
    def forget(self, memory_id: str) -> bool:
        """Delete a specific memory."""
        if not self.memories:
            return False
        
        try:
            self.memories.delete(ids=[memory_id])
            logger.info(f"Deleted memory {memory_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False
    
    def list_all_facts(self) -> List[Dict]:
        """List all stored facts."""
        if not self.facts:
            return []
        
        try:
            results = self.facts.get(
                include=["documents", "metadatas"]
            )
            
            facts = []
            if results['documents']:
                for i, doc in enumerate(results['documents']):
                    facts.append({
                        "id": results['ids'][i],
                        "content": doc,
                        "metadata": results['metadatas'][i] if results['metadatas'] else {}
                    })
            return facts
        except Exception as e:
            logger.error(f"Failed to list facts: {e}")
            return []
    
    def get_memory_context(self, query: str) -> str:
        """
        Build a memory context string for the AI prompt.
        Includes relevant memories and facts.
        """
        context_parts = []
        
        # Get relevant facts
        facts = self.recall_facts(query, n_results=3)
        if facts:
            context_parts.append("**IMPORTANT FACTS:**")
            for fact in facts:
                context_parts.append(f"• {fact}")
        
        # Get relevant memories
        memories = self.recall(query, n_results=5)
        if memories:
            context_parts.append("\n**RELEVANT MEMORIES:**")
            for mem in memories:
                timestamp = mem['metadata'].get('timestamp', 'unknown')[:10]
                context_parts.append(f"[{timestamp}] {mem['content']}")
        
        if context_parts:
            return "\n".join(context_parts)
        return ""


# Global memory manager instance
_memory_manager = None

def get_memory_manager() -> MemoryManager:
    """Get or create the global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
