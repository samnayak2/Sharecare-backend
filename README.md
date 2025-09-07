# ShareCare Backend

A **FastAPI-based backend service** for the ShareCare mobile application that handles:

- User management  
- Donations  
- Chat functionality  
- Item tracking  

---

## 🚀 Prerequisites

- Python **3.8+**  
- `pip` (Python package installer)  
- Google Cloud **Service Account JSON** file  

---

## ⚙️ Setup Instructions

### 1. Create Python Virtual Environment

```bash
python -m venv env
````

### 2. Activate Virtual Environment

**Windows (PowerShell):**

```powershell
env\Scripts\activate
```

**macOS/Linux:**

```bash
source env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Google Application Credentials

Your service account JSON must be set as an environment variable in **Base64 format**.

#### Convert JSON to Base64 (Windows PowerShell):

```powershell
[Convert]::ToBase64String((Get-Content -Path "service_account.json" -Encoding Byte))
```

This will output a long Base64 string.

#### Set Environment Variable (Windows PowerShell):

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "BASE64_STRING_HERE"
```

#### Set Environment Variable (macOS/Linux):

```bash
export GOOGLE_APPLICATION_CREDENTIALS="BASE64_STRING_HERE"
```

---

### 5. Run the Application

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```


The backend will now be available at:
👉 [http://localhost:8000](http://localhost:8000)

---

## 📌 Notes

* Replace `"BASE64_STRING_HERE"` with the actual Base64-encoded content of your `service_account.json`.
* Ensure your `requirements.txt` includes **FastAPI**, **Uvicorn**, and any Google Cloud dependencies you use.
* API documentation will be available at:

  * Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
  * ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

```

