"""
Log Ingestion Module
Handles log ingestion from syslog and journald
Provides unified interface for different log sources
"""

import os
import sys
import subprocess
import re
from typing import Optional, Iterator
from datetime import datetime
import threading
import queue

from database import store_log_entry
from drain_parser import parse_log_entry

class LogIngestion:
    """
    Unified log ingestion from multiple sources
    Supports syslog, journald, and file-based logs
    """
    
    def __init__(self, source: str = "file", log_file: Optional[str] = None):
        """
        Initialize log ingestion
        
        Args:
            source: Log source type ('syslog', 'journald', or 'file')
            log_file: Path to log file (for file source)
        """
        self.source = source
        self.log_file = log_file or "server.log"
        self.running = False
        self.log_queue = queue.Queue()
        self.ingestion_thread = None
    
    def _ingest_syslog(self) -> Iterator[str]:
        """
        Ingest logs from syslog
        Uses tail -f on /var/log/syslog or journalctl -f
        """
        try:
            # Try journalctl first (systemd systems)
            if os.path.exists("/run/systemd/system"):
                process = subprocess.Popen(
                    ["journalctl", "-f", "--no-pager", "-o", "short"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                for line in iter(process.stdout.readline, ''):
                    if line:
                        yield line.strip()
            else:
                # Fallback to syslog file
                if os.path.exists("/var/log/syslog"):
                    process = subprocess.Popen(
                        ["tail", "-f", "/var/log/syslog"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1
                    )
                    
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            yield line.strip()
                else:
                    print("[INGESTION] syslog not found. Falling back to file-based ingestion.")
                    yield from self._ingest_file()
        
        except FileNotFoundError:
            print("[INGESTION] syslog/journald tools not found. Falling back to file-based ingestion.")
            yield from self._ingest_file()
        except Exception as e:
            print(f"[INGESTION] Error reading syslog: {e}")
            yield from self._ingest_file()
    
    def _ingest_journald(self) -> Iterator[str]:
        """
        Ingest logs from systemd journal
        Uses journalctl -f for real-time streaming
        """
        try:
            process = subprocess.Popen(
                ["journalctl", "-f", "--no-pager", "-o", "short"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            for line in iter(process.stdout.readline, ''):
                if line:
                    yield line.strip()
        
        except FileNotFoundError:
            print("[INGESTION] journalctl not found. Falling back to file-based ingestion.")
            yield from self._ingest_file()
        except Exception as e:
            print(f"[INGESTION] Error reading journald: {e}")
            yield from self._ingest_file()
    
    def _ingest_file(self) -> Iterator[str]:
        """
        Ingest logs from file (tail -f style)
        """
        if not os.path.exists(self.log_file):
            # Create empty file if it doesn't exist
            open(self.log_file, 'a').close()
            print(f"[INGESTION] Created log file: {self.log_file}")
        
        try:
            process = subprocess.Popen(
                ["tail", "-f", self.log_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            for line in iter(process.stdout.readline, ''):
                if line:
                    yield line.strip()
        
        except FileNotFoundError:
            print(f"[INGESTION] tail command not found. Using simple file reading.")
            # Fallback: simple file reading
            with open(self.log_file, 'r') as f:
                f.seek(0, 2)  # Seek to end
                while True:
                    line = f.readline()
                    if line:
                        yield line.strip()
                    else:
                        import time
                        time.sleep(0.1)
        except Exception as e:
            print(f"[INGESTION] Error reading file: {e}")
    
    def _process_log_line(self, log_line: str):
        """
        Process a single log line
        Parses with Drain, stores in database, and checks for anomalies
        """
        if not log_line or not log_line.strip():
            return
        
        # Detect anomaly using pattern matching
        anomaly_keywords = ['ERROR', 'CRITICAL', 'Failed', 'Timeout', 'FATAL', 'WARNING']
        is_anomaly = any(keyword in log_line.upper() for keyword in anomaly_keywords)
        
        # Parse with Drain to extract template
        try:
            template, template_id = parse_log_entry(log_line)
        except Exception as e:
            print(f"[INGESTION] Drain parsing error: {e}")
            template = None
            template_id = None
        
        # Store in database with dual-indexing
        try:
            log_id = store_log_entry(log_line, is_anomaly=is_anomaly, template_id=template_id)
            
            # Update embedding if RAG is available
            try:
                from rag_framework import RAGRetriever
                retriever = RAGRetriever()
                if retriever.embedder is not None:
                    retriever.update_log_embeddings(log_id, log_line)
            except Exception as e:
                # RAG not available or error - continue without embedding
                pass
            
        except Exception as e:
            print(f"[INGESTION] Database error: {e}")
    
    def _ingestion_worker(self):
        """
        Worker thread for log ingestion
        Continuously reads from log source and processes lines
        """
        try:
            if self.source == "syslog":
                log_iterator = self._ingest_syslog()
            elif self.source == "journald":
                log_iterator = self._ingest_journald()
            else:
                log_iterator = self._ingest_file()
            
            for log_line in log_iterator:
                if not self.running:
                    break
                
                self._process_log_line(log_line)
        
        except Exception as e:
            print(f"[INGESTION] Ingestion worker error: {e}")
    
    def start(self):
        """Start log ingestion in background thread"""
        if self.running:
            print("[INGESTION] Already running")
            return
        
        self.running = True
        self.ingestion_thread = threading.Thread(target=self._ingestion_worker, daemon=True)
        self.ingestion_thread.start()
        print(f"[INGESTION] Started log ingestion from {self.source}")
    
    def stop(self):
        """Stop log ingestion"""
        self.running = False
        if self.ingestion_thread:
            self.ingestion_thread.join(timeout=5)
        print("[INGESTION] Stopped log ingestion")
    
    def get_source_info(self) -> dict:
        """Get information about the log source"""
        info = {
            'source': self.source,
            'running': self.running
        }
        
        if self.source == "file":
            info['log_file'] = self.log_file
            info['exists'] = os.path.exists(self.log_file)
        elif self.source == "syslog":
            info['syslog_exists'] = os.path.exists("/var/log/syslog")
            info['journald_available'] = os.path.exists("/run/systemd/system")
        elif self.source == "journald":
            info['journald_available'] = os.path.exists("/run/systemd/system")
        
        return info

if __name__ == "__main__":
    # Test log ingestion
    print("Testing Log Ingestion:")
    print("=" * 60)
    
    # Test file-based ingestion
    ingestion = LogIngestion(source="file", log_file="server.log")
    info = ingestion.get_source_info()
    print(f"Source info: {info}")
    
    # Test syslog detection
    syslog_ingestion = LogIngestion(source="syslog")
    syslog_info = syslog_ingestion.get_source_info()
    print(f"Syslog info: {syslog_info}")
