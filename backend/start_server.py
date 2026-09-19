import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uvicorn.main import main

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.argv = ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
    main()