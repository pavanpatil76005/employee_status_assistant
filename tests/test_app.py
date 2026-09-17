import csv
import importlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend import app as api


class EmployeeApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.csv_path = Path(self.directory.name) / "employees.csv"
        self.csv_path.write_text(
            "employee_id,name,department,role,location,status\n"
            "EMP001,Asha,IT,Tester,Pune,Active\n"
            "EMP002,Ravi,HR,HR Executive,Mumbai,On Leave\n",
            encoding="utf-8",
        )
        patcher = patch.object(api, "CSV_FILE", self.csv_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = api.app.test_client()

    def test_home_and_all_employees(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/employees").json["count"], 2)

    def test_filters(self):
        for query in ({"department": " it "}, {"location": "pune"},
                      {"status": "active"},
                      {"department": "IT", "location": "Pune", "status": "Active"}):
            with self.subTest(query=query):
                response = self.client.get("/employees", query_string=query)
                self.assertEqual(response.json["count"], 1)
                self.assertEqual(response.json["employees"][0]["employee_id"], "EMP001")
        self.assertEqual(self.client.get("/employees?department=Unknown").json["count"], 0)

    def test_employee_lookup_and_missing_id(self):
        self.assertEqual(self.client.get("/employees/emp001").json["name"], "Asha")
        self.assertEqual(self.client.get("/employees/unknown").status_code, 404)

    def test_utf8_bom(self):
        content = self.csv_path.read_text(encoding="utf-8")
        self.csv_path.write_text(content, encoding="utf-8-sig")
        self.assertEqual(self.client.get("/employees/EMP001").status_code, 200)

    def test_missing_file_returns_json(self):
        self.csv_path.unlink()
        for url in ("/employees", "/employees/EMP001"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 503)
            self.assertTrue(response.is_json)

    def test_invalid_data_returns_json(self):
        header = "employee_id,name,department,role,location,status\n"
        record = "EMP001,Asha,IT,Tester,Pune,Active\n"
        for content in ("", "employee_id,name\nEMP001,Asha\n",
                        header + "EMP001,Asha\n", header + record + record,
                        header + "EMP001,Asha,IT,Tester,Pune,Active,extra\n"):
            with self.subTest(content=content):
                self.csv_path.write_text(content, encoding="utf-8")
                response = self.client.get("/employees")
                self.assertEqual(response.status_code, 503)
                self.assertTrue(response.is_json)

    def test_header_only_file_is_empty_list(self):
        self.csv_path.write_text(",".join(api.REQUIRED_COLUMNS) + "\n", encoding="utf-8")
        self.assertEqual(self.client.get("/employees").json, {"count": 0, "employees": []})

    def test_generator_import_does_not_write_and_output_is_valid(self):
        with patch("builtins.open", side_effect=AssertionError("Import must not write files")):
            generator = importlib.import_module("data.generate_employees")
            importlib.reload(generator)
        generator.generate_employees(self.csv_path)
        with self.csv_path.open(encoding="utf-8", newline="") as file:
            employees = list(csv.DictReader(file))
        self.assertEqual(len(employees), 100)
        self.assertEqual(len({row["employee_id"] for row in employees}), 100)
        self.assertEqual(self.client.get("/employees").json["count"], 100)


if __name__ == "__main__":
    unittest.main()
