# TaskFlow API – Séance 2
## Installation ```bash 
python -m venv venv 
# macOS/Linux 
source venv/bin/activate 
# Windows 
# .\venv\Scripts\activate 
pip install -r requirements.txt 
python manage.py migrate 
python manage.py runserver