from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
import csv
import os
import re

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

app = Flask(__name__)
CORS(app)

# Find employees.csv
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "..", "data", "employees.csv")
REQUIRED_COLUMNS = ("employee_id", "name", "department", "role", "location", "status")


class EmployeeDataError(Exception):
    """The employee data source cannot be read or is invalid."""


@app.errorhandler(EmployeeDataError)
def handle_employee_data_error(error):
    app.logger.error("Employee data error: %s", error)
    return jsonify({"message": "Employee data is unavailable. Check data/employees.csv."}), 503


def load_employees():
    employees = []

    try:
        with open(CSV_FILE, mode="r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, strict=True)
            if not reader.fieldnames or not set(REQUIRED_COLUMNS).issubset(reader.fieldnames):
                raise EmployeeDataError("Missing required CSV columns")
            seen_ids = set()
            for row in reader:
                if None in row or any(not row.get(key) or not row[key].strip() for key in REQUIRED_COLUMNS):
                    raise EmployeeDataError(f"Invalid employee record at line {reader.line_num}")
                employee = {key: row[key].strip() for key in REQUIRED_COLUMNS}
                employee_id = employee["employee_id"].casefold()
                if employee_id in seen_ids:
                    raise EmployeeDataError(f"Duplicate employee ID at line {reader.line_num}")
                seen_ids.add(employee_id)
                employees.append(employee)
    except (OSError, UnicodeError, csv.Error) as error:
        raise EmployeeDataError(str(error)) from error

    return employees


# Home route
@app.route("/")
def home():
    return jsonify({
        "message": "Employee Information & Status Assistant API is running"
    })


# Get all employees
@app.route("/employees", methods=["GET"])
def get_employees():

    employees = load_employees()

    department = request.args.get("department", "").strip()
    location = request.args.get("location", "").strip()
    status = request.args.get("status", "").strip()

    if department:
        employees = [
            emp for emp in employees
            if emp["department"].lower() == department.lower()
        ]

    if location:
        employees = [
            emp for emp in employees
            if emp["location"].lower() == location.lower()
        ]

    if status:
        employees = [
            emp for emp in employees
            if emp["status"].lower() == status.lower()
        ]

    return jsonify({
        "count": len(employees),
        "employees": employees
    })


# Get employee by employee ID
@app.route("/employees/<employee_id>", methods=["GET"])
def get_employee(employee_id):

    employees = load_employees()

    for employee in employees:

        if employee["employee_id"].lower() == employee_id.lower():
            return jsonify(employee)

    return jsonify({
        "message": "Employee not found"
    }), 404


@app.route("/ai/chat", methods=["POST"])
def ai_chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("message", ""), str):
        return jsonify({"error": "Message must be a string"}), 400
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message is required"}), 400

    # Find an employee ID such as EMP001
    match = re.search(r"\bEMP\d+\b", message, re.IGNORECASE)

    if not match:
        return jsonify({
            "reply": "Please provide an employee ID, for example EMP001."
        })

    employee_id = match.group(0).upper()

    employees = load_employees()
    employee = next(
        (
            emp for emp in employees
            if emp["employee_id"].upper() == employee_id
        ),
        None
    )

    if not employee:
        return jsonify({
            "reply": f"I could not find employee {employee_id}."
        }), 404

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key in {"your_actual_gemini_key", "your_api_key_here"}:
        return jsonify({"error": "Set GEMINI_API_KEY to enable AI chat"}), 503

    try:
        with genai.Client(api_key=api_key) as client:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
                config={"system_instruction": (
                    "You are an Employee Information Assistant. "
                    "Answer only using the employee information provided. "
                    "Keep the answer clear and concise."
                )},
                contents=f"""
User question: {message}

Employee information:
Employee ID: {employee['employee_id']}
Name: {employee['name']}
Department: {employee['department']}
Role: {employee['role']}
Location: {employee['location']}
Status: {employee['status']}
"""
            )

        if not response.text:
            return jsonify({"error": "AI service returned no text"}), 502

        return jsonify({
            "employee": employee,
            "reply": response.text
        })

    except Exception as error:
        app.logger.error("Gemini request failed (%s)", type(error).__name__)
        return jsonify({
            "error": "AI service failed"
        }), 500


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
