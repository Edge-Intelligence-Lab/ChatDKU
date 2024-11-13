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

## New Usage(Mingxi Li)
For the sake of easy monitoring and long-term running, the commands will all be executed with "nohup".

First, we need to turn this folder into a Python server so that users can see the index.html file when they access the corresponding port.
```bash
cd /home/ChatDKU_Deployment/ChatDKU/deploy
nohup python3 -u -m http.server 9011 > ./logs/python_server_logs.txt &
disown -h
```

Next, start the agent_app service. This is the agent interface.(agent_app use port 9012 now)
```bash
nohup python3 -u agent_app.py > ./logs/agent_logs.txt &
disown -h
```

Finally, start the save_feedback.py service. (Using port 9013 now)
```bash
nohup python3 -u save_feedback.py > ./logs/save_fb_logs.txt &
disown -h
```

You can use this to check if ther are running.
```bash
ps -aux | grep python
```
