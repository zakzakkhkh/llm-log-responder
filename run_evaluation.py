#!/usr/bin/env python3
"""
Evaluation Runner Script
Runs comprehensive evaluation on datasets and generates reports
"""

import sys
import json
import os
from datetime import datetime
from typing import Optional
from evaluation import (
    evaluate_on_dataset,
    evaluate_action_usefulness,
    evaluate_summarization_quality_enhanced,
    get_metrics_summary
)

def run_comprehensive_evaluation(dataset_file: str, limit: Optional[int] = None):
    """
    Run comprehensive evaluation on dataset
    Generates JSON and formatted text reports
    """
    print("="*70)
    print("COMPREHENSIVE EVALUATION - LLM Log Responder")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}\n")
    
    # Run dataset evaluation
    print("1. Running dataset evaluation...")
    dataset_results = evaluate_on_dataset(dataset_file, limit=limit)
    
    # Extract summaries for quality evaluation
    summaries = dataset_results.get('summaries', [])
    
    # Evaluate summarization quality
    print("\n2. Evaluating summarization quality...")
    summary_quality = evaluate_summarization_quality_enhanced(summaries)
    
    # Evaluate action usefulness
    print("3. Evaluating action usefulness...")
    action_usefulness = evaluate_action_usefulness()
    
    # Get operational metrics
    print("4. Gathering operational metrics...")
    operational_metrics = get_metrics_summary()
    
    # Compile comprehensive report
    report = {
        'timestamp': datetime.now().isoformat(),
        'dataset_file': dataset_file,
        'dataset_evaluation': {
            'total_logs': dataset_results['total_logs'],
            'true_anomalies': dataset_results['true_anomalies'],
            'detected_anomalies': dataset_results['detected_anomalies'],
            'false_positives': dataset_results['false_positives'],
            'false_negatives': dataset_results['false_negatives'],
            'precision': round(dataset_results['precision'], 2),
            'recall': round(dataset_results['recall'], 2),
            'f1_score': round(dataset_results['f1_score'], 2),
            'latency': {
                'average': round(dataset_results['avg_latency'], 2),
                'min': round(dataset_results['min_latency'], 2),
                'max': round(dataset_results['max_latency'], 2)
            }
        },
        'summarization_quality': summary_quality,
        'action_usefulness': action_usefulness,
        'operational_metrics': operational_metrics
    }
    
    # Save JSON report
    output_file = f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nResults saved to: {output_file}\n")
    
    # Print formatted report to terminal so demo audience sees it
    print_formatted_report(report)
    det = report['dataset_evaluation']
    print("\n>>> EVALUATION COMPLETE. Key metrics: Precision {}%, Recall {}%, F1-Score {}%, Avg latency {:.2f}s".format(
        det['precision'], det['recall'], det['f1_score'], det['latency']['average']))
    print("="*70 + "\n")
    sys.stdout.flush()
    
    return report

def print_formatted_report(report: dict):
    """Print formatted evaluation report"""
    print("\n" + "="*70)
    print("EVALUATION REPORT SUMMARY")
    print("="*70)
    print(f"Generated: {report['timestamp']}\n")
    
    # Dataset Evaluation
    det = report['dataset_evaluation']
    print("1. DETECTION METRICS")
    print("-"*70)
    print(f"  Total logs evaluated: {det['total_logs']}")
    print(f"  True anomalies: {det['true_anomalies']}")
    print(f"  Detected anomalies: {det['detected_anomalies']}")
    print(f"  False positives: {det['false_positives']}")
    print(f"  False negatives (missed events): {det['false_negatives']}")
    print(f"  Precision: {det['precision']}%")
    print(f"  Recall: {det['recall']}%")
    print(f"  F1-Score: {det['f1_score']}%\n")
    
    # Latency
    lat = det['latency']
    print("2. LATENCY METRICS")
    print("-"*70)
    print(f"  Average latency: {lat['average']:.2f}s")
    print(f"  Min latency: {lat['min']:.2f}s")
    print(f"  Max latency: {lat['max']:.2f}s\n")
    
    # Summarization Quality
    summ = report['summarization_quality']
    print("3. SUMMARIZATION QUALITY")
    print("-"*70)
    print(f"  Total summaries: {summ['total_summaries']}")
    print(f"  Average length: {summ['avg_length']} characters")
    print(f"  Keyword coverage: {summ['keyword_coverage']}%")
    print(f"  Informativeness score: {summ['informativeness_score']}/100\n")
    
    # Action Usefulness
    action = report['action_usefulness']
    print("4. ACTION USEFULNESS")
    print("-"*70)
    print(f"  Total incidents: {action['total_incidents']}")
    print(f"  Incidents with actions: {action['incidents_with_actions']}")
    print(f"  Useful actions: {action['useful_actions']}")
    print(f"  Usefulness rate: {action['usefulness_rate']:.2f}%\n")
    
    print("="*70)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default to sample dataset
        dataset_file = "test_datasets/sample_logs.csv"
        if not os.path.exists(dataset_file):
            print(f"Error: Dataset file not found: {dataset_file}")
            print("Usage: python3 run_evaluation.py <dataset_file> [limit]")
            sys.exit(1)
    else:
        dataset_file = sys.argv[1]
    
    limit = None
    if len(sys.argv) > 2:
        try:
            limit = int(sys.argv[2])
        except ValueError:
            print(f"Warning: Invalid limit value '{sys.argv[2]}', ignoring...")
    
    run_comprehensive_evaluation(dataset_file, limit=limit)
