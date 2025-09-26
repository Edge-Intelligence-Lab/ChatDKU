import dspy
from chatdku.core.dspy_classes.tool_memory import ToolMemory
from chatdku.core.tools.llama_index import VectorRetrieverOuter, KeywordRetrieverOuter
from chatdku.config import config
from chatdku.setup import use_phoenix, setup


class PlannerSignature(dspy.Signature):
    "Plan the appropiate tool calls to answer the given user question."

    question: str = dspy.InputField()
    max_calls: int = dspy.InputField()
    tools: list[dspy.Tool] = dspy.InputField()
    # tool_history: str = dspy.InputField(
    #     desc= "Your previous tool calls in JSON Lines format. "
    #     "It would be empty if you have not called any tools previously."
    # )
    # previous_tool_plan: dspy.ToolCalls = dspy.InputField()
    # conversation_history: dspy.History = dspy.InputField()

    tool_plan: dspy.ToolCalls = dspy.OutputField()


class Planner(dspy.Module):
    def __init__(self, tools: list[dspy.Tool]):
        super().__init__()

        self.tools = tools

        self.plan = dspy.ChainOfThought(PlannerSignature)

    def forward(
        self,
        user_message: str,
        # conversation_history: dspy.History,
        # tool_memory: ToolMemory,
        max_calls: int = 5,
    ) -> dspy.Prediction:

        planner = self.plan(
            question=user_message,
            max_calls=max_calls,
            tools=self.tools,
            # tool_history = tool_memory.history_str(),
            # previous_tool_plan = tool_memory.plan,
            # conversation_history = conversation_history
        )

        tool_plan = planner.tool_plan

        return dspy.Prediction(tool_plan=tool_plan)

    async def aforward(
        self,
        user_message: str,
        conversation_history: dspy.History,
        tool_memory: ToolMemory,
        max_calls: int = 5,
    ) -> dspy.Prediction:

        planner = await self.plan.acall(
            question=user_message,
            max_calls=max_calls,
            tools=self.tools,
            tool_history=tool_memory.history_str(),
            previous_tool_plan=tool_memory.plan,
            conversation_history=conversation_history,
        )

        return dspy.Prediction(tool_plan=planner.tool_plan)


def main(input: str):
    tools = {
        "VectorRetriever": dspy.Tool(VectorRetrieverOuter({})),
        "KeywordRetriever": dspy.Tool(KeywordRetrieverOuter({})),
    }

    planner = Planner(tools)
    tool_calls = planner(user_message=input, max_calls=5).tool_plan

    print(tool_calls)
    print(tool_calls.tool_calls[0])
    for tool in tool_calls.tool_calls:
        if tool.name in tools:
            result = tools[tool.name](**tool.args)
            print(f"Tool: {tool.name}")
            print(f"Args: {tool.args}")
            print(f"Result: {result}")


if __name__ == "__main__":
    setup(False, False)
    use_phoenix()

    lm = dspy.LM(
        model="openai/" + config.llm,
        api_base=config.llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=config.context_window,
        temperature=config.llm_temperature,
        launch_kwargs={
            "TopP": 0.95,
        },
    )
    dspy.configure(lm=lm)
    main(input("Enter question: "))
