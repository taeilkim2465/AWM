import os, json, random
import numpy as np
import math
import uuid
import argparse
import re
import fcntl
from typing import List, Dict, Any
from pathlib import Path
from collections import Counter
from datetime import datetime
from utils.llm import get_embedding
from nltk.stem import SnowballStemmer

import logging
logger = logging.getLogger(__name__)

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

class ReasoningBank:
    def __init__(self, storage_path: str = "reasoning_bank.json", embedding_path: str = "reasoning_bank_embeddings.json"):
        self.storage_path = storage_path
        self.embedding_path = embedding_path
        self.memories = []
        # Initial load for read access. For writing, we'll reload under lock.
        self._load_bank_read_only()

    def _load_bank_read_only(self):
        """Load the reasoning bank content and embeddings from disk safely using shared locks."""
        # Ensure directories exist
        dir_name = os.path.dirname(self.storage_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        
        self.memories = []
        embeddings_map = {}

        # 1. Load Content
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    fcntl.flock(f, fcntl.LOCK_SH) # Shared lock for reading
                    self.memories = json.load(f)
                    fcntl.flock(f, fcntl.LOCK_UN)
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode {self.storage_path}. Starting with empty bank.")
                self.memories = []
            except Exception as e:
                logger.error(f"Error reading {self.storage_path}: {e}")

        # 2. Load Embeddings
        if os.path.exists(self.embedding_path):
            try:
                with open(self.embedding_path, 'r', encoding='utf-8') as f:
                    fcntl.flock(f, fcntl.LOCK_SH) # Shared lock for reading
                    embeddings_map = json.load(f)
                    fcntl.flock(f, fcntl.LOCK_UN)
            except json.JSONDecodeError:
                embeddings_map = {}
            except Exception as e:
                logger.error(f"Error reading {self.embedding_path}: {e}")

        # 3. Merge (In-memory only)
        for entry in self.memories:
            if "id" in entry:
                entry["embedding"] = embeddings_map.get(entry["id"])

    def add_memory(self, task_query: str, trajectory_summary: str, memory_items: List[Dict[str, str]], score: float, domain: str = ""):
        """
        Add memory items to the bank, storing each item as a separate entry.
        Each item gets its own embedding based on task_query + title.
        """
        if not memory_items:
            logger.warning("No memory items to add.")
            return

        # Store each memory item as a separate entry
        for item in memory_items:
            # Create embedding from title + description + content for comprehensive semantic representation
            parts = [
                item.get('title', '').strip(),
                item.get('description', '').strip(),
                item.get('content', '').strip()
            ]
            embedding_text = ' '.join(part for part in parts if part)  # Filter out empty strings

            if not embedding_text:
                logger.warning(f"Skipping memory item with no content: {item}")
                continue

            embedding = get_embedding(embedding_text)

            new_id = str(uuid.uuid4())
            new_entry = {
                "id": new_id,
                "source_task": task_query,
                "domain": domain,
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "content": item.get("content", ""),
                "score": score,
                "timestamp": datetime.now().isoformat()
            }

            # --- Critical Section: Content File ---
            try:
                # Ensure file exists
                if not os.path.exists(self.storage_path):
                    with open(self.storage_path, 'w') as f: json.dump([], f)

                with open(self.storage_path, 'r+', encoding='utf-8') as f:
                    # 1. Acquire Lock
                    fcntl.flock(f, fcntl.LOCK_EX)

                    # 2. Read latest data
                    try:
                        content_data = json.load(f)
                    except json.JSONDecodeError:
                        content_data = []

                    # 3. Modify
                    content_data.append(new_entry)

                    # 4. Write back
                    f.seek(0)
                    json.dump(content_data, f, indent=2, ensure_ascii=False)
                    f.truncate()
                    f.flush()
                    os.fsync(f.fileno())

                    # 5. Release Lock
                    fcntl.flock(f, fcntl.LOCK_UN)

                    # Update in-memory state
                    self.memories = content_data

            except Exception as e:
                logger.error(f"Failed to save content to {self.storage_path}: {e}")
                continue

            # --- Critical Section: Embedding File ---
            if embedding:
                new_entry["embedding"] = embedding
                try:
                    if not os.path.exists(self.embedding_path):
                        with open(self.embedding_path, 'w') as f: json.dump({}, f)

                    with open(self.embedding_path, 'r+', encoding='utf-8') as f:
                        fcntl.flock(f, fcntl.LOCK_EX)
                        try:
                            embedding_data = json.load(f)
                        except json.JSONDecodeError:
                            embedding_data = {}

                        embedding_data[new_id] = embedding

                        f.seek(0)
                        json.dump(embedding_data, f)
                        f.truncate()
                        f.flush()
                        os.fsync(f.fileno())
                        fcntl.flock(f, fcntl.LOCK_UN)
                except Exception as e:
                    logger.error(f"Failed to save embedding to {self.embedding_path}: {e}")

            logger.info(f"Memory item added successfully (ID: {new_id}, Title: {item.get('title', '')[:30]}...)")

    def retrieve(self, query: str, top_k: int = 3, domain: str = None, retrieve_type: str = "embedding") -> List[Dict[str, Any]]:
        """
        Retrieve relevant memory items based on the specified retrieval type.
        """
        self._load_bank_read_only()

        if not self.memories:
            return []

        candidates = self.memories
        if domain:
            filtered_candidates = [m for m in self.memories if m.get("domain") == domain]
            if filtered_candidates:
                candidates = filtered_candidates

        if not candidates:
            return []

        if retrieve_type == "embedding":
            query_embedding = get_embedding(query)
            if not query_embedding:
                return []

            scored_items = []
            for item in candidates:
                item_embedding = item.get("embedding")
                if item_embedding:
                    similarity = cosine_similarity(query_embedding, item_embedding)
                    scored_items.append((similarity, item))
            
            scored_items.sort(key=lambda x: x[0], reverse=True)

        elif retrieve_type == "bm25":
            stemmer = SnowballStemmer("english")
            
            # Stem the corpus
            corpus = [
                [stemmer.stem(token) for token in f"{item.get('title', '')} {item.get('description', '')} {item.get('content', '')}".lower().split()]
                for item in candidates
            ]
            
            # Stem the query
            query_tokens = [stemmer.stem(token) for token in query.lower().split()]
            
            bm25 = BM25(corpus)
            scores = bm25.get_scores(query_tokens)
            
            scored_items = list(zip(scores, candidates))
            scored_items.sort(key=lambda x: x[0], reverse=True)

        else:
            raise ValueError(f"Unknown retrieve_type: {retrieve_type}")

        top_items = []
        for sim, item in scored_items[:top_k]:
            top_items.append({
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "content": item.get("content", "")
            })
            logger.info(f"Retrieved: {item.get('title', '')[:50]}... (similarity={sim:.3f}, source={item.get('source_task', '')[:30]}...)")

        return top_items

if __name__ == "__main__":
    from autoeval.evaluate_trajectory import extract_think_and_action
    from utils.distiller import MemoryDistiller
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--result_dir", type=str, required=True,
                        help="Path to the result directory, e.g., 'results/webarena.0'.")
    parser.add_argument("--reasoning_bank_path", type=str, default="reasoning_bank.json",
                        help="Path to Reasoning Bank storage file.")
    args = parser.parse_args()

    # 1. Parse Task ID and Load Config
    try:
        task_id = args.result_dir.rstrip('/').split('.')[-1] # extract 0 from webarena.0
        config_path = os.path.join("config_files", f"{task_id}.json")
        if not os.path.exists(config_path):
             # Fallback if result_dir structure is different or config not found
             pass
        config = json.load(open(config_path))
    except Exception as e:
        print(f"Failed to load config for {args.result_dir}: {e}")
        exit(1)

    # 2. Check Evaluation Result
    eval_file = None
    for f in os.listdir(args.result_dir):
        if f.endswith("_autoeval.json"):
            eval_file = os.path.join(args.result_dir, f)
            break
    
    if not eval_file:
        print(f"No autoeval result found in {args.result_dir}. Skipping Reasoning Bank update.")
        exit(0)

    try:
        eval_data = json.load(open(eval_file))
        if not eval_data:
            print("Empty autoeval result.")
            exit(0)
        
        result_item = eval_data[0]
        is_success = result_item.get("rm")
        
        if is_success:
            status_str = "Success"
            score = 1.0
        else:
            status_str = "Failure"
            score = 0.0
            print(f"Task {task_id} failed. Processing as negative example.")

    except Exception as e:
        print(f"Error reading evaluation result: {e}")
        exit(1)

    # 3. Extract Trajectory Info
    log_path = os.path.join(args.result_dir, "experiment.log")
    try:
        think_list, action_list = extract_think_and_action(log_path)
    except Exception as e:
        print(f"Error parsing trajectory log: {e}")
        exit(1)

    # 4. Construct Memory Entry using MemoryDistiller
    task_query = config.get("intent", "")
    domain = config.get("sites", [""])[0] 
    
    # Construct trajectory string
    trajectory_str = ""
    for think, actions in zip(think_list, action_list):
        trajectory_str += f"Thought: {think}\nActions: {actions}\n\n"

    print(f"Distilling memory items for task {task_id} ({status_str})...")
    
    distiller = MemoryDistiller()
    memory_items = distiller.distill(
        task=task_query,
        trajectory=trajectory_str,
        outcome=status_str,
        domain=domain
    )

    if not memory_items:
        print("No memory items extracted from LLM response.")
    else:
        # 5. Initialize and Update Reasoning Bank
        storage_path = args.reasoning_bank_path
        base, ext = os.path.splitext(storage_path)
        embedding_path = f"{base}_embeddings{ext}"
        
        bank = ReasoningBank(storage_path=storage_path, embedding_path=embedding_path)
        
        print(f"Adding {len(memory_items)} memory items for task {task_id} to Reasoning Bank...")
        bank.add_memory(
            task_query=task_query,
            trajectory_summary=f"Task: {task_query}\nStatus: {status_str}\n{trajectory_str}", 
            memory_items=memory_items,
            score=score, 
            domain=domain
        )
        print("Reasoning Bank updated successfully.")
