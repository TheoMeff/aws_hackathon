import json
import os
from typing import List, Dict, Any
from tqdm import tqdm
import time

def process_ndjson_files(directory: str) -> List[Dict[str, Any]]:
    """
    Process all NDJSON files in the given directory and extract resource_type, resource_id, and json content.
    
    Args:
        directory: Path to the directory containing NDJSON files
        
    Returns:
        List of dictionaries containing resource_type, resource_id, and json content
    """
    results = []
    
    # Get all NDJSON files in the directory
    ndjson_files = [f for f in os.listdir(directory) if f.endswith('.ndjson')]
    total_files = len(ndjson_files)
    
    print(f"\nProcessing {total_files} NDJSON files:")
    
    for filename in tqdm(ndjson_files, desc="Processing files", unit="file"):
        resource_type = filename.replace('.ndjson', '')
        filepath = os.path.join(directory, filename)
        
        print(f"\nProcessing {resource_type} ({filename})...")
        
        # Get total lines in file for progress bar
        with open(filepath, 'r') as f:
            total_lines = sum(1 for line in f)
        
        with open(filepath, 'r') as f:
            for line in tqdm(f, desc=f"Processing {resource_type}", total=total_lines, unit="lines"):
                try:
                    # Parse the NDJSON line
                    json_data = json.loads(line)
                    # Extract the resource ID (assuming it's in the 'id' field)
                    resource_id = json_data.get('id')
                    
                    if resource_id:
                        results.append({
                            'resource_type': resource_type,
                            'resource_id': resource_id,
                            'json': json_data
                        })
                except json.JSONDecodeError:
                    continue
        
        # Add a small delay to prevent overwhelming output
        time.sleep(0.1)
    
    return results

if __name__ == "__main__":
    # Get the path to the mimic-fhir directory
    mimic_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'mimic-fhir')
    
    print("Starting NDJSON processing...")
    print("")
    
    processed_data = process_ndjson_files(mimic_dir)
    
    # Save the processed data to a JSON file in the current directory
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'processed_data.json')
    
    print(f"\nSaving results to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(processed_data, f, indent=2)
    
    print("\nProcessing complete!")
    print(f"Total resources processed: {len(processed_data)}")
    print(f"Output saved to: {output_file}")
