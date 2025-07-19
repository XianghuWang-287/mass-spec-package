import re
import requests
import numpy as np
from pyteomics import mzml
import io
import time

def get_zenodo_files(database_num):
    """Get all mzML file information from Zenodo database"""
    request_url = f"https://zenodo.org/api/records/{database_num}"
    response = requests.get(request_url)
    response.raise_for_status()
    data = response.json()
    
    # Extract all mzML files
    mzml_files = {file['key']: file['size'] for file in data['files'] if file['key'].endswith('.mzML')}
    
    print("Available mzML files:")
    for file, size in mzml_files.items():
        if size < 1024:
            size_str = f"{size} bytes"
        elif size < 1024**2:
            size_str = f"{size / 1024:.2f} KB"
        elif size < 1024**3:
            size_str = f"{size / 1024**2:.2f} MB"
        else:
            size_str = f"{size / 1024**3:.2f} GB"
        print(f"{file} ({size_str})")
    
    return mzml_files

def extract_scan_index(file_name, database_num, file_size, target_scan=None):
    """Extract scan index from the end of mzML file, supports partial indexing (up to target scan)"""
    file_url = f"https://zenodo.org/record/{database_num}/files/{file_name}"
    scan_dict = {}
    
    # Start reading from the end of file, 250KB at a time
    chunk_size = 250000
    start_byte = max(0, file_size - chunk_size)
    end_byte = file_size - 1
    
    while True:
        # Download the end portion of the file
        headers = {"Range": f"bytes={start_byte}-{end_byte}"}
        response = requests.get(file_url, headers=headers)
        response.raise_for_status()
        
        # Process data in memory
        content = response.content.decode('utf-8', errors='ignore')
        
        # Extract scan offsets
        matches = re.findall(r'<offset idRef="[^"]*?(\d+)">(\d+)</offset>', content)
        for scan_id, offset in matches:
            scan_dict[int(scan_id)] = int(offset)
        
        # Stop if target scan is found or reached the beginning of file
        if target_scan is None or target_scan in scan_dict or start_byte == 0:
            break
            
        # Continue reading forward
        start_byte = max(0, start_byte - chunk_size)
    
    if not scan_dict:
        raise ValueError("No scan indices found in the file")
    
    return scan_dict

def get_scan_data(file_name, database_num, scan_number):
    """Get data for the specified scan"""
    start_time = time.time()
    
    # Get file size from Zenodo API
    request_url = f"https://zenodo.org/api/records/{database_num}"
    response = requests.get(request_url)
    response.raise_for_status()
    data = response.json()
    
    mzml_files = {file['key']: file['size'] for file in data['files'] if file['key'].endswith('.mzML')}
    if file_name not in mzml_files:
        raise ValueError(f"File {file_name} not found in the database")
    
    file_size = mzml_files[file_name]
    
    # Get scan index
    scan_dict = extract_scan_index(file_name, database_num, file_size, scan_number)
    
    if scan_number not in scan_dict:
        raise ValueError(f"Scan {scan_number} not found in the file")
    
    # Find the start position of the next scan
    scan_numbers = sorted(scan_dict.keys())
    scan_index = scan_numbers.index(scan_number)
    next_scan = scan_numbers[scan_index + 1] if scan_index + 1 < len(scan_numbers) else None
    
    # Calculate scan data range
    scan_start = scan_dict[scan_number]
    scan_end = scan_dict[next_scan] - 10 if next_scan else file_size - 1
    
    # Download scan data
    file_url = f"https://zenodo.org/record/{database_num}/files/{file_name}"
    headers = {"Range": f"bytes={scan_start}-{scan_end}"}
    response = requests.get(file_url, headers=headers)
    response.raise_for_status()
    
    # Process mzML data in memory
    scan_content = response.content.decode('utf-8', errors='ignore')
    
    # If it's the last scan, ensure truncation at </spectrum>
    if not next_scan:
        last_spectrum_end = scan_content.rfind("</spectrum>")
        if last_spectrum_end != -1:
            scan_content = scan_content[:last_spectrum_end + len("</spectrum>")]
    
    # Parse scan data using pyteomics
    with io.BytesIO(scan_content.encode('utf-8')) as bio:
        with mzml.read(bio) as reader:
            for spectrum in reader:
                mz_values = spectrum['m/z array']
                intensity_values = spectrum['intensity array']
                retention_time = spectrum.get('scanList', {}).get('scan', [{}])[0].get('scan start time', 'N/A')
                charge_state = spectrum.get('precursorList', {}).get('precursor', [{}])[0].get('selectedIonList', {}).get('selectedIon', [{}])[0].get('charge state', 'N/A')
                collision_energy = spectrum.get('precursorList', {}).get('precursor', [{}])[0].get('activation', {}).get('collision energy', 'N/A')
                ms_level = spectrum.get('ms level', 'N/A')
                
                # Normalize intensity values
                max_intensity = max(intensity_values)
                normalized_intensities = intensity_values / max_intensity
                
                scan_data = {
                    'mz': mz_values,
                    'intensities': normalized_intensities,
                    'RT-time': retention_time,
                    'charge': charge_state,
                    'collision energy': collision_energy,
                    'ms level': ms_level
                }
                
                end_time = time.time()
                print(f"Time taken to retrieve scan {scan_number}: {end_time - start_time:.2f} seconds")
                
                return scan_data
    
    raise ValueError(f"No spectrum data found for scan {scan_number}")

def main():
    """Main function test example"""
    database = 10211590
    test_scans = [421, 1685, 8645, 255]
    
    # Get file information
    mzml_files = get_zenodo_files(database)
    file_name = list(mzml_files.keys())[0]
    
    print(f"\nProcessing file: {file_name}")
    
    # Get data for multiple scans
    for scan_num in test_scans:
        try:
            scan_data = get_scan_data(file_name, database, scan_num)
            print(f"Scan {scan_num} RT-time: {scan_data['RT-time']}")
        except Exception as e:
            print(f"Error getting scan {scan_num}: {e}")

if __name__ == "__main__":
    main()