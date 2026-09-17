const API_URL = "https://employee-status-pavan-2026-a6hmdrg0feh8cgb5.indiasouthcentral-01.azurewebsites.net";


async function searchEmployee() {

    const employeeId =
        document.getElementById("employeeId").value.trim();

    const result =
        document.getElementById("employeeResult");

    const list =
        document.getElementById("employeeList");

    const message =
        document.getElementById("message");

    list.innerHTML = "";
    message.innerHTML = "";

    if (employeeId === "") {

        message.innerHTML =
            "<p class='error'>Please enter an Employee ID.</p>";

        return;
    }

    try {

        const response =
            await fetch(`${API_URL}/employees/${employeeId}`);

        if (!response.ok) {

            result.innerHTML = "";

            message.innerHTML =
                "<p class='error'>Employee not found.</p>";

            return;
        }

        const employee = await response.json();

        result.innerHTML = `
            <div class="employee-card">

                <h2>${employee.name}</h2>

                <p>
                    <strong>Employee ID:</strong>
                    ${employee.employee_id}
                </p>

                <p>
                    <strong>Department:</strong>
                    ${employee.department}
                </p>

                <p>
                    <strong>Role:</strong>
                    ${employee.role}
                </p>

                <p>
                    <strong>Location:</strong>
                    ${employee.location}
                </p>

                <p>
                    <strong>Status:</strong>
                    ${employee.status}
                </p>

            </div>
        `;

    } catch (error) {

        message.innerHTML =
            "<p class='error'>Cannot connect to backend.</p>";

    }
}


async function filterEmployees() {

    const department =
        document.getElementById("department").value;

    const location =
        document.getElementById("location").value;

    const status =
        document.getElementById("status").value;

    let url = `${API_URL}/employees?`;

    const params = new URLSearchParams();

    if (department) {
        params.append("department", department);
    }

    if (location) {
        params.append("location", location);
    }

    if (status) {
        params.append("status", status);
    }

    url += params.toString();

    loadEmployees(url);
}


async function loadAllEmployees() {

    loadEmployees(`${API_URL}/employees`);

}


async function loadEmployees(url) {

    const result =
        document.getElementById("employeeResult");

    const list =
        document.getElementById("employeeList");

    const message =
        document.getElementById("message");

    result.innerHTML = "";
    message.innerHTML = "";

    try {

        const response = await fetch(url);

        const data = await response.json();

        if (data.employees.length === 0) {

            list.innerHTML =
                "<p class='error'>No employees found.</p>";

            return;
        }

        let table = `

            <p class="success">
                Employees Found: ${data.count}
            </p>

            <table>

                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Department</th>
                        <th>Role</th>
                        <th>Location</th>
                        <th>Status</th>
                    </tr>
                </thead>

                <tbody>
        `;

        data.employees.forEach(employee => {

            table += `

                <tr>
                    <td>${employee.employee_id}</td>
                    <td>${employee.name}</td>
                    <td>${employee.department}</td>
                    <td>${employee.role}</td>
                    <td>${employee.location}</td>
                    <td>${employee.status}</td>
                </tr>
            `;

        });

        table += `
                </tbody>
            </table>
        `;

        list.innerHTML = table;

    } catch (error) {

        list.innerHTML =
            "<p class='error'>Cannot connect to backend.</p>";

    }
}
