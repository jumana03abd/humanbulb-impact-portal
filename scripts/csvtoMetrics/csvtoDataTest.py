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
    'clean tech': ['clean tech'],
    'introduction': ['introduction', 'introducing'],
    'interview confidence':['interview'],
    'initiative': ['initiative', 'leadership'],
    'professional workplace': ['workplace'],
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
def find_name_column(header):
    for idx, column in enumerate(header):
        column = column.strip().lower()

        if (
            column == 'name'
            or column == 'full name'
            or 'participant' in column
        ):
            return idx

    return None
def get_metric_columns(header):
    normalized_headers = convert_labels_to_metric_num(header)

    metric_columns = {}

    for idx, metric in enumerate(normalized_headers):
        if metric in METRIC_KEYWORDS:
            metric_columns[metric] = idx

    return metric_columns
# Compares two files("week1.csv","week8.csv") and prints metrics
def analyze_progress(week1_file: str, week8_file: str):


    # --------------------------------
    # Read Week 8
    # --------------------------------

    week8_data = {}

    with open(week8_file, mode='r', encoding='utf-8') as f8:
        reader = csv.reader(f8)

        header8 = next(reader, None)

        if header8 is None:
            raise ValueError("Week 8 CSV is empty.")

        name_idx8 = find_name_column(header8)

        if name_idx8 is None:
            raise ValueError("Could not find name column in Week 8 CSV.")

        metric_columns8 = get_metric_columns(header8)

        for row in reader:

            if len(row) <= name_idx8:
                continue

            name = row[name_idx8].strip().lower()

            week8_data[name] = row

    # --------------------------------
    # Track progress
    # --------------------------------

    results = {
        metric: {
            'improved': 0,
            'same': 0,
            'decreased': 0,
            'total': 0
        }
        for metric in METRIC_KEYWORDS
    }

    # --------------------------------
    # Read Week 1
    # --------------------------------

    with open(week1_file, mode='r', encoding='utf-8') as f1:
        reader = csv.reader(f1)

        header1 = next(reader, None)

        if header1 is None:
            raise ValueError("Week 1 CSV is empty.")

        name_idx1 = find_name_column(header1)

        if name_idx1 is None:
            raise ValueError("Could not find name column in Week 1 CSV.")

        metric_columns1 = get_metric_columns(header1)

        # --------------------------------
        # Compare participants
        # --------------------------------

        for row in reader:

            if len(row) <= name_idx1:
                continue

            name = row[name_idx1].strip().lower()

            # Participant exists in Week 8
            if name not in week8_data:
                continue

            w1_row = row
            w8_row = week8_data[name]

            # --------------------------------
            # Compare each metric
            # --------------------------------

            for metric in METRIC_KEYWORDS:
                if metric == 'clarity':

                    if metric not in metric_columns8:
                        continue

                    col_idx8 = metric_columns8[metric]

                    if col_idx8 >= len(w8_row):
                        continue

                    clarity_value = w8_row[col_idx8].strip().lower()

                    results[metric]['total'] += 1

                    if clarity_value == 'yes':
                        results[metric]['improved'] += 1

                    elif clarity_value == 'somewhat':
                        results[metric]['same'] += 1

                    elif clarity_value == 'no':
                        results[metric]['decreased'] += 1

                    continue
                # Make sure metric exists in both files
                if metric not in metric_columns1:
                    continue

                if metric not in metric_columns8:
                    continue

                col_idx1 = metric_columns1[metric]
                col_idx8 = metric_columns8[metric]

                # Make sure rows actually contain those columns
                if col_idx1 >= len(w1_row):
                    continue

                if col_idx8 >= len(w8_row):
                    continue

                init_val = conf.parseRating(w1_row[col_idx1])
                final_val = conf.parseRating(w8_row[col_idx8])

                results[metric]['total'] += 1

                if final_val > init_val:
                    results[metric]['improved'] += 1

                elif final_val == init_val:
                    results[metric]['same'] += 1

                else:
                    results[metric]['decreased'] += 1

    # --------------------------------
    # Print results
    # --------------------------------

    print(
        f"{'Metric':<38} | "
        f"{'Improved':<10} | "
        f"{'Unchanged':<10} | "
        f"{'Decreased':<10} | "
        f"{'% Improved'}"
    )

    print("-" * 82)

    for metric, data in results.items():

        total = data['total']

        pct = (
            data['improved'] / total * 100
            if total > 0
            else 0.0
        )

        print(
            f"{metric:<38} | "
            f"{data['improved']:<10} | "
            f"{data['same']:<10} | "
            f"{data['decreased']:<10} | "
            f"{pct:>6.1f}%"
        )
    # Clear metric breakdown output(print)
    # print(f"{'Metric':<38} | {'Improved':<10} | {'Unchanged':<10} | {'Decreased':<10} | {'% Improved'}")
    # print("-" * 82)
    
    # for metric, data in results.items():
    #     total = data['total']
    #     pct = (data['improved'] / total * 100) if total > 0 else 0.0
    #     print(f"{metric:<38} | {data['improved']:<10} | {data['same']:<10} | {data['decreased']:<10} | {pct:>6.1f}%")
    base, extension = os.path.splitext(week8_file)
    output_file = f"{base}_progress.csv"

    with open(output_file, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        # CSV header
        writer.writerow([
            'Metric',
            'Improved',
            'Unchanged',
            'Decreased',
            'Total',
            '% Improved'
        ])

        # CSV data
        for metric, data in results.items():
            total = data['total']
            pct = (data['improved'] / total * 100) if total > 0 else 0.0

            writer.writerow([
                metric,
                data['improved'],
                data['same'],
                data['decreased'],
                total,
                round(pct, 1)
            ])

    print(f"\nResults saved to: {output_file}")

if __name__ == "__main__":
    analyze_progress("scripts/csvtoMetrics/week1.csv", "scripts/csvtoMetrics/week8.csv")
#Next Improvement: automatically ignore timestamp and score, and learn name separate from hard-coded col