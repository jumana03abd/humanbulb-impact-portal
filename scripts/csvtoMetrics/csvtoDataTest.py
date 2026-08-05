import csv
import conf
METRICS = [
    'Communication',
    'Public Speaking',
    'Project Management',
    'Teamwork',
    'Research',
    'Familiarity with Clean Tech Careers',
    'Introducing to a Professional',
    'Job Interview',
    'Initiative/leadership',
    'Professional Workplace'
]
# Compares two files("week1.csv","week8.csv") and prints metrics
def analyze_progress(week1_file: str, week8_file: str):
    # Map participant name -> list of responses
    week8_data = {}
    
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
        for m in METRICS
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
                
                for idx, metric in enumerate(METRICS):
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
    analyze_progress("week1.csv", "week8.csv")