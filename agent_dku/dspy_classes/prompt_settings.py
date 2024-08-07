import dspy

VERBOSE = True

CURRENT_USER_MESSAGE_FIELD = dspy.InputField(desc="The current user message to answer.")
CONVERSATION_HISTORY_FIELD = dspy.InputField(
    desc=(
        "Previous conversation between user and you, the assistant, in JSON Lines format. "
        "Each line specifies the role and content of the message. "
        "The Current User Message is a continuation of this conversation. "
        "It would be empty if there were no previous conversation."
    ),
    format=lambda x: x,
)
CONVERSATION_SUMMARY_FIELD = dspy.InputField(
    desc="Summary of old and discarded Conversation History. Might be empty.",
    format=lambda x: x,
)
TOOL_HISTORY_FIELD = dspy.InputField(
    desc=(
        "Your previous tool calls in JSON Lines format. "
        "Each line specifies the name and parameters of the tool and its result. "
        "It would be empty if you have not called any tools previously."
    ),
    format=lambda x: x,
)
TOOL_SUMMARY_FIELD = dspy.InputField(
    desc="Summary of old and discarded Tool History. Might be empty.",
    format=lambda x: x,
)

ROLE_PROMPT = (
    "You are ChatDKU, a helpful, respectful, and honest assistant for students, "
    "faculty, and staff of, or people interested in Duke Kunshan University (DKU). "
    "You are created by the DKU Edge Intelligence Lab.\n\n"
    "Duke Kunshan University is a world-class liberal arts institution in Kunshan, China, "
    "established in partnership with Duke University and Wuhan University."
)
