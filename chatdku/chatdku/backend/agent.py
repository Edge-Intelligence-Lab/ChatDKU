from chatdku.core.agent import Agent
from flask import Response, stream_with_context


def agent_config(message_content,question_id,max_iterations=1, streaming=True, get_intermediate=False):
            # Create a new Agent instance per request
        agent = Agent(max_iterations=max_iterations, streaming=streaming, get_intermediate=get_intermediate)
        responses_gen = agent(
            current_user_message=message_content, question_id=question_id
        )

        # Stream the responses
        def generate():
            for response in responses_gen.response:
                yield f"{response}"

        return Response(stream_with_context(generate()), content_type="text/plain")

