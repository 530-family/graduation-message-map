import csv
import json
import os
import argparse

def update_ndjson_file(file_path, results_data, school_name_field='schoolName', video_status_field='videoStatus', video_url_field='videoUrl'):
    """
    Updates an ndjson file with data from the results CSV.

    Args:
        file_path (str): The path to the ndjson file.
        results_data (dict): A dictionary mapping school names to their results.
        school_name_field (str): The field name for the school in the ndjson.
        video_status_field (str): The field name for video status in the ndjson.
        video_url_field (str): The field name for video URL in the ndjson.
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return set()

    updated_lines = []
    schools_updated = set()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                school_name = data.get(school_name_field)
                
                if school_name in results_data:
                    # Add/update the video status and URL
                    data[video_status_field] = results_data[school_name]['Status']
                    data[video_url_field] = results_data[school_name]['URL']
                    schools_updated.add(school_name)
                
                updated_lines.append(data)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON from line: {line.strip()}")
                # Decide if you want to keep malformed lines, here we drop it.
                continue

    # Write the updated data back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in updated_lines:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
            
    return schools_updated

def main():
    """
    Main function to orchestrate the update process.
    """
    parser = argparse.ArgumentParser(description='Update school data in NDJSON files from a results CSV.')
    parser.add_argument('--results-csv', type=str, default='public/data/results.csv',
                        help='Path to the results CSV file.')
    parser.add_argument('--coords-ndjson', type=str, default='public/data/coordinates.ndjson',
                        help='Path to the coordinates NDJSON file.')
    parser.add_argument('--internal-ndjson', type=str, default='public/data/coordinates.internal.ndjson',
                        help='Path to the internal coordinates NDJSON file.')
    parser.add_argument('--backup', action='store_true',
                        help='Create a backup of the internal coordinates NDJSON file before modification.')
    args = parser.parse_args()

    results_csv_path = args.results_csv
    coords_ndjson_path = args.coords_ndjson
    internal_ndjson_path = args.internal_ndjson

    # 1. Read results.csv into a lookup dictionary
    results_data = {}
    try:
        with open(results_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                school_name = row.get('School')
                if school_name:
                    results_data[school_name.strip()] = row
    except FileNotFoundError:
        print(f"Error: Results file not found at {results_csv_path}")
        return
        
    print(f"Loaded {len(results_data)} schools from {results_csv_path}")

    # 2. Backup coordinates.internal.ndjson if requested
    if args.backup:
        backup_dir = 'public/data/backup'
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = os.path.getmtime(internal_ndjson_path) # Use modification time or current time
        backup_path = os.path.join(backup_dir, f"coordinates.internal.ndjson.{int(timestamp)}.backup")
        try:
            import shutil
            shutil.copyfile(internal_ndjson_path, backup_path)
            print(f"Backup created: {backup_path}")
        except FileNotFoundError:
            print(f"Warning: Could not create backup. File not found: {internal_ndjson_path}")
        except Exception as e:
            print(f"Error creating backup: {e}")

    # 3. Update coordinates.ndjson
    print(f"Updating {coords_ndjson_path}...")
    updated_coords = update_ndjson_file(coords_ndjson_path, results_data)
    print(f"Updated {len(updated_coords)} schools in {coords_ndjson_path}.")

    # 4. Update coordinates.internal.ndjson
    print(f"Updating {internal_ndjson_path}...")
    updated_internal_coords = update_ndjson_file(internal_ndjson_path, results_data)
    print(f"Updated {len(updated_internal_coords)} schools in {internal_ndjson_path}.")
    
    # 5. Report which schools in results.csv were not found in either file
    found_schools = updated_coords.union(updated_internal_coords)
    missing_schools = set(results_data.keys()) - found_schools
    
    if missing_schools:
        print("\nWarning: The following schools from results.csv were not found in any .ndjson file:")
        for school in sorted(list(missing_schools)):
            print(f"- {school}")

    print("\nUpdate process finished.")

if __name__ == '__main__':
    main()
