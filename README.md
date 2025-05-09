# mass-spec-package
## A Python package for mass spectrometry.
Developed by Akshay Jay.\n
Use case: create an mzml_repo object. After propviding a Zenodo database ID, the object stores the name, URL, and size of all files in the database.
Requesting a scan from the file will provide the scan's mz and intensity values along with other metadata. If not already in memory, calling get_scan() will store the byte offets of that scan and all scans that come after it.