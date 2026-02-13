"""
Retrieval-Augmented Generation (RAG) Framework
Implements RAG for log summarization with vector embeddings
Uses Sentence-BERT for dense vector embeddings and retrieval
"""

import os
# Suppress HuggingFace/transformers progress and verbose logs for cleaner demo output
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
import sqlite3
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("[WARNING] sentence-transformers not available. Install with: pip install sentence-transformers")

from database import get_logs_by_template_id, search_logs_by_pattern, get_incidents_by_time_window
from llm_api_caller import call_llm

class RAGRetriever:
    """
    Retrieval component for RAG framework
    Uses vector embeddings for semantic search and template-based correlation
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize RAG retriever with embedding model
        
        Args:
            model_name: Sentence-BERT model name (default: all-MiniLM-L6-v2, lightweight)
        """
        self.model_name = model_name
        self.embedder = None
        self.db_file = "incidents.db"
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedder = SentenceTransformer(model_name)
            except Exception as e:
                print(f"[RAG] Failed to load embedding model: {e}")
                self.embedder = None
        else:
            print("[RAG] Using fallback keyword-based retrieval (sentence-transformers not installed)")
    
    def _embed_text(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding vector for text"""
        if self.embedder is None:
            return None
        try:
            # Truncate very long texts to avoid token limits
            max_length = 512
            if len(text) > max_length:
                text = text[:max_length]
            return self.embedder.encode(text, convert_to_numpy=True, show_progress_bar=False)
        except Exception as e:
            print(f"[RAG] Embedding error: {e}")
            return None
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
    
    def retrieve_relevant_logs(self, query: str, incident_id: Optional[int] = None, 
                                hours: int = 1, top_k: int = 10) -> List[Dict]:
        """
        Retrieve relevant logs using RAG retrieval
        Combines template-based correlation and semantic similarity
        
        Args:
            query: Query text or incident summary
            incident_id: Optional incident ID for template correlation
            hours: Time window for retrieval
            top_k: Number of top results to return
        
        Returns:
            List of relevant log entries with similarity scores
        """
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get time window
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        cutoff_iso = datetime.fromtimestamp(cutoff_time).isoformat()
        
        # Step 1: Template-based retrieval (if incident has template_id)
        template_logs = []
        if incident_id:
            cursor.execute('''
                SELECT template_id FROM logs l
                INNER JOIN incidents i ON l.log_line = i.log_line
                WHERE i.incident_id = ?
                LIMIT 1
            ''', (incident_id,))
            row = cursor.fetchone()
            if row:
                template_id = row[0]
                template_logs = get_logs_by_template_id(template_id, hours)
        
        # Step 2: Semantic retrieval using embeddings
        semantic_logs = []
        if self.embedder is not None:
            query_embedding = self._embed_text(query)
            if query_embedding is not None:
                # Get logs with embeddings
                cursor.execute('''
                    SELECT log_id, log_line, timestamp, embedding_vector
                    FROM logs
                    WHERE timestamp >= ? AND embedding_vector IS NOT NULL
                    LIMIT 100
                ''', (cutoff_iso,))
                
                results = []
                for row in cursor.fetchall():
                    log_id = row['log_id']
                    log_line = row['log_line']
                    timestamp = row['timestamp']
                    embedding_bytes = row['embedding_vector']
                    
                    if embedding_bytes:
                        try:
                            log_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                            similarity = self._cosine_similarity(query_embedding, log_embedding)
                            results.append({
                                'log_id': log_id,
                                'log_line': log_line,
                                'timestamp': timestamp,
                                'similarity': float(similarity),
                                'retrieval_method': 'semantic'
                            })
                        except Exception as e:
                            print(f"[RAG] Error decoding embedding: {e}")
                            continue
                
                # Sort by similarity and take top_k
                results.sort(key=lambda x: x['similarity'], reverse=True)
                semantic_logs = results[:top_k]
        
        # Step 3: Keyword-based retrieval (fallback)
        keyword_logs = []
        if not semantic_logs and not template_logs:
            # Extract keywords from query
            import re
            keywords = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
            for keyword in keywords[:3]:  # Use top 3 keywords
                keyword_results = search_logs_by_pattern(keyword, hours)
                keyword_logs.extend(keyword_results[:5])  # Top 5 per keyword
        
        # Combine and deduplicate results
        all_logs = {}
        
        # Add template-based logs
        for log in template_logs:
            log_id = log.get('log_id')
            if log_id:
                all_logs[log_id] = {
                    **log,
                    'similarity': 0.9,  # High similarity for template matches
                    'retrieval_method': 'template'
                }
        
        # Add semantic logs
        for log in semantic_logs:
            log_id = log['log_id']
            if log_id not in all_logs or log['similarity'] > all_logs[log_id].get('similarity', 0):
                all_logs[log_id] = log
        
        # Add keyword logs as fallback
        for log in keyword_logs:
            log_id = log.get('log_id')
            if log_id and log_id not in all_logs:
                all_logs[log_id] = {
                    **log,
                    'similarity': 0.5,  # Lower similarity for keyword matches
                    'retrieval_method': 'keyword'
                }
        
        # Sort by similarity and return top_k
        sorted_logs = sorted(all_logs.values(), 
                           key=lambda x: x.get('similarity', 0), 
                           reverse=True)
        
        conn.close()
        return sorted_logs[:top_k]
    
    def update_log_embeddings(self, log_id: int, log_line: str):
        """Update embedding vector for a log entry"""
        if self.embedder is None:
            return
        
        embedding = self._embed_text(log_line)
        if embedding is not None:
            embedding_bytes = embedding.tobytes()
            
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE logs SET embedding_vector = ? WHERE log_id = ?
            ''', (embedding_bytes, log_id))
            conn.commit()
            conn.close()

class RAGSummarizer:
    """
    RAG-based summarization component
    Retrieves relevant context and generates summaries using LLM
    """
    
    def __init__(self):
        """Initialize RAG summarizer"""
        self.retriever = RAGRetriever()
    
    def summarize_incident(self, incident_id: int, hours: int = 1) -> str:
        """
        Generate summary for an incident using RAG
        
        Args:
            incident_id: Incident ID to summarize
            hours: Time window for context retrieval
        
        Returns:
            Generated summary text
        """
        # Get incident details
        conn = sqlite3.connect(self.retriever.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM incidents WHERE incident_id = ?', (incident_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return "Incident not found"
        incident = dict(row)  # sqlite3.Row has no .get(); use dict for safe access
        
        incident_log = incident.get('log_line', '')
        incident_summary = incident.get('summary', '')
        
        # Retrieve relevant context using RAG
        query = f"{incident_log} {incident_summary}"
        relevant_logs = self.retriever.retrieve_relevant_logs(
            query, incident_id=incident_id, hours=hours, top_k=10
        )
        
        # Build context for LLM
        context_logs = []
        for log_entry in relevant_logs:
            log_line = log_entry.get('log_line', '')
            timestamp = log_entry.get('timestamp', '')
            method = log_entry.get('retrieval_method', 'unknown')
            context_logs.append(f"[{timestamp}] {log_line} (retrieved via {method})")
        
        context_text = "\n".join(context_logs[:10])  # Top 10 relevant logs
        
        # Generate summary using LLM with retrieved context
        prompt = f"""
        Analyze the following incident and its related log context (retrieved using RAG):
        
        INCIDENT:
        {incident_log}
        
        RELATED LOG CONTEXT (retrieved via template correlation and semantic similarity):
        {context_text}
        
        Provide a comprehensive summary that:
        1. Explains the root cause
        2. Identifies related events from the context
        3. Suggests remediation steps
        
        Summary:
        """
        
        result = call_llm(prompt)
        if result and 'summary' in result:
            return result['summary']
        else:
            # Fallback summary
            return f"Incident detected: {incident_log}. Related events found: {len(relevant_logs)}"
    
    def summarize_time_window(self, hours: int = 1) -> str:
        """
        Summarize all incidents in a time window using RAG
        
        Args:
            hours: Time window in hours
        
        Returns:
            Generated summary text
        """
        incidents = get_incidents_by_time_window(hours)
        
        if not incidents:
            return f"No incidents found in the last {hours} hour(s)"
        
        # Retrieve relevant logs for all incidents
        all_relevant_logs = []
        for incident in incidents[:5]:  # Limit to 5 incidents for performance
            incident_id = incident['incident_id']
            incident_log = incident['log_line']
            
            relevant_logs = self.retriever.retrieve_relevant_logs(
                incident_log, incident_id=incident_id, hours=hours, top_k=5
            )
            all_relevant_logs.extend(relevant_logs)
        
        # Deduplicate
        seen_log_ids = set()
        unique_logs = []
        for log_entry in all_relevant_logs:
            log_id = log_entry.get('log_id')
            if log_id and log_id not in seen_log_ids:
                seen_log_ids.add(log_id)
                unique_logs.append(log_entry)
        
        # Build context
        context_text = "\n".join([
            f"[{log.get('timestamp', '')}] {log.get('log_line', '')}"
            for log in unique_logs[:20]
        ])
        
        incidents_text = "\n".join([
            f"- {inc['log_line']}" for inc in incidents[:10]
        ])
        
        # Generate summary
        prompt = f"""
        Summarize the following incidents and their related log context (retrieved using RAG):
        
        INCIDENTS ({len(incidents)} total):
        {incidents_text}
        
        RELATED LOG CONTEXT (retrieved via template correlation and semantic similarity):
        {context_text}
        
        Provide a comprehensive summary covering:
        1. Main issues and patterns
        2. Root causes
        3. Recommended actions
        
        Summary:
        """
        
        result = call_llm(prompt)
        if result and 'summary' in result:
            return result['summary']
        else:
            return f"Found {len(incidents)} incidents in the last {hours} hour(s). Related context: {len(unique_logs)} log entries."

# Global RAG instance
_rag_summarizer = None

def get_rag_summarizer() -> RAGSummarizer:
    """Get global RAG summarizer instance"""
    global _rag_summarizer
    if _rag_summarizer is None:
        _rag_summarizer = RAGSummarizer()
    return _rag_summarizer

if __name__ == "__main__":
    # Test RAG framework
    print("Testing RAG Framework:")
    print("=" * 60)
    
    summarizer = RAGSummarizer()
    print("RAG Summarizer initialized")
    
    # Test retrieval
    test_query = "ERROR connection failed"
    relevant_logs = summarizer.retriever.retrieve_relevant_logs(test_query, hours=24, top_k=5)
    print(f"\nRetrieved {len(relevant_logs)} relevant logs for query: '{test_query}'")
    for log in relevant_logs[:3]:
        print(f"  - {log.get('log_line', '')[:60]}... (similarity: {log.get('similarity', 0):.2f})")
