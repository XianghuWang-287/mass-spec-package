import unittest
from unittest.mock import patch, MagicMock
from mzml_script import mzml_repo

class TestMzmlRepo(unittest.TestCase):
    def setUp(self):
        self.database_num = 10211590
        self.repo = mzml_repo(self.database_num)

    @patch('mzml_script.requests.get')
    def test_get_files(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'files': [
                {'key': 'file1.mzML', 'size': 1024},
                {'key': 'file2.txt', 'size': 2048},
                {'key': 'file3.mzML', 'size': 512}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        file_names = self.repo.get_files()
        self.assertIn('file1.mzML', file_names)
        self.assertIn('file3.mzML', file_names)
        self.assertNotIn('file2.txt', file_names)

    @patch('mzml_script.requests.get')
    @patch('builtins.open', new_callable=MagicMock)
    def test_populate_all_scans(self, mock_open, mock_get):
        self.repo.file_names = ['file1.mzML']
        self.repo.all_files = {'file1.mzML': 1000000}

        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"<offset idRef=\"scan=1\">100</offset>", b"</mzML>"]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        self.repo.populate_all_scans('file1.mzML')
        self.assertIn('file1.mzML', self.repo.all_scans)
        self.assertEqual(self.repo.all_scans['file1.mzML'][1], 1)  # max_scan

    @patch('mzml_script.requests.get')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('mzml_script.mzml.read')
    def test_get_scan(self, mock_mzml_read, mock_open, mock_get):
        self.repo.file_names = ['file1.mzML']
        self.repo.all_scans = {
            'file1.mzML': (
                {1: 100, 2: 200},
                2,
                'https://zenodo.org/record/10211590/files/file1.mzML',
                1000000
            )
        }

        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"<spectrum></spectrum>"]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        mock_mzml_read.return_value.__enter__.return_value = iter([
            {
                'm/z array': [100, 200, 300],
                'intensity array': [10, 20, 30],
                'scanList': {'scan': [{'scan start time': 5.0}]},
                'precursorList': {'precursor': [{'selectedIonList': {'selectedIon': [{'charge state': 2}]}, 'activation': {'collision energy': 35.0}}]},
                'ms level': 2
            }
        ])

        self.repo.get_scan('file1.mzML', 1)
        mock_open.assert_called()
        mock_get.assert_called()
        mock_mzml_read.assert_called()

if __name__ == '__main__':
    unittest.main()
