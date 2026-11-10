import json
import unittest

from backend.schemas import parse_telemetry
from backend.tests.support import fixture, validated


class ValidationTests(unittest.TestCase):
    def test_all_three_assignments(self):
        for board in range(1, 4):
            self.assertEqual(len(validated(fixture(board)).slots), 4)

    def test_unsynchronized_and_mixed_startup(self):
        data = fixture()
        data.update(timestamp=None, clock_synced=False)
        for slot in data["slots"]:
            slot["timestamp"] = None
        self.assertFalse(validated(data).clock_synced)
        data.update(timestamp=fixture()["timestamp"], clock_synced=True)
        self.assertTrue(validated(data).clock_synced)

    def test_unknown_and_distance_boundaries(self):
        for distance in [2, 20, 400]:
            data = fixture(); data["slots"][0]["distance_cm"] = distance
            self.assertEqual(validated(data).slots[0].distance_cm, distance)
        data["slots"][0].update(distance_cm=None, occupancy_status="UNKNOWN")
        self.assertIsNone(validated(data).slots[0].distance_cm)

    def test_reject_invalid_root_fields(self):
        for field, value in [("sequence", True),("sequence",-1),("sequence",2**32),
                             ("uptime_ms","5"),("schema_version",2),("device_id","esp32_04"),
                             ("clock_synced",False),("timestamp","2026-11-10T10:00:00+00:00"),
                             ("timestamp","2026-02-30T10:00:00Z")]:
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                data=fixture(); data[field]=value; validated(data)

    def test_reject_invalid_slot_fields(self):
        for field,value in [("distance_cm",True),("distance_cm","10"),("distance_cm",float("nan")),
                            ("distance_cm",1.9),("distance_cm",401),("distance_cm",None),
                            ("occupancy_status","FREE"),("occupancy_status","UNKNOWN"),
                            ("timestamp","yesterday"),("slot_id","P12")]:
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                data=fixture(); data["slots"][0][field]=value; validated(data)

    def test_reject_duplicate_missing_and_extra_slots(self):
        data=fixture(); data["slots"][0]=data["slots"][1]
        with self.assertRaises(ValueError): validated(data)
        for count in [0,3,5]:
            data=fixture(); data["slots"]=(data["slots"]*2)[:count]
            with self.assertRaises(ValueError): validated(data)

    def test_topic_mismatch_and_extra_fields(self):
        with self.assertRaises(ValueError): parse_telemetry(json.dumps(fixture()).encode(),"esp32_02")
        data=fixture(); data["secret"]="not accepted"
        with self.assertRaises(ValueError): validated(data)

    def test_malformed_oversized_duplicate_json(self):
        for raw in [b"",b"{",b"null",b"\xff",b"x"*4097,b'{"x":1,"x":2}',b'{"x":NaN}']:
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                parse_telemetry(raw,"esp32_01")
