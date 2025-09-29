#!/usr/bin/env python

"""
Fix mbsync sync hiccups by finding files with duplicate UIDs and removing the
part of the filename that denotes the UID and IMAP flags from all but the
earliest one.
"""

import os
import re
from pathlib import Path
from collections import defaultdict

def extract_id(filename):
    """Extract the ID from pattern ...,U=<ID>:... in filename."""
    match = re.search(r',U=([0-9]+):', filename)
    return match.group(1) if match else None


def get_file_creation_time(filepath):
    """Get the creation time of a file."""
    return os.path.getctime(filepath)


def truncate_to_first_comma(filename):
    """Truncate filename to everything before the first comma."""
    comma_pos = filename.find(',')
    if comma_pos != -1:
        new_name = filename[:comma_pos]
    else:
        new_name = filename
    
    return new_name


def main():
    files = [f for f in Path('.').iterdir() if f.is_file()]
    
    # Group files by their ID
    id_to_files = defaultdict(list)
    
    for file in files:
        file_id = extract_id(file.name)
        if file_id:
            id_to_files[file_id].append(file)
    
    # Find duplicates and process them
    for file_id, file_list in id_to_files.items():
        if len(file_list) > 1:
            print(f"\nFound {len(file_list)} files with ID: {file_id}")
            
            # Sort by creation time (earliest first)
            file_list.sort(key=lambda f: get_file_creation_time(f))
            
            # Keep the earliest, rename the rest
            earliest = file_list[0]
            print(f"  Keeping (earliest): {earliest.name}")
            
            for file in file_list[1:]:
                new_name = truncate_to_first_comma(file.name)
                new_path = file.parent / new_name
                
                # Handle potential naming conflicts
                counter = 1
                while new_path.exists() and new_path != file:
                    stem = Path(new_name).stem
                    ext = Path(new_name).suffix
                    new_name = f"{stem}_{counter}{ext}"
                    new_path = file.parent / new_name
                    counter += 1
                
                print(f"  Renaming: {file.name} -> {new_name}")
                try:
                    file.rename(new_path)
                except Exception as e:
                    print(f"    Error renaming file: {e}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()

