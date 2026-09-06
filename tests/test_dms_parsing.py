import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tolerance_parser import ToleranceParser


class TestDMSParsing(unittest.TestCase):
    def setUp(self):
        self.parser = ToleranceParser()

    def test_compact_dms_four_digits(self):
        # 4°3023° -> 4 độ 30' 23"
        res = self.parser.parse("4°3023°")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4°30'23\"")
        self.assertEqual(res["tol_type"], "angle")
        self.assertEqual(res["full_callout"], "4°30'23\"")

    def test_compact_dms_without_trailing_deg(self):
        # 4°3023 -> 4°30'23"
        res = self.parser.parse("4°3023")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4°30'23\"")

    def test_compact_dms_three_digits(self):
        # 4°523° -> 4°5'23"
        res = self.parser.parse("4°523°")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4°5'23\"")

    def test_compact_dms_two_digits(self):
        # 4°30° -> 4°30'
        res = self.parser.parse("4°30°")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4°30'")

    def test_explicit_dms(self):
        # 4°30'23" and variants
        res = self.parser.parse("4°30'23\"")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4°30'23\"")

        res2 = self.parser.parse("4°30'23''")
        self.assertTrue(res2["success"])
        self.assertEqual(res2["nominal_str"], "4°30'23\"")

    def test_space_separated_dms(self):
        # 4° 30 23 -> 4°30'23"
        res = self.parser.parse("4° 30 23")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4°30'23\"")

    def test_boundary_values(self):
        # 60' and 60'' are maximum valid
        res = self.parser.parse("4°6060°")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4°60'60\"")

        # 61' > 60 -> invalid minutes, must reject 61
        res_invalid_min = self.parser.parse("4°6123°")
        self.assertTrue(res_invalid_min["success"])
        self.assertEqual(res_invalid_min["nominal_str"], "4°")

        # 65'' > 60 -> invalid seconds, must reject
        res_invalid_sec = self.parser.parse("4°3065°")
        self.assertTrue(res_invalid_sec["success"])
        self.assertEqual(res_invalid_sec["nominal_str"], "4°")

    def test_dms_with_symmetric_tolerance(self):
        # 4°3023° ± 10'
        res = self.parser.parse("4°3023° ± 10'")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4°30'23\"")
        self.assertEqual(res["upper_tol"], "+10'")
        self.assertEqual(res["lower_tol"], "-10'")
        self.assertEqual(res["tol_type"], "angle_tol")
        self.assertIn("±10'", res["full_callout"])

    def test_dms_with_asymmetric_tolerance(self):
        # 4°3023° +10' -5'
        res = self.parser.parse("4°3023° +10' -5'")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4°30'23\"")
        self.assertEqual(res["upper_tol"], "+10'")
        self.assertEqual(res["lower_tol"], "-5'")
        self.assertEqual(res["tol_type"], "angle_tol")

    def test_stacked_double_minus_tolerances(self):
        # Case: 4.94 with stacked -0.003 / -0.008
        res = self.parser.parse("4.94 -0.003 -0.008")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "4.94")
        self.assertEqual(res["upper_tol"], "-0.003")
        self.assertEqual(res["lower_tol"], "-0.008")
        self.assertEqual(res["full_callout"], "4.94 -0.003/-0.008")

        # Multiline variant: -0.003\n4.94\n-0.008
        res_multi = self.parser.parse("-0.003\n4.94\n-0.008")
        self.assertTrue(res_multi["success"])
        self.assertEqual(res_multi["nominal_str"], "4.94")
        self.assertEqual(res_multi["upper_tol"], "-0.003")
        self.assertEqual(res_multi["lower_tol"], "-0.008")

    def test_mechanical_tolerance_logic_and_inverted_artifacts(self):
        # Case from user: 0.24 +0.004 1000+
        # Nominal: 0.24 (unsigned, tol cannot be > nominal)
        # 1000+ -> +0.001
        res = self.parser.parse("0.24 +0.004 1000+")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "0.24")
        self.assertEqual(res["upper_tol"], "+0.004")
        self.assertEqual(res["lower_tol"], "+0.001")
        self.assertEqual(res["full_callout"], "0.24 +0.004/+0.001")

        # Inverted variants
        res_inv1 = self.parser.parse("0.24 +0.004 +1000")
        self.assertEqual(res_inv1["nominal_str"], "0.24")
        self.assertEqual(res_inv1["upper_tol"], "+0.004")
        self.assertEqual(res_inv1["lower_tol"], "+0.001")

        res_inv2 = self.parser.parse("0.24 +0.004 0001+")
        self.assertEqual(res_inv2["nominal_str"], "0.24")
        self.assertEqual(res_inv2["upper_tol"], "+0.004")
        self.assertEqual(res_inv2["lower_tol"], "+0.001")

        res_inv3 = self.parser.parse("0.24 +0.004 1000-")
        self.assertEqual(res_inv3["nominal_str"], "0.24")
        self.assertEqual(res_inv3["upper_tol"], "+0.004")
        self.assertEqual(res_inv3["lower_tol"], "-0.001")

    def test_stacked_unilateral_tolerance_artifacts(self):
        # Case: 41.42 -0.0-1 -> 41.42 0/-0.01
        res = self.parser.parse("41.42 -0.0-1")
        self.assertTrue(res["success"])
        self.assertEqual(res["nominal_str"], "41.42")
        self.assertEqual(res["upper_tol"], "0")
        self.assertEqual(res["lower_tol"], "-0.01")
        self.assertEqual(res["full_callout"], "41.42 0/-0.01")

        # Variances
        res2 = self.parser.parse("41.42 -0.0 -1")
        self.assertEqual(res2["nominal_str"], "41.42")
        self.assertEqual(res2["upper_tol"], "0")
        self.assertEqual(res2["lower_tol"], "-0.01")

        res3 = self.parser.parse("41.42 0 -1")
        self.assertEqual(res3["nominal_str"], "41.42")
        self.assertEqual(res3["upper_tol"], "0")
        self.assertEqual(res3["lower_tol"], "-0.01")

        res4 = self.parser.parse("41.42 -0.01")
        self.assertEqual(res4["nominal_str"], "41.42")
        self.assertEqual(res4["upper_tol"], "0")
        self.assertEqual(res4["lower_tol"], "-0.01")

        res5 = self.parser.parse("50.25 -0.0-2")
        self.assertEqual(res5["nominal_str"], "50.25")
        self.assertEqual(res5["upper_tol"], "0")
        self.assertEqual(res5["lower_tol"], "-0.02")
        self.assertEqual(res5["full_callout"], "50.25 0/-0.02")

    def test_local_auto_detect_functionality(self):
        from pdf_processor import PDFProcessor
        processor = PDFProcessor()
        pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "107-M1457.pdf"))
        if os.path.exists(pdf_path):
            result = processor.local_auto_detect(pdf_path, page_num=0, dpi=200)
            self.assertTrue(result["success"])
            self.assertGreater(result["count"], 5)
            # Check presence of major dimensions
            callouts = [d["full_callout"] for d in result["dimensions"]]
            has_494 = any("4.94" in c for c in callouts)
            self.assertTrue(has_494, "Should detect 4.94 dimension in 107-M1457")

    def test_ocr_device_switching(self):
        from pdf_processor import get_ocr_device_info, set_ocr_device
        from fastapi.testclient import TestClient
        from app import app

        info = get_ocr_device_info()
        self.assertIn("current_device", info)
        self.assertIn("dml_available", info)

        # Test switching to CPU
        cpu_res = set_ocr_device("cpu")
        self.assertTrue(cpu_res["success"])
        self.assertEqual(cpu_res["current_device"], "cpu")

        # Test API GET and POST
        client = TestClient(app)
        resp = client.get("/api/ocr/device")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["current_device"], "cpu")

        if info["dml_available"]:
            gpu_res = set_ocr_device("gpu")
            self.assertTrue(gpu_res["success"])
            self.assertEqual(gpu_res["current_device"], "gpu")

            resp_post = client.post("/api/ocr/device", json={"device": "gpu"})
            self.assertEqual(resp_post.status_code, 200)
            self.assertEqual(resp_post.json()["current_device"], "gpu")


if __name__ == "__main__":
    unittest.main()
