# 📋 TaskFlow

A role-based project and task management web app built with Django and Tailwind CSS.
Designed to simulate real workplace workflows — from room creation and task assignment
to graded submissions and performance analytics.

---

## 👥 Roles & Permissions

### 🔑 Admin
- View all users and rooms across the platform
- Delete or manage users
- Access system-wide statistics on room performance

### 👔 Boss (Manager)
- Create and manage rooms (public or private)
- Assign tasks to employees with priority levels (Low / Medium / High)
- Review and grade completed task submissions (out of 100)
- Accept or reject employee join requests for private rooms
- View employee performance analytics:
  - Completion ratio
  - Average rating
  - Performance ranking across categories

### 👷 Employee
- Join public rooms by searching room name
- Request to join private rooms via room code (boss must approve)
- View assigned tasks with priority and deadline info
- Upload file submissions and mark tasks complete
- Track personal task history

---

## ✨ Features

- Role-based authentication (Admin / Boss / Employee)
- Public rooms (open join) and Private rooms (code + approval flow)
- Task assignment with Low / Medium / High importance tagging
- File upload for task submissions
- Boss grading system with performance scoring
- Employee analytics dashboard with ranking system
- Admin panel with platform-wide oversight

---

## 🛠️ Tech Stack

- **Backend:** Django (Python)
- **Frontend:** Tailwind CSS, HTML
- **Database:** SQLite
- **Auth:** Django built-in authentication

---

## ⚙️ Setup & Installation
```bash
# Clone the repo
git clone https://github.com/SahilRpanjwani/TaskFlow.git
cd TaskFlow/TaskFlow

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start the server
python manage.py runserver
```

---

## 👤 Author

**Sahil Panjwani**
- GitHub: [@SahilRpanjwani](https://github.com/SahilRpanjwani)
- LinkedIn: [linkedin.com/in/sahil-panjwani-6843a92b1](https://www.linkedin.com/in/sahil-panjwani-6843a92b1)
