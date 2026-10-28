# SmartCare: Single-Hospital Healthcare & Emergency Management System

SmartCare is a full-stack healthcare web application built with **Python 3.13**, **Django 6.1**, **SQLite**, and **HTML5 / CSS3 / Vanilla JavaScript**.

SmartCare represents **ONE hospital** (configured in settings), uniting hospital-controlled doctor onboarding, confidential doctor-specific appointment scheduling with smart travel departure buffers, and a separated priority-based emergency triage queue implemented with a genuine Python min-heap.

---

## 🏥 Single-Hospital Architecture

1. **One Central Hospital**:
   - Configured in `smartcare_project/settings.py` via `DEFAULT_HOSPITAL_NAME` and `DEFAULT_HOSPITAL_ADDRESS`.
   - All doctors, patients, appointments, and emergency cases belong to this hospital.
2. **Strict Doctor-Specific Appointment Isolation**:
   - When a doctor logs in, their dashboard displays **strictly** appointments whose assigned doctor is that authenticated doctor.
   - Access control is enforced on the Django backend for every appointment URL and endpoint (`HttpResponseForbidden` on tampering).
   - Patients can view only their own bookings.
3. **Hospital Administrator Doctor Onboarding**:
   - Public doctor self-registration is disabled.
   - Only authorized hospital administrators can create doctor accounts, license numbers, consultation fees, and working hours.
   - Doctors log in using their own credentials and can manage their consultation days, hours, slot intervals, and active status.
4. **Emergency vs. Routine Consultation Segregation**:
   - Direct question: *"Are you seeking a routine consultation or emergency medical assistance?"*
   - Emergency guidance instructs patients not to wait for routine appointments and provides 24/7 hotline and emergency pavilion gate information.
   - Patients may report symptoms, but **never assign themselves a clinical priority**.
   - Clinical staff assign triage priorities: **Critical (Red)**, **Urgent (Orange)**, **Less Urgent (Green)**.
5. **Patient-Visible Emergency Queue Status & Privacy**:
   - Authenticated patients can view their position (#X in queue), count of patients ahead, and status.
   - Other patients' names, symptoms, and medical details are strictly confidential and never transmitted.

---

## ⚡ Quick Start: Windows PowerShell Commands

From your project directory:

```powershell
# 1. Activate the virtual environment
.\venv\Scripts\Activate.ps1

# 2. Run database migrations
.\venv\Scripts\python.exe manage.py migrate

# 3. Initialize administrator account (does NOT recreate old mock doctors)
.\venv\Scripts\python.exe manage.py seed_data

# 4. Start the development server
.\venv\Scripts\python.exe manage.py runserver 8000
```
Open your browser at: **`http://127.0.0.1:8000/`**

---

## 📋 Step-by-Step Walkthrough

### 1. Log in as Hospital Administrator
- Navigate to `http://127.0.0.1:8000/login/`
- **Email**: `admin@smartcare.org`
- **Password**: `AdminPass123!`
- Click on **"Manage Doctors"** in the top navigation bar (`/hospital/doctors/`).

### 2. Add Your First Doctor
- In the Doctor Management dashboard, click **"+ Onboard New Doctor"**.
- Enter:
  - Doctor Name (e.g. `Dr. Rajesh Kumar`)
  - Email (e.g. `rajesh.kumar@smartcare.org`)
  - Initial Password (e.g. `DoctorPass123!`)
  - License Number (e.g. `MED-KUM-2026`)
  - Specialization (e.g. `Cardiology`)
  - Consultation Fee (e.g. `$500.00`)
  - Working Days (e.g. `Mon, Tue, Wed, Thu, Fri`) and working hours.
- Submit the form. The doctor is now active in the hospital directory.

### 3. Register a Patient Account
- Log out, or open an incognito window.
- Click **"Patient Registration"** at `http://127.0.0.1:8000/register/patient/`.
- Register a patient (e.g. `Ananya Sharma`, `ananya@example.com`, password: `Password123!`).

### 4. Book an Appointment
- Navigate to **"Find Specialists"** (`/find-doctors/`).
- Click **"Select Slot & Book Appointment"** for the doctor.
- In the consultation form:
  - Choose **"Routine consultation"**.
  - Select your primary health concern (e.g. *Heart-related concern*).
  - Select a date and available time slot.
  - Enter your starting address or click *"Use My Current Location"*.
  - Choose your safety buffer (15 mins).
  - Submit booking.

### 5. Verify Doctor-Specific Appointment Isolation
- Log out and log in as the newly created doctor (`rajesh.kumar@smartcare.org` / `DoctorPass123!`).
- The doctor dashboard will show **only** Ananya Sharma's appointment with Dr. Rajesh Kumar.
- If another doctor (e.g. `pratiksha@smartcare.org`) logs in, they will **not** see Ananya's appointment with Dr. Kumar.
- If Dr. Prathiksha tries to manually change the URL to view Dr. Kumar's appointment, the server rejects the request with **403 Forbidden**.

---

## 🧪 Running Automated Tests

Run the full automated test suite covering all 10 verified requirements:
```powershell
.\venv\Scripts\python.exe manage.py test
```

### Verified Test Suite:
1. `test_1_doctor_a_cannot_see_doctor_b_appointments_on_dashboard`
2. `test_2_doctor_a_cannot_access_doctor_b_appointment_by_changing_url`
3. `test_3_patient_sees_only_their_own_appointments`
4. `test_4_patient_cannot_view_another_patient_emergency_record`
5. `test_5_patients_cannot_assign_or_change_their_own_emergency_priority`
6. `test_6_queue_positions_update_when_queue_changes`
7. `test_7_routine_appointments_remain_separate_from_emergency_cases`
8. `test_admin_can_add_doctor_manually_without_sample_doctors_reappearing`
9. `test_unauthorized_users_cannot_create_doctor_accounts`
10. `test_10_appointment_slots_cannot_be_double_booked`

---

## 🔄 Instructions for Safely Resetting Development Database

If you ever wish to completely wipe and recreate the development database:

1. Delete the SQLite file:
   ```powershell
   Remove-Item db.sqlite3
   ```
2. Re-apply migrations:
   ```powershell
   .\venv\Scripts\python.exe manage.py migrate
   ```
3. Initialize the hospital administrator:
   ```powershell
   .\venv\Scripts\python.exe manage.py seed_data
   ```
This recreates a clean hospital database with only `admin@smartcare.org`, with zero mock doctors or appointments.
