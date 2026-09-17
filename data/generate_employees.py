import csv
import random
from pathlib import Path

departments = ["IT", "HR", "Finance", "Sales", "Marketing"]
roles_by_department = {
    "IT": [
        "Software Developer",
        "Tester",
        "System Engineer",
        "Data Analyst"
    ],

    "HR": [
        "HR Executive",
        "HR Manager",
        "Recruiter"
    ],

    "Finance": [
        "Financial Analyst",
        "Accountant",
        "Finance Executive"
    ],

    "Sales": [
        "Sales Executive",
        "Sales Manager",
        "Business Development Executive"
    ],

    "Marketing": [
        "Marketing Executive",
        "Digital Marketing Executive",
        "Marketing Analyst"
    ]
}

locations = ["Bengaluru", "Mumbai", "Pune", "Hyderabad", "Chennai"]

statuses = ["Active", "Active", "Active", "On Leave", "Inactive"]

first_names = [
    "Rahul", "Priya", "Arun", "Sneha", "Ravi",
    "Anjali", "Kiran", "Neha", "Amit", "Pooja"
]

last_names = [
    "Kumar", "Sharma", "Patil", "Rao", "Singh",
    "Verma", "Reddy", "Nair", "Joshi", "Mehta"
]

def generate_employees(output_path=Path(__file__).with_name("employees.csv")):
    with open(output_path, "w", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)

        writer.writerow([
            "employee_id",
            "name",
            "department",
            "role",
            "location",
            "status"
        ])

        for i in range(1, 101):

            employee_id = f"EMP{i:03}"

            name = f"{random.choice(first_names)} {random.choice(last_names)}"

            department = random.choice(departments)

            role = random.choice(roles_by_department[department])

            location = random.choice(locations)

            status = random.choice(statuses)

            writer.writerow([
                employee_id,
                name,
                department,
                role,
                location,
                status
            ])

    print("100 employee records created successfully!")


if __name__ == "__main__":
    generate_employees()
