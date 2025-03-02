import requests
from pyteomics import mzml
import re


def get_scan(max_scan):
   scan = input(f"Enter a scan number between 1 and {max_scan} or type q to quit: ")
   if(scan == "q"):
      print("Exiting...")
      exit()
   return scan

url = "https://zenodo.org/records/10211590/files/D141_POS.mzML"
start_byte = 56_068_462 - 1_000_000
end_byte = 56_068_462 - 1
headers = {"Range": f"bytes={start_byte}-{end_byte}"}
response = requests.get(url, headers=headers, stream=True)
response.raise_for_status()

with open("indexed_part.mzML", "wb") as f:
   for chunk in response.iter_content(chunk_size=8192):
       f.write(chunk)
print("Downloaded indexed part of mzML")

with open("indexed_part.mzML", "r", encoding="utf-8") as f:
   text = f.read()

# If text contains <offset idRef="abc123">456</offset> then matches stores ('abc123', '456')
matches = re.findall(r'<offset idRef="([^"]+)">(\d+)</offset>', text)
scan_offsets = {scan_id: int(offset) for scan_id, offset in matches}
scan_list = list(scan_offsets.items())
print("Scan offsets found:", scan_list[:5])
last_key = None
for key in reversed(scan_offsets):
   if 'scan=' in key:
      last_key = key
      break
if last_key is None:
   raise ValueError("No key containing 'scan=' found in scan_offsets")
max_scan = int(last_key.split('scan=')[1].split(' ')[0])
while(True):
   desired_scan = get_scan(max_scan)
   while(not desired_scan.isdigit() or int(desired_scan) < 0 or int(desired_scan) > max_scan):
      print("Invalid scan number. Please enter a valid integer.")
      desired_scan = get_scan(max_scan)
   if desired_scan.startswith('0'):
      desired_scan = desired_scan.lstrip('0')
   print(f"Desired scan: {desired_scan}")
   end_scan = str(int(desired_scan) + 1)
   target_scan_id = "controllerType=0 controllerNumber=1 scan=" + desired_scan
   end_scan_id = "controllerType=0 controllerNumber=1 scan=" + end_scan
   scan_start = scan_offsets[target_scan_id]
   scan_end = scan_offsets[end_scan_id] - 10 if end_scan_id in scan_offsets else 10000

   # Request the specific scan range from the server
   headers = {"Range": f"bytes={scan_start}-{scan_end}"}
   response = requests.get(url, headers=headers, stream=True)
   response.raise_for_status()

   with open("target_scan.mzML", "wb") as f:
      for chunk in response.iter_content(chunk_size=8192):
         f.write(chunk)
   print(f"Downloaded scan {target_scan_id}")