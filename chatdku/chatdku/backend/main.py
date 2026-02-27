from app import app,socketio,setup,use_phoenix,CustomClient,dspy,Agent
# NOTE: Do not use this file on forduction, this is only for dev




# NOTE: gunicorn doesn't use if __name__ == "__main__" . SO it can be commented out. For development it can be uncommented and used with `python agent_app.py`

if __name__ == "__main__":
    setup()
    use_phoenix()
    llama_client = CustomClient()
    dspy.settings.configure(lm=llama_client)
    agent = Agent(max_iterations=1, streaming=True, get_intermediate=False)

    socketio.run(app=app, host="0.0.0.0", port=18420,debug=True)
# NOTE: Might want to make it easier to change the port
