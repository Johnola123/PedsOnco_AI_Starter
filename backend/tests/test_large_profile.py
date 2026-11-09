import io
from unittest.mock import patch
from app import profiling

class FakeS3:
    def head_object(self, **kwargs):
        return {"ContentLength": 243 * 1024 * 1024}
    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(b"patient_id,disease\np01,Neuroblastoma\np02,Neuroblastoma\n")}

def test_large_csv_uses_sample_not_413():
    with patch.object(profiling, 'get_s3_client', return_value=FakeS3()):
        result = profiling.profile_dataset('test.csv', 'test.csv')
    assert result['profile_mode'] == 'bounded_stream_sample'
    assert result['tables'][0]['fields'][0]['name'] == 'patient_id'
    assert result['row_count_complete'] is False

def test_large_json_is_metadata_only_not_error():
    with patch.object(profiling, 'get_s3_client', return_value=FakeS3()):
        result = profiling.profile_dataset('test.json', 'test.json')
    assert result['profile_mode'] == 'metadata_only'
