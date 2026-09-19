$ErrorActionPreference = "Stop"
if (!(Test-Path ".venv")) {
  py -3.14 -m venv .venv
}
.\.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
