# Demo Frontend and Backend

## Usage

Install dependencies in a virtual environment:
```bash
pip install -e .
```

Start backend:
```bash
./app.py
```
Note that the port can be changed in the arguments for `app.run()`.

Start frontend:
```bash
python3 -m http.server [port]
```
Note that the backend URL is currently hard-coded.
