import os, json, random
import numpy as np
import math
import uuid
import re
import nltk
from nltk.stem import SnowballStemmer # Changed from PorterStemmer
from typing import List, Dict, Any
from pathlib import Path
from collections import Counter
from datetime import datetime
from utils.llm import get_embedding

import logging
logger = logging.getLogger(__name__)

# Initialize Snowball Stemmer globally for English
stemmer = SnowballStemmer("english") # Initialized SnowballStemmer

def cosine_similarity(v1, v2):
    if not v1 or not v2:
        return 0.0
    v1 = np.array(v1)
    v2 = np.array(v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return np.dot(v1, v2) / (norm1 * norm2)

class BM25:
    """Simple BM25 implementation."""
    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avgdl = sum(len(doc) for doc in corpus) / self.corpus_size if self.corpus_size > 0 else 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        
        for doc in corpus:
            self.doc_len.append(len(doc))
            frequencies = Counter(doc)
            self.doc_freqs.append(frequencies)
            for token in frequencies:
                self.idf[token] = self.idf.get(token, 0) + 1
        
        for token, freq in self.idf.items():
            self.idf[token] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query: List[str]) -> List[float]:
        scores = [0.0] * self.corpus_size
        for token in query:
            if token not in self.idf:
                continue
            idf = self.idf[token]
            for index, doc_freqs in enumerate(self.doc_freqs):
                freq = doc_freqs.get(token, 0)
                if freq > 0:
                    numerator = idf * freq * (self.k1 + 1)
                    denominator = freq + self.k1 * (1 - self.b + self.b * self.doc_len[index] / self.avgdl)
                    scores[index] += numerator / denominator
        return scores

def tokenize(text: str) -> List[str]:
    """Basic tokenizer to split text into words, convert to lowercase, and apply stemming."""
    words = re.findall(r'\w+', text.lower())
    return [stemmer.stem(word) for word in words]

