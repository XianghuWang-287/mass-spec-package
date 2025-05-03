import re
import requests
import numpy as np
from pyteomics import mzml
import matplotlib.pyplot as plt
import scipy.signal as signal

database = 10211590

class mzml_repo:
   def __init__(self, databaseNum):
      self.database_num = databaseNum
      self.file_names = []
      self.all_files = {}
      self.all_scans = {}

   def get_files(self):
      if self.file_names != []:
         print("File names already retrieved.")
         return self.file_names
      request_url = f"https://zenodo.org/api/records/{self.database_num}"
      response = requests.get(request_url)
      response.raise_for_status()
      data = response.json()

      # Loop through the files to find a .mzML file
      self.all_files = {file['key']: file['size'] for file in data['files'] if file['key'].endswith('.mzML')}
      file_url = None
      file_size = 0
      print("Available files:")
      for file, size in self.all_files.items():
         if size < 1024:
            size_str = f"{size} bytes"
         elif size < 1024**2:
            size_str = f"{size / 1024:.2f} KB"
         elif size < 1024**3:
            size_str = f"{size / 1024**2:.2f} MB"
         else:
            size_str = f"{size / 1024**3:.2f} GB"
         print(f"{file} ({size_str})")
         self.all_files[file] = size
      self.file_names = list(self.all_files.keys())
      return self.file_names

   # Create an entry in all_scans for each file and a list of its offsets
   def populate_all_scans_full(self, file_name):
      if file_name not in self.file_names:
         raise ValueError("File not found in the database.")
      file_url = f"https://zenodo.org/record/{database}/files/{file_name}"
      file_size = self.all_files[file_name]
      if not file_url:
         raise ValueError("No .mzML file found in the provided Zenodo database.")

      start_byte = file_size - 250000
      end_byte = file_size - 1
      headers = {"Range": f"bytes={start_byte}-{end_byte}"}
      response = requests.get(file_url, headers=headers, stream=True)
      response.raise_for_status()

      with open("indexed_part.mzML", "wb") as f:
         for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

      while True:
         with open("indexed_part.mzML", "r", encoding="utf-8") as f:
            text = f.read()

         if "</mzML>" in text:
            break

         start_byte = max(0, start_byte - 250000)
         headers = {"Range": f"bytes={start_byte}-{end_byte}"}
         response = requests.get(file_url, headers=headers, stream=True)
         response.raise_for_status()

         with open("indexed_part.mzML", "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
               f.write(chunk)

      # If text contains <offset idRef="abcd scan=123">456</offset> then matches stores ('abcd scan=123', '456')
      matches = re.findall(r'<offset idRef="([^"]+)">(\d+)</offset>', text)
      # scan_dict stores [123] = 456
      scan_dict = {int(scan_id.split('scan=')[1]): int(offset) for scan_id, offset in matches if 'scan=' in scan_id}
      # scan_numbers = [int(scan_id.split('scan=')[1]) for scan_id in scan_offsets.keys() if 'scan=' in scan_id]
      first_scan = list(scan_dict.keys())[0] if scan_dict else None
      max_scan = list(scan_dict.keys())[-1] if scan_dict else None
      if max_scan is None:
         raise ValueError("No key containing 'scan=' found in scan_dict")
      self.all_scans[file_name] = (scan_dict, first_scan, max_scan, file_url, file_size)
   
   # Create an entry in all_scans for each file and a list of its offsets, but only up until the given scan number is read
   def populate_all_scans_partial(self, file_name, scan_number):
      if file_name not in self.file_names:
         raise ValueError("File not found in the database.")
      file_url = f"https://zenodo.org/record/{database}/files/{file_name}"
      file_size = self.all_files[file_name]
      if not file_url:
         raise ValueError("No .mzML file found in the provided Zenodo database.")
      
      start_byte = file_size - 250000
      end_byte = file_size - 1
      headers = {"Range": f"bytes={start_byte}-{end_byte}"}
      response = requests.get(file_url, headers=headers, stream=True)
      response.raise_for_status()

      with open("indexed_part.mzML", "wb") as f:
         for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
      
      with open("indexed_part.mzML", "r", encoding="utf-8") as f:
            text = f.read()
      # If text contains <offset idRef="abcd scan=123">456</offset> then matches stores ('abcd scan=123', '456')
      matches = re.findall(r'<offset idRef="([^"]+)">(\d+)</offset>', text)
      # scan_dict stores [123] = 456
      scan_dict = {int(scan_id.split('scan=')[1]): int(offset) for scan_id, offset in matches if 'scan=' in scan_id}
      while scan_number not in scan_dict:
         if "</mzML>" in text:
            break
         start_byte = max(0, start_byte - 250000)
         headers = {"Range": f"bytes={start_byte}-{end_byte}"}
         response = requests.get(file_url, headers=headers, stream=True)
         response.raise_for_status()

         with open("indexed_part.mzML", "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
               f.write(chunk)
         with open("indexed_part.mzML", "r", encoding="utf-8") as f:
            text = f.read()
         new_matches = re.findall(r'<offset idRef="([^"]+)">(\d+)</offset>', text)
         new_matches.extend(matches)
         matches = new_matches
         scan_dict = {int(scan_id.split('scan=')[1]): int(offset) for scan_id, offset in matches if 'scan=' in scan_id}

      first_scan = list(scan_dict.keys())[0] if scan_dict else None
      max_scan = list(scan_dict.keys())[-1] if scan_dict else None
      if max_scan is None:
         raise ValueError("No key containing 'scan=' found in scan_dict")
      if not(self.all_scans.get(file_name) and self.all_scans[file_name][1] <= first_scan):
         self.all_scans[file_name] = (scan_dict, first_scan, max_scan, file_url, file_size)
   
   def populate_all_scans(self, file_name, scan_number, partial_indexing=True):
      if partial_indexing:
         self.populate_all_scans_partial(file_name, scan_number)
      else:
         self.populate_all_scans_full(file_name)

   # If a file is in all_scans already, return the scan. If not, call populate_all_scans first.
   def get_scan(self, file_name, given_scan):
      if(file_name not in self.file_names):
         raise ValueError("File not found in the database.")
      if given_scan not in self.all_scans.get(file_name, {}).get(0, {}):
         print(f"Scan {given_scan} not found in all_scans for {file_name}.\nPopulating all scans...")
         self.populate_all_scans(file_name, given_scan)

      scan_dict = self.all_scans[file_name][0]
      scan_numbers = list(scan_dict.keys())
      max_scan = self.all_scans[file_name][2]
      file_url = self.all_scans[file_name][3]
      file_size = self.all_scans[file_name][4]
      desired_scan = str(given_scan)
      if desired_scan.startswith('0'):
         desired_scan = desired_scan.lstrip('0')
      if(desired_scan.isdigit() and (0 <= int(desired_scan) <= max_scan)):
         if int(desired_scan) not in scan_numbers:
            print(f"Scan {desired_scan} not found. Please try again.")
            return
      else:
         print(f"Not a valid scan number. Please try again.")
         return
      next_scan_number = None
      for scan_num in scan_numbers[1:]:
         if scan_num > int(desired_scan):
            next_scan_number = scan_num
            break
      end_scan_id = next_scan_number
      scan_start = scan_dict[given_scan]
      scan_end = scan_dict[end_scan_id] - 10 if end_scan_id else file_size - 1

      # Request the specific scan range from the server
      headers = {"Range": f"bytes={scan_start}-{scan_end}"}
      response = requests.get(file_url, headers=headers, stream=True)
      response.raise_for_status()

      with open("target_scan.mzML", "wb") as f:
         for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
      print(f"Downloaded scan {desired_scan}")

      # If searching the last index, ensure the file cuts off exactly at </spectrum>
      if not end_scan_id:
         with open("target_scan.mzML", "rb+") as f:
            f.seek(0, 2)  # Move to the end of the file
            target_size = f.tell()
            f.seek(0)  # Move back to the start of the file
            content = f.read(target_size).decode("utf-8", errors="ignore")
            last_spectrum_end = content.rfind("</spectrum>")
            if last_spectrum_end != -1:
               f.seek(last_spectrum_end + len("</spectrum>"))
               f.truncate()

      with mzml.read("target_scan.mzML") as reader:
         for spectrum in reader:
            mz_values = spectrum['m/z array']
            intensity_values = spectrum['intensity array']
            retention_time = spectrum.get('scanList', {}).get('scan', [{}])[0].get('scan start time', 'N/A')
            charge_state = spectrum.get('precursorList', {}).get('precursor', [{}])[0].get('selectedIonList', {}).get('selectedIon', [{}])[0].get('charge state', 'N/A')
            collision_energy = spectrum.get('precursorList', {}).get('precursor', [{}])[0].get('activation', {}).get('collision energy', 'N/A')
            ms_level = spectrum.get('ms level', 'N/A')

            print(f"Retention time: {retention_time} seconds")
            print(f"Charge state: {charge_state}")
            print(f"Collision energy: {collision_energy}")
            print(f"MS level: {ms_level}")


            max_intensity = max(intensity_values)
            normalized_intensities = intensity_values / max_intensity # Normalize the intensities
            # peak_indices, _ = signal.find_peaks(normalized_intensities, prominence=0.05)
            filtered_mz = mz_values
            filtered_intensity = normalized_intensities

            # Plot the filtered peaks as a bar graph
            plt.figure(figsize=(10, 6))
            plt.bar(filtered_mz, filtered_intensity, width=1.0, color='blue', alpha=0.7)
            plt.xlabel('m/z')
            plt.ylabel('Intensity')
            plt.title(f'Filtered Peaks for Scan {desired_scan}')

      # Return scan as a dictionary
      scan_data = {
            'mz': filtered_mz,
            'intensities': filtered_intensity,
            'RT-time': retention_time,
            'charge': charge_state,
            'collision energy': collision_energy,
            'ms level': ms_level
      }
      plt.show()
      plt.close()
      return scan_data

given_scan = 8312
test_repo = mzml_repo(database)
file_name = test_repo.get_files()[0]
scan1 = test_repo.get_scan(file_name, given_scan)
print(f"Scan {given_scan}'s data: {scan1}")
# User will keep calling get_scan() to populate their own scan list