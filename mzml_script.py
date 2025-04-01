import re
import requests
import numpy as np
from pyteomics import mzml
import matplotlib.pyplot as plt
import scipy.signal as signal

database = 10211590

def scan_user_input(max_scan):
   scan = input(f"Enter a scan number between 1 and {max_scan} or type q to quit: ")
   if(scan.lower() == "q" or scan.lower() == "quit"):
      print("Exiting...")
      exit()
   return scan

def mzml_scan(databaseNum):
   # database = input("Enter the Zenodo database ID (e.g., 1234567): ")
   # if(database == 'q' or database == 'quit'):
   #    print("Exiting...")
   #    exit()
   # while not database.isdigit():
   #    print("Invalid input. Please enter a numeric database ID.")
   #    database = input("Enter the Zenodo database ID (e.g., 1234567): ")
   request_url = f"https://zenodo.org/api/records/{databaseNum}"
   response = requests.get(request_url)
   response.raise_for_status()
   data = response.json()

   # Loop through the files to find a .mzML file
   available_files = {file['key']: file['size'] for file in data['files'] if file['key'].endswith('.mzML')}
   file_url = None
   file_size = 0
   print("Available files:")
   for file, size in available_files.items():
      if size < 1024:
         size_str = f"{size} bytes"
      elif size < 1024**2:
         size_str = f"{size / 1024:.2f} KB"
      elif size < 1024**3:
         size_str = f"{size / 1024**2:.2f} MB"
      else:
         size_str = f"{size / 1024**3:.2f} GB"
      print(f"{file} ({size_str})")
   file_name = input("Enter the file you want to process: ")
   if file_name in available_files:
      file_url = f"https://zenodo.org/record/{database}/files/{file_name}"
      file_size = available_files[file_name]
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

   # If text contains <offset idRef="abc123">456</offset> then matches stores ('abc123', '456')
   matches = re.findall(r'<offset idRef="([^"]+)">(\d+)</offset>', text)
   scan_offsets = {scan_id: int(offset) for scan_id, offset in matches}
   scan_numbers = [int(scan_id.split('scan=')[1]) for scan_id in scan_offsets.keys() if 'scan=' in scan_id]
   last_key = None
   for key in reversed(scan_offsets):
      if 'scan=' in key:
         last_key = key
         break
   if last_key is None:
      raise ValueError("No key containing 'scan=' found in scan_offsets")
   max_scan = int(last_key.split('scan=')[1])

   while(True):
      desired_scan = scan_user_input(max_scan)
      while(not(desired_scan.isdigit() and (0 <= int(desired_scan) <= max_scan) and int(desired_scan) in scan_numbers)):
         if(desired_scan.isdigit() and (0 <= int(desired_scan) <= max_scan)):
            print(f"Scan {desired_scan} not found. Please try again.")
         else:
            print("Invalid scan number. Please enter a valid integer.")
         desired_scan = scan_user_input(max_scan)
      if desired_scan.startswith('0'):
         desired_scan = desired_scan.lstrip('0')
      print(f"Desired scan: {desired_scan}")
      target_scan_id = "controllerType=0 controllerNumber=1 scan=" + desired_scan
      next_scan_number = None
      for scan_num in scan_numbers[1:]:
         if scan_num > int(desired_scan):
            next_scan_number = scan_num
            break
      end_scan_id = "controllerType=0 controllerNumber=1 scan=" + str(next_scan_number) if next_scan_number else None
      scan_start = scan_offsets[target_scan_id]
      scan_end = scan_offsets[end_scan_id] - 10 if end_scan_id else file_size - 1

      # Request the specific scan range from the server
      headers = {"Range": f"bytes={scan_start}-{scan_end}"}
      response = requests.get(file_url, headers=headers, stream=True)
      response.raise_for_status()

      with open("target_scan.mzML", "wb") as f:
         for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
      print(f"Downloaded scan {target_scan_id}")

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
            # print(f"m/z values: {mz_values}")
            # print(f"Intensity values: {intensity_values}")
            retention_time = spectrum.get('scanList', {}).get('scan', [{}])[0].get('scan start time', 'N/A')
            charge_state = spectrum.get('precursorList', {}).get('precursor', [{}])[0].get('selectedIonList', {}).get('selectedIon', [{}])[0].get('charge state', 'N/A')
            collision_energy = spectrum.get('precursorList', {}).get('precursor', [{}])[0].get('activation', {}).get('collision energy', 'N/A')
            ms_level = spectrum.get('ms level', 'N/A')

            print(f"Retention time: {retention_time} seconds")
            print(f"Charge state: {charge_state}")
            print(f"Collision energy: {collision_energy}")
            print(f"MS level: {ms_level}")

            #Filter peaks and plot as bar graph here
            
            plt.figure(figsize=(10, 6))
            plt.plot(mz_values, intensity_values)
            plt.xlabel('m/z')
            plt.ylabel('Intensity')
            plt.title(f'Scan {desired_scan}')
      plt.show()

mzml_scan(database)