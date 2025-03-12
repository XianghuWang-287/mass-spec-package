import mzml_script
import unittest
from unittest.mock import patch, mock_open, MagicMock

class TestMzmlScript(unittest.TestCase):

    @patch('builtins.input', side_effect=['1234567', 'test.mzML', '1', 'q'])
    @patch('requests.get')
    def test_mzml_scan(self, mock_get, mock_input):
        # Mock the response from Zenodo API
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'files': [{'key': 'test.mzML', 'size': 1024}]
        }
        mock_response.iter_content = lambda chunk_size: [b'data']
        mock_get.return_value = mock_response

        # Mock the open function to simulate file reading/writing
        with patch('builtins.open', mock_open(read_data='<offset idRef="controllerType=0 controllerNumber=1 scan=1">100</offset>')):
            with patch('mzml_script.mzml.read', return_value=[{
                'm/z array': [100, 200, 300],
                'intensity array': [10, 20, 30],
                'scanList': {'scan': [{'scan start time': 5.0}]},
                'precursorList': {'precursor': [{'selectedIonList': {'selectedIon': [{'charge state': 2}]}, 'activation': {'collision energy': 35.0}}]},
                'ms level': 2
            }]):
                mzml_script.mzml_scan()

if __name__ == '__main__':
    unittest.main()
