## A Python Package for Mass Spectrometry
Developed by Akshay Jay.  
Use case: create an mzml_repo object. After providing a Zenodo database ID, the object stores the name, URL, and size of all files in the database.
Requesting a scan from the file will provide the scan's mz and intensity values along with other metadata. If not already in memory, calling get_scan() will store the byte offets of that scan and all scans that come after it.
## How to Use the Class
file_names stores the names of every file in the database  
all_files stores the size of each file in the database  
all_scans is a dictionary of tuples where each key is a file name and the value is a tuple containing:  
    1. scan_dict: a dictionary with keys as scan numbers and values as byte offsets  
    2. first_scan: the first scan number in the file  
    3. max_scan: the last scan number in the file  
    4. file_url: the file's URL  
    5. file_size: the file's size in bytes  
E.g. to access the scan_dict for a file, use all_scans[file_name][0].  
The populate_all_scans() method populates the scan_dict for a given file.  
Toggle between partial and full indexing via the partial_indexing attribute.  
The get_scan() method retrieves a specific scan from the file and returns it as a dictionary.  
get_scan() depends on populate_all_scans() since retrieves the desired scan's byte offset from all_scans

## Runtime
Based on 5 tests from 4 Zenodo databases. Using a wired connection with ~100Mbps.
### First Scan in a File
Average runtime: 12.08 seconds  
Median runtime: 10.29 seconds
### All Successive Scans in the File
Average Runtime: 0.78 seconds  
Median Runtime: 0.83 seconds  
(Data table coming soon)

## Valid Formats
The class is able to parse the following idRef formats:  
idRef="SPECTRUM_XXXX"  
idRef="controllerType=X controllerNumber=X scan=XXXX"