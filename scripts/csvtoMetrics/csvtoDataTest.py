import csv
import conf
import pandas as pd
import os
METRIC_KEYWORDS = {
    'communication': ['communication'],
    'public speaking': ['public speaking'],
    'project management': ['project management'],
    'teamwork': ['teamwork'],
    'research': ['research'],
    'clean tech careers': ['clean tech careers'],
    'introduction': ['introduction', 'introducing'],
    'initiative': ['initiative', 'leadership'],
    'professional workplace': ['professional workplace'],
    'clarity': ['clarity', 'confidence']
}
# If the prompts have any of these words in them, it shouldn't matter how they're phrased
# Will help to check labels, especially if they are inconsistent between forms
def convert_labels_to_metric_num(headers):
    normalized = []
    for header in headers:
        header_lower = header.lower()
        found_metric = None
        for metric, keywords in METRIC_KEYWORDS.items():
            if any(keyword in header_lower for keyword in keywords):
                found_metric = metric
                break
        if found_metric:
            normalized.append(found_metric)
        else:
            normalized.append(header)
    return normalized
def consistent_labels(week1_file: str, week8_file:str):
    # returns False if labels are INCONSISTENT
    # returns True if labels are CONSISTENT
    # checks if labels are consistent across two files; 
    # if not will need refactoring of some kind
    with open(week1_file, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header_init = convert_labels_to_metric_num(next(reader, None))
    with open(week8_file, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header_final = convert_labels_to_metric_num(next(reader, None))
    if header_final != header_init:
        return False
    return True

def refactor_csv(week1_file: str, week8_file: str):
    # Read Week 1 headers
    with open(week1_file, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        week1_headers = next(reader)

    # Read entire Week 8 file
    with open(week8_file, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        week8_headers = next(reader)
        week8_rows = list(reader)

    # Normalize the headers so we know what metric each column represents
    normalized_week1 = convert_labels_to_metric_num(week1_headers)
    normalized_week8 = convert_labels_to_metric_num(week8_headers)

    # Figure out where each Week 8 metric is located
    week8_column_indices = {}

    for i, metric in enumerate(normalized_week8):
        week8_column_indices[metric] = i

    # Determine the new order based on Week 1
    new_column_order = []

    for metric in normalized_week1:
        if metric in week8_column_indices:
            new_column_order.append(week8_column_indices[metric])
        else:
            print(f"WARNING: Could not find '{metric}' in Week 8")
            return

    # Create the new headers
    new_headers = [
        week8_headers[index]
        for index in new_column_order
    ]

    # Reorder every row using the same column order
    new_rows = []

    for row in week8_rows:
        new_row = [
            row[index]
            for index in new_column_order
        ]
        new_rows.append(new_row)

    # Create filename: week8.csv -> week8_new.csv
    base, extension = os.path.splitext(week8_file)
    new_file = f"{base}_new{extension}"

    # Write the new CSV
    with open(new_file, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        writer.writerow(new_headers)
        writer.writerows(new_rows)

    return new_file
# Compares two files("week1.csv","week8.csv") and prints metrics
def analyze_progress(week1_file: str, week8_file: str):
    # Map participant name -> list of responses
    week8_data = {}
    if not consistent_labels(week1_file,week8_file):
        week8_file=refactor_csv(week1_file,week8_file)#renamed file
    
    with open(week8_file, mode='r', encoding='utf-8') as f8:
        reader = csv.reader(f8)
        header = next(reader, None)  # Skip header if present
        for row in reader:
            if len(row) > 2:
                name = row[2].strip().lower()
                week8_data[name] = row

    # Track progress stats per metric
    results = {
        m: {'improved': 0, 'same': 0, 'decreased': 0, 'total': 0} 
        for m in METRIC_KEYWORDS
    }

    with open(week1_file, mode='r', encoding='utf-8') as f1:
        reader = csv.reader(f1)
        header = next(reader, None)  # Skip header if present
        
        for row in reader:
            if len(row) <= 2:
                continue
            
            name = row[2].strip().lower()
            
            # Match participant in week 8 dataset
            if name in week8_data:
                w1_row = row
                w8_row = week8_data[name]
                
                for idx, metric in enumerate(METRIC_KEYWORDS):
                    col_idx = idx + 3  # Metrics start at column index 3
                    
                    if col_idx < len(w1_row) and col_idx < len(w8_row):
                        init_val = conf.parseRating(w1_row[col_idx])
                        final_val = conf.parseRating(w8_row[col_idx])
                        
                        results[metric]['total'] += 1
                        if final_val > init_val:
                            results[metric]['improved'] += 1
                        elif final_val == init_val:
                            results[metric]['same'] += 1
                        else:
                            results[metric]['decreased'] += 1

    # Clear metric breakdown output
    print(f"{'Metric':<38} | {'Improved':<10} | {'Unchanged':<10} | {'Decreased':<10} | {'% Improved'}")
    print("-" * 82)
    
    for metric, data in results.items():
        total = data['total']
        pct = (data['improved'] / total * 100) if total > 0 else 0.0
        print(f"{metric:<38} | {data['improved']:<10} | {data['same']:<10} | {data['decreased']:<10} | {pct:>6.1f}%")

if __name__ == "__main__":
    analyze_progress("scripts/csvtoMetrics/week1.csv", "scripts/csvtoMetrics/week8.csv")
#Next Improvement: automatically ignore timestamp and score, and learn name separate from hard-coded col