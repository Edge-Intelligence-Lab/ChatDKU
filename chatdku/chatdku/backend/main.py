from app import app, socketio, setup, use_phoenix, dspy, Agent
from chatdku.config import config

# NOTE: Do not use this file on production, this is only for dev


# NOTE: gunicorn doesn't use if __name__ == "__main__" . SO it can be commented out. For development it can be uncommented and used with `python agent_app.py`

if __name__ == "__main__":
    setup()
    use_phoenix()
    lm = dspy.LM(
        model="openai/" + config.backup_llm,
        api_base=config.backup_llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=config.context_window,
        temperature=config.llm_temperature,
    )
    dspy.configure(lm=lm)
    agent = Agent(max_iterations=1, streaming=True, get_intermediate=False)
    socketio.run(app=app, host="0.0.0.0", port=18420, debug=True)
# NOTE: Might want to make it easier to change the port
