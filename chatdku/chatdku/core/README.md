# ChatDKU Core Development Guide

This guide assumes that you know how DSPy works. If you do not, please take a look at [this guide](https://dspy.ai/learn/) first.

***

# Running Agent
You can run `agent.py` to directly talk with out agent. In the first two arguments it asks `UserID` and `Files`, you can just enter and input blank.

# About Agent

The agent consists of 6 big DSPy sub-modules:
- Query rewriter
- Planner
- Tool memory
- Judge
- Synthesizer
- Conversation Memory

Right now, we are NOT doing a true Agentic RAG. We have only 2 tools and doesn't really need the planner, but once we implement more tools we wil turn on the planner. 

As of 2025-11-04, our pipeline is as the following:

1. The previous conversation is loaded in if there is one.
2. User message is sent to the Query rewriter.
3. The rewritten query is used to retrieve documents from the `KeywordRetriever` and `VectorRetriever`.
4. The Judge will check if additional retrieval is necessary or not.
5. If it is needed, run Query rewriter again and retrieve documents that did not get retrieved (Done using the `internal_memory`).
6. If not needed, the Synthesizer will use the retrieved documents, conversation history and the original query to give an answer.
7. Return the answer to the user.
8. Summarize the answer and save it as `conversation_history` type.

## About Sub-modules

All off these modules are using:
- `span` to telemeterize the inputs and outputs to `Phoenix`, our analytical tool. 
- truncation on inputs to accomodate for too much tokens if the model context window is small
- DSPy [refinement](https://dspy.ai/api/modules/Refine/) to see if the model gave an answer in correct format (e.g. "Yes" or "No" for Judge).

### Query rewriter

This module's purpose is to:
1. Clean the user query for any misspellings
2. If there is any conversation before this query, add conversation context to the query
    > For example: 
    >Say, the user is talking about CS courses and then asks "which of these course are required for Applied Math computer science track?".
    > Then, the added context could be "From these CS courses (*list of CS courses*), which ones are required for Applied Math computer science track?"
    > If not added context, the tools will use this text as is and will retrieve uncorelated contexts. 
3. Create the text used for **context retrieval** 


### Planner

> [!IMPORTANT]
> This module is turned off for the time being as we only have 2 tools. Once more tools are implemented we will start usign this module.

The "brain" of our agent. This module's responsibility is to plan the necessary tool calls, as well as, the tool's parameters for a successful **context retrieval**. 

The **context retrieval** can be anything that is necessary for a succesful answer to the **user query**.

> [!IMPORTANT]
> Optimizing this module to multi-hop reasoning will give our agent huge accuracy boost. 
> Also, creating more tools for specific purposes will make our agent more "capable".

The current tools are here:

https://github.com/Glitterccc/ChatDKU/blob/ea80410cf8ebfce0b72bbe576ba8dbb4d0875fea/chatdku/chatdku/core/agent.py#L105-L122

To create a tool please look at this issue https://github.com/Glitterccc/ChatDKU/issues/122.

### Judge

The Judge is there to check if the retrieved **context** is enough to answer the **user query**. 

If it is **NOT** enough, the above mentioned sub-modules are called again to retrieve more **context**. This will loop for however many times the `max_iterations` is set to until the Judge deems the **context** is enough OR the loop ends.

If it is enough, the retrieved **context** and the **user query** is passed to the Synthesizer. 

### Synthesizer

This sub-module's responsibility is to output the final answer based on the retrieved **context** from previous modules. 

The prompt of this sub-module will define how the behaviour of our Agent's answer, thus, the long instructions are passed. Remember that, our instruction prompt is quite long. This would mean that our response time from this module will also be long. 

### Conversation memory

This module activates after the Synthesizer and summarizes the Agent output. Once summarized, the conversation is stored in the following format:

```
    role: user,
    content: user_query,
    role: assistant,
    context: answer
```

***

# About ChatDKU Syllabi Tool 
Similar to ChatDKU's other tools, the Syllabi Tool uses DSPy for orchestrating tasks for the LLM. The folder `chatdku/chatdku/core/tools/syllabi_tool` contains the code that culminates in `query_curriculum_db.py`, which is passed onto `agent.py` as a tool for the Planner to use. 

Currently, the problem in implementing this tool is the amount of latency it adds to ChatDKU's response due to the constant connecting and disconnecting from the Postgres DB. This can be solved with a proper DB connection handled by Django. 

## About the Local Document Ingestion Pipeline

This folder also contains the ingestion mechanism (`local_ingest.py`) for extracting structured data from PDF and DOCX files into a Postgres database called  `chatdku_db` under the username `chatdku_user`. 

The schema for this database can be found in `create_table.sql`. Running this SQL query inside Postgres will remove all data from the classes table, so any modifications to the schema should be made as post-hoc SQL schema definition queries. 

You may also find a file called `classes_schema.json`. This is a JSON representation of the same schema defined in the `create_table.sql` file. This file **MUST** be in-sync with the actual schema used in the database, as both the document ingestion **and** SQL generation agent use this as a reference. (this is faster than using `get_schema.py` for reading schema during runtime)
