import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

# Unit tests never need local credentials or a real Gemini client.
with patch("dotenv.load_dotenv"), patch("google.genai.Client"):
    from backend import employee_agent as agent


EMPLOYEE = {
    "employee_id": "EMP001",
    "name": "Asha",
    "department": "Sales",
    "role": "Sales Executive",
    "location": "Pune",
    "status": "Active",
}
DESTINATION = {"destinationConfiguration": {"URL": "https://employees.example/"}}


class EmployeeAgentTests(unittest.TestCase):
    def setUp(self):
        self.destination = self.enterContext(
            patch.object(agent, "get_btp_destination", return_value=DESTINATION)
        )
        self.get = self.enterContext(patch.object(agent.requests, "get"))
        self.client = self.enterContext(patch.object(agent, "client"))
        self.generate = self.client.models.generate_content
        self.generate.return_value = SimpleNamespace(text="Prepared answer")

    def test_all_employees_accepts_both_api_formats(self):
        for payload in ([EMPLOYEE], {"count": 1, "employees": [EMPLOYEE]}):
            with self.subTest(payload=payload):
                self.get.return_value = Mock(status_code=200)
                self.get.return_value.json.return_value = payload
                self.assertEqual(agent.get_all_employees(), [EMPLOYEE])
                self.get.assert_called_with(
                    "https://employees.example/employees", timeout=30
                )

    def test_all_employees_rejects_malformed_payloads(self):
        for payload in (None, {}, {"employees": None}, [None], "unavailable"):
            with self.subTest(payload=payload):
                self.get.return_value = Mock(status_code=200)
                self.get.return_value.json.return_value = payload
                self.assertIn("error", agent.get_all_employees())

    def test_missing_destination_or_url_does_not_call_api(self):
        for destination, message in (
            ({}, "destination configuration"),
            ({"destinationConfiguration": {"Name": "Employees"}}, "API URL"),
        ):
            with self.subTest(destination=destination):
                self.destination.return_value = destination
                self.assertIn(message, agent.get_all_employees()["error"])
        self.get.assert_not_called()

    def test_all_employees_reports_http_and_connection_errors(self):
        for status, message in ((401, "status 401"), (503, "temporarily unavailable")):
            with self.subTest(status=status):
                self.get.return_value = Mock(status_code=status)
                self.assertIn(message, agent.get_all_employees()["error"])
        for error, message in (
            (requests.Timeout(), "timed out"),
            (requests.ConnectionError("offline"), "connection error"),
            (ValueError("invalid data"), "Employee agent error"),
        ):
            with self.subTest(error=type(error).__name__):
                self.get.side_effect = error
                self.assertIn(message, agent.get_all_employees()["error"])

    def test_parallel_lookup_preserves_order_and_isolates_failures(self):
        second_finished = Event()

        def retrieve(employee_id):
            if employee_id == "EMP001":
                if not second_finished.wait(timeout=5):
                    raise RuntimeError("Lookups did not run concurrently")
                return EMPLOYEE
            second_finished.set()
            raise RuntimeError("Second employee unavailable")

        with patch.object(agent, "get_employee_details", side_effect=retrieve):
            result = agent.get_multiple_employee_details(["EMP001", "EMP002"])
        self.assertEqual(result, [EMPLOYEE, {"error": "Second employee unavailable"}])

    def test_parallel_lookup_accepts_empty_input(self):
        self.assertEqual(agent.get_multiple_employee_details([]), [])
        self.destination.assert_not_called()

    def test_analytics_reads_dataset_from_api(self):
        self.get.return_value = Mock(status_code=200)
        self.get.return_value.json.return_value = {"count": 1, "employees": [EMPLOYEE]}
        question = "How many Sales employees are Active?"
        self.assertEqual(agent.ask_employee_agent(question), "Prepared answer")
        prompt = self.generate.call_args.kwargs["contents"]
        for expected in (question, "Employee dataset:", "Asha", "Department: Sales"):
            self.assertIn(expected, prompt)

    def test_specific_employees_are_deduplicated_and_limited(self):
        ids = [f"EMP{number:03d}" for number in range(1, 13)]
        question = "Compare emp001, " + ", ".join(ids)
        with patch.object(agent, "get_multiple_employee_details") as multiple:
            multiple.return_value = [dict(EMPLOYEE, employee_id=value) for value in ids[:10]]
            self.assertEqual(agent.ask_employee_agent(question), "Prepared answer")
            multiple.assert_called_once_with(ids[:10])
        self.get.assert_not_called()

    def test_invalid_numeric_id_does_not_trigger_analytics(self):
        for question in ("Status of EMP12?", "Status of EMP1234?"):
            with self.subTest(question=question):
                self.assertIn("Invalid employee ID", agent.ask_employee_agent(question))
        self.destination.assert_not_called()
        self.generate.assert_not_called()

    def test_fallback_employee_id_is_normalized(self):
        self.get.return_value = Mock(status_code=200)
        self.get.return_value.json.return_value = EMPLOYEE
        self.assertEqual(agent.ask_employee_agent("What is their role?", " emp001 "), "Prepared answer")
        self.get.assert_called_once_with("https://employees.example/employees/EMP001", timeout=15)

    def test_partial_failures_are_shown_alongside_answer(self):
        with patch.object(agent, "get_multiple_employee_details", return_value=[
            {"error": "Employee EMP999 was not found."}, EMPLOYEE
        ]):
            answer = agent.ask_employee_agent("Compare EMP999 and EMP001")
        self.assertIn("Prepared answer", answer)
        self.assertIn("Employee EMP999 was not found.", answer)
        self.assertIn("Name: Asha", self.generate.call_args.kwargs["contents"])

    def test_unusable_lookups_do_not_call_ai(self):
        with patch.object(agent, "get_multiple_employee_details", return_value=[None, {}]):
            answer = agent.ask_employee_agent("Compare EMP001 and EMP002")
        self.assertIn("EMP001 could not be retrieved", answer)
        self.assertIn("EMP002 could not be retrieved", answer)
        self.generate.assert_not_called()

    def test_empty_or_failed_dataset_does_not_call_ai(self):
        for result, message in (([], "No employees"), ({"error": "Unavailable"}, "Unavailable")):
            with self.subTest(result=result):
                with patch.object(agent, "get_all_employees", return_value=result):
                    self.assertIn(message, agent.ask_employee_agent("Show all Sales employees"))
        self.generate.assert_not_called()

    def test_ai_failure_returns_friendly_message_and_preserves_lookup_error(self):
        self.generate.side_effect = RuntimeError("private service details")
        with patch.object(agent, "get_multiple_employee_details", return_value=[
            EMPLOYEE, {"error": "Employee EMP999 was not found."}
        ]):
            answer = agent.ask_employee_agent("Compare EMP001 and EMP999")
        self.assertIn("AI service could not prepare the response", answer)
        self.assertIn("Employee EMP999 was not found", answer)
        self.assertNotIn("private service details", answer)

    def test_empty_ai_response_is_reported(self):
        self.generate.return_value = SimpleNamespace(text=None)
        with patch.object(agent, "get_all_employees", return_value=[EMPLOYEE]):
            self.assertIn("AI service returned no answer", agent.ask_employee_agent("Count employees"))


class EmployeeStreamlitTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest

        self.enterContext(patch.object(agent, "get_btp_destination", return_value=DESTINATION))
        self.enterContext(patch.object(agent.requests, "get", side_effect=self.api_response))
        self.client = self.enterContext(patch.object(agent, "client"))
        self.client.models.generate_content.return_value = SimpleNamespace(text="Prepared answer")
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        self.app = AppTest.from_file(str(app_path), default_timeout=15).run()
        self.assertEqual(len(self.app.exception), 0)

    @staticmethod
    def api_response(url, **kwargs):
        response = Mock(status_code=200)
        if url.endswith("/employees"):
            response.json.return_value = {"count": 1, "employees": [EMPLOYEE]}
        elif url.endswith("/EMP001"):
            response.json.return_value = EMPLOYEE
        else:
            response.status_code = 404
        return response

    def submit(self, question):
        self.app.chat_input[0].set_value(question).run()
        self.assertEqual(len(self.app.exception), 0)
        return self.app.session_state["messages"][-1]["content"]

    def test_analytics_without_id_reaches_agent(self):
        self.assertEqual(self.submit("How many Sales employees are Active?"), "Prepared answer")
        self.assertIsNone(self.app.session_state["employee"])
        self.assertIn("Employee dataset:", self.client.models.generate_content.call_args.kwargs["contents"])

    def test_missing_first_employee_does_not_block_other_employees(self):
        answer = self.submit("Compare EMP999 and EMP001")
        self.assertIn("Prepared answer", answer)
        self.assertIn("Employee EMP999 was not found", answer)
        self.assertIsNone(self.app.session_state["employee"])

    def test_analytics_clears_previous_employee_card(self):
        self.submit("What is the status of EMP001?")
        self.assertEqual(self.app.session_state["employee"], EMPLOYEE)
        self.submit("Show all employees in Sales")
        self.assertIsNone(self.app.session_state["employee"])
        self.assertIn("Employee dataset:", self.client.models.generate_content.call_args.kwargs["contents"])

    def test_invalid_id_is_reported_in_chat(self):
        self.assertIn("Invalid employee ID", self.submit("What is the status of EMP12?"))
        self.client.models.generate_content.assert_not_called()


if __name__ == "__main__":
    unittest.main()
