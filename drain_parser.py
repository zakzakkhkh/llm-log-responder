"""
Drain Online Log Parser
Implements the Drain algorithm for log template extraction
Based on: "Drain: An Online Log Parsing Approach with Fixed Depth Tree"
He et al., 2018
"""

import re
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import sqlite3
from datetime import datetime

class DrainNode:
    """Node in the Drain parsing tree"""
    def __init__(self, depth: int, token: Optional[str] = None):
        self.depth = depth
        self.token = token  # None for root node
        self.children: Dict[str, 'DrainNode'] = {}
        self.log_groups: List[Dict] = []  # List of log groups (templates)
    
    def add_log_group(self, log_id: int, log_line: str, template: str):
        """Add a log entry to this node's log groups"""
        # Check if template already exists
        for group in self.log_groups:
            if group['template'] == template:
                group['log_ids'].append(log_id)
                group['frequency'] += 1
                return
        
        # Create new log group
        self.log_groups.append({
            'template': template,
            'log_ids': [log_id],
            'frequency': 1,
            'example': log_line
        })

class DrainParser:
    """
    Drain online log parser with fixed-depth tree
    """
    
    def __init__(self, depth: int = 4, st: float = 0.5, max_child: int = 100):
        """
        Initialize Drain parser
        
        Args:
            depth: Maximum depth of the parsing tree (default: 4)
            st: Similarity threshold for template matching (default: 0.5)
            max_child: Maximum number of children per node (default: 100)
        """
        self.depth = depth
        self.st = st
        self.max_child = max_child
        self.root = DrainNode(depth=0)
        self.template_cache: Dict[str, str] = {}  # Cache log_line -> template
        self.db_file = "incidents.db"
        
    def _tokenize(self, log_line: str) -> List[str]:
        """
        Tokenize log line into tokens
        Splits by spaces and handles special cases
        """
        # Remove leading/trailing whitespace
        log_line = log_line.strip()
        
        # Split by spaces
        tokens = log_line.split()
        
        # Replace numbers and IPs with placeholders
        processed_tokens = []
        for token in tokens:
            # Check if token is a number
            if re.match(r'^\d+$', token):
                processed_tokens.append('<NUM>')
            # Check if token is an IP address
            elif re.match(r'^\d+\.\d+\.\d+\.\d+$', token):
                processed_tokens.append('<IP>')
            # Check if token is a hex value
            elif re.match(r'^0x[0-9a-fA-F]+$', token):
                processed_tokens.append('<HEX>')
            # Check if token is a path
            elif '/' in token or '\\' in token:
                processed_tokens.append('<PATH>')
            else:
                processed_tokens.append(token)
        
        return processed_tokens
    
    def _calculate_similarity(self, tokens1: List[str], tokens2: List[str]) -> float:
        """
        Calculate similarity between two token sequences
        Returns Jaccard similarity
        """
        set1 = set(tokens1)
        set2 = set(tokens2)
        
        if len(set1) == 0 and len(set2) == 0:
            return 1.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def _find_best_match(self, tokens: List[str], node: DrainNode, depth: int) -> Optional[Dict]:
        """
        Recursively find the best matching log group
        """
        if depth >= self.depth or len(tokens) == 0:
            # Leaf node - check log groups
            if node.log_groups:
                best_match = None
                best_similarity = 0.0
                
                for group in node.log_groups:
                    template_tokens = self._tokenize(group['template'])
                    similarity = self._calculate_similarity(tokens, template_tokens)
                    
                    if similarity > best_similarity and similarity >= self.st:
                        best_similarity = similarity
                        best_match = group
                
                return best_match
            return None
        
        # Internal node - traverse children
        current_token = tokens[0] if len(tokens) > 0 else '<*>'
        
        # Try exact match first
        if current_token in node.children:
            match = self._find_best_match(tokens[1:], node.children[current_token], depth + 1)
            if match:
                return match
        
        # Try wildcard match
        if '<*>' in node.children:
            match = self._find_best_match(tokens[1:], node.children['<*>'], depth + 1)
            if match:
                return match
        
        return None
    
    def _add_to_tree(self, log_id: int, log_line: str, template: str, tokens: List[str], 
                     node: DrainNode, depth: int):
        """
        Add log entry to the parsing tree
        """
        if depth >= self.depth or len(tokens) == 0:
            # Leaf node - add to log groups
            node.add_log_group(log_id, log_line, template)
            return
        
        current_token = tokens[0] if len(tokens) > 0 else '<*>'
        
        # Check if we should use wildcard
        if len(node.children) >= self.max_child:
            current_token = '<*>'
        
        # Create child node if it doesn't exist
        if current_token not in node.children:
            node.children[current_token] = DrainNode(depth=depth + 1, token=current_token)
        
        # Recursively add to child
        self._add_to_tree(log_id, log_line, template, tokens[1:], 
                         node.children[current_token], depth + 1)
    
    def parse(self, log_line: str, log_id: Optional[int] = None) -> Tuple[str, int]:
        """
        Parse a log line and return the template pattern and template_id
        
        Args:
            log_line: The log line to parse
            log_id: Optional log ID from database
        
        Returns:
            Tuple of (template_pattern, template_id)
        """
        # Check cache first
        if log_line in self.template_cache:
            template = self.template_cache[log_line]
            template_id = self._get_or_create_template_id(template)
            return template, template_id
        
        tokens = self._tokenize(log_line)
        
        # Try to find existing template
        best_match = self._find_best_match(tokens, self.root, 0)
        
        if best_match:
            # Use existing template
            template = best_match['template']
            template_id = self._get_or_create_template_id(template)
            self.template_cache[log_line] = template
            return template, template_id
        
        # Create new template
        # Replace tokens with placeholders to create template
        template_tokens = []
        for i, token in enumerate(tokens):
            if token in ['<NUM>', '<IP>', '<HEX>', '<PATH>']:
                template_tokens.append(token)
            else:
                # Use first few characters as identifier
                template_tokens.append(token[:8] if len(token) > 8 else token)
        
        template = ' '.join(template_tokens)
        template_id = self._get_or_create_template_id(template)
        
        # Add to tree
        if log_id is None:
            log_id = 0  # Dummy ID if not provided
        self._add_to_tree(log_id, log_line, template, tokens, self.root, 0)
        
        # Cache result
        self.template_cache[log_line] = template
        
        return template, template_id
    
    def _get_or_create_template_id(self, template_pattern: str) -> int:
        """
        Get or create template ID in database
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Ensure templates table exists
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_pattern TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    frequency INTEGER DEFAULT 1
                )
            ''')
            conn.commit()
        except Exception:
            pass  # Table might already exist
        
        # Check if template exists
        try:
            cursor.execute('SELECT template_id FROM templates WHERE template_pattern = ?', 
                          (template_pattern,))
            row = cursor.fetchone()
            
            if row:
                template_id = row[0]
                # Update frequency
                cursor.execute('UPDATE templates SET frequency = frequency + 1 WHERE template_id = ?',
                              (template_id,))
            else:
                # Create new template
                cursor.execute('''
                    INSERT INTO templates (template_pattern, frequency)
                    VALUES (?, 1)
                ''', (template_pattern,))
                template_id = cursor.lastrowid
            
            conn.commit()
        except Exception as e:
            # If database error, return dummy ID
            print(f"[DRAIN] Database error: {e}")
            template_id = 0
        
        conn.close()
        
        return template_id
    
    def get_template_statistics(self) -> Dict:
        """Get statistics about parsed templates"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM templates')
        total_templates = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(frequency) FROM templates')
        total_logs = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_templates': total_templates,
            'total_logs_parsed': total_logs,
            'tree_depth': self.depth,
            'similarity_threshold': self.st
        }

def parse_log_entry(log_line: str, log_id: Optional[int] = None) -> Tuple[str, int]:
    """
    Convenience function to parse a single log entry
    Uses a global Drain parser instance
    """
    global _drain_parser
    if '_drain_parser' not in globals():
        _drain_parser = DrainParser()
    return _drain_parser.parse(log_line, log_id)

if __name__ == "__main__":
    # Test Drain parser
    parser = DrainParser()
    
    test_logs = [
        "2024-01-01 10:00:00 ERROR: Connection failed to 192.168.1.1:8080",
        "2024-01-01 10:00:01 ERROR: Connection failed to 192.168.1.2:8080",
        "2024-01-01 10:00:02 INFO: User logged in from 10.0.0.1",
        "2024-01-01 10:00:03 CRITICAL: Server crashed at /var/log/app.log",
    ]
    
    print("Testing Drain Parser:")
    print("=" * 60)
    
    for i, log_line in enumerate(test_logs):
        template, template_id = parser.parse(log_line, log_id=i+1)
        print(f"Log: {log_line[:50]}...")
        print(f"Template: {template}")
        print(f"Template ID: {template_id}")
        print()