class ReasoningBank:
    def __init__(self, storage_path: str = "data/reasoning_bank.json", embedding_path: str = "data/reasoning_bank_embeddings.json"):
        # nltk.download('punkt') # Download necessary NLTK data for tokenization
        self.storage_path = storage_path
        self.embedding_path = embedding_path
        self.memories = []
        self._load_bank()

    def _load_bank(self):
        """Load the reasoning bank content and embeddings from disk, merging them."""
        # 1. Load Content
        if not os.path.exists(self.storage_path):
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            self.memories = []
        else:
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.memories = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode {self.storage_path}. Starting with empty bank.")
                self.memories = []

        # 2. Load Embeddings
        embeddings_map = {}
        if os.path.exists(self.embedding_path):
            try:
                with open(self.embedding_path, 'r', encoding='utf-8') as f:
                    embeddings_map = json.load(f)
            except json.JSONDecodeError:
                embeddings_map = {}

        # 3. Merge and Migrate (Assign IDs if missing, move inline embeddings to map)
        data_dirty = False
        for entry in self.memories:
            # Ensure ID exists
            if "id" not in entry:
                entry["id"] = str(uuid.uuid4())
                data_dirty = True
            
            # Check for inline embedding (legacy migration)
            if "embedding" in entry:
                if entry["embedding"]:
                    embeddings_map[entry["id"]] = entry["embedding"]
                # We don't delete it here effectively, but the save_bank logic 
                # will strip it from the content file.
                data_dirty = True
            else:
                # Load from external map
                entry["embedding"] = embeddings_map.get(entry["id"])
        
        # If migration happened or IDs were generated, save immediately to normalize files
        if data_dirty:
            self.save_bank()

    def save_bank(self):
        """Save content and embeddings to separate files."""
        content_data = []
        embedding_data = {}

        for entry in self.memories:
            # Create a clean copy for content file (exclude embedding)
            item_copy = entry.copy()
            if "embedding" in item_copy:
                del item_copy["embedding"]
            content_data.append(item_copy)
            
            # Store embedding separately if it exists
            if entry.get("embedding"):
                embedding_data[entry["id"]] = entry.get("embedding")

        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(content_data, f, indent=2, ensure_ascii=False)
            
            with open(self.embedding_path, 'w', encoding='utf-8') as f:
                json.dump(embedding_data, f) # Embeddings file can be compact
            
            logger.info(f"Reasoning Bank saved: {len(self.memories)} items.")
        except Exception as e:
            logger.error(f"Failed to save Reasoning Bank: {e}")

    def add_memory(self, task_query: str, trajectory_summary: str, memory_items: List[Dict[str, str]], score: float, outcome: str, domain: str = ""):
        """Add a new entry to the bank (legacy - multiple items)."""
        embedding = get_embedding(task_query)
        new_id = str(uuid.uuid4())
        entry = {
            "id": new_id,
            "task_query": task_query,
            "domain": domain,
            "trajectory_summary": trajectory_summary,
            "memory_items": memory_items,
            "score": score,
            "outcome": outcome,
            "embedding": embedding,
            "timestamp": datetime.now().isoformat()
        }
        self.memories.append(entry)
        self.save_bank()

    def add_memory_item(self, task_query: str, memory_item: Dict[str, str], outcome: str, domain: str = "", context: str = ""):
        """
        Add a single memory item as an independent entry.

        Args:
            task_query: The original task description
            memory_item: Single memory item dict with 'title', 'description', 'content'
            outcome: "SUCCESS" or "FAILURE"
            domain: Website domain
            context: Additional context (e.g., "Successful steps from task")
        """
        # Create embedding text: task + context + item title & description
        embedding_text = f"Task: {task_query}\n"
        if domain:
            embedding_text += f"Domain: {domain}\n"
        if outcome:
            embedding_text += f"Type: {outcome}\n"
        if context:
            embedding_text += f"Context: {context}\n"

        embedding_text += f"\nStrategy: {memory_item.get('title', '')}\n{memory_item.get('description', '')}"

        embedding = get_embedding(embedding_text)
        new_id = str(uuid.uuid4())

        # Flat structure: flatten memory_item fields to top level
        entry = {
            "id": new_id,
            "source_task": task_query,
            "domain": domain,
            "title": memory_item.get("title", ""),
            "description": memory_item.get("description", ""),
            "content": memory_item.get("content", ""),
            "score": 1.0 if outcome == "SUCCESS" else 0.0,
            "embedding": embedding,
            "timestamp": datetime.now().isoformat()
        }
        self.memories.append(entry)
        self.save_bank()

    def retrieve(self, query: str, top_k: int = 3, domain: str = None, retrieve_type: str = "embedding") -> List[Dict[str, Any]]:
        """
        Retrieve relevant memory items based on query similarity using either embedding or BM25.
        Optionally filter by domain.
        Returns list of memory items in format: {"title": ..., "description": ..., "content": ...}
        """
        if not self.memories:
            return []

        # 1. Filter candidates by domain
        candidates = self.memories
        if domain:
            filtered_candidates = [m for m in self.memories if m.get("domain") == domain]
            if filtered_candidates:
                candidates = filtered_candidates

        if not candidates:
            return []

        scored_items = []
        updates_made = False

        if retrieve_type == "embedding":
            # 2. Compute query embedding
            query_embedding = get_embedding(query)
            if not query_embedding:
                return []

            # 3. Calculate similarity for each memory item
            for entry in candidates:
                # Recompute embedding if not present
                mem_embedding = entry.get("embedding")
                if not mem_embedding:
                    # Try both source_task (new) and task_query (legacy) for embedding generation
                    task_text = entry.get("source_task") or entry.get("task_query", "")
                    mem_embedding = get_embedding(task_text)
                    entry["embedding"] = mem_embedding
                    updates_made = True

                if mem_embedding:
                    similarity = cosine_similarity(query_embedding, mem_embedding)
                    scored_items.append((similarity, entry))
        
        elif retrieve_type == "bm25":
            # Prepare BM25 corpus and tokenize query
            corpus_docs = []
            for entry in candidates:
                # Combine relevant text fields for BM25
                combined_text = f"{entry.get('title', '')} {entry.get('description', '')} {entry.get('content', '')}"
                corpus_docs.append(tokenize(combined_text))
            
            if not corpus_docs:
                return []

            bm25 = BM25(corpus_docs)
            tokenized_query = tokenize(query)
            bm25_scores = bm25.get_scores(tokenized_query)

            for i, score in enumerate(bm25_scores):
                scored_items.append((score, candidates[i]))
        else:
            logger.warning(f"Unknown retrieve_type: {retrieve_type}. Defaulting to embedding retrieval.")
            # Fallback to embedding if an unknown type is provided
            query_embedding = get_embedding(query)
            if not query_embedding:
                return []
            for entry in candidates:
                mem_embedding = entry.get("embedding")
                if not mem_embedding:
                    task_text = entry.get("source_task") or entry.get("task_query", "")
                    mem_embedding = get_embedding(task_text)
                    entry["embedding"] = mem_embedding
                    updates_made = True
                if mem_embedding:
                    similarity = cosine_similarity(query_embedding, mem_embedding)
                    scored_items.append((similarity, entry))


        # Save updates if any lazy loading occurred
        if updates_made:
            self.save_bank()

        # 4. Sort by similarity/score and select top-k items
        scored_items.sort(key=lambda x: x[0], reverse=True)

        # 5. Return top-k items in correct format
        # Support multiple formats for backward compatibility
        top_items = []
        for sim, entry in scored_items[:top_k]:
            # New flat format: title, description, content at top level
            if "title" in entry and "description" in entry and "content" in entry:
                top_items.append({
                    "title": entry["title"],
                    "description": entry["description"],
                    "content": entry["content"]
                })
            # Legacy format: single memory_item object
            elif "memory_item" in entry and entry["memory_item"]:
                top_items.append(entry["memory_item"])
            # Legacy format: memory_items array
            elif "memory_items" in entry and entry["memory_items"]:
                top_items.extend(entry["memory_items"])

            if len(top_items) >= top_k:
                break

        return top_items[:top_k]