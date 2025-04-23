import React from "react";

export default function Remark() {
  return (
    <div>
      <h2 className="text-xl font-bold mt-2 mb-1">LLM</h2>
      <p>
        A Large Language Model (LLM) is effectively a calculator for languages,
        where given a sequence of tokens as its input, it will return the most
        probable token that would follow this sequence. A token is the smallest
        semantic unit represented with a vector, which could be compared to a
        word, or more accurately, a morpheme, plus some positional information.
        The output could be extended to choosing randomly from the set of most
        probable next tokens, whose size is controlled by the `temperature`
        parameter.
      </p>
      <p>
        Thus, an LLM does not have memory, nor would it be able to "think"
        similar to a human. However, it could be argued that an LLM is able to
        "reason" to some extent, as you could define "reason" as a process of
        repeatedly applying a sequence of rules, such as a step-by-step proof of
        a mathematical theorem. An LLM is able to reason by this definition, as
        it can be prompted to generate a sequence of tokens obeying a
        statistical pattern that reflects the rules of grammar or logic to some
        extent.
      </p>

      <h2 className="text-xl font-bold mt-2 mb-1">ChatDKU</h2>
      <p>
        ChatDKU is a conversational agent powered by LLM and Retrieval-Augmented
        Generation (RAG) pipeline. By "agent", it means that it can call
        different tools and iteratively reflect upon its past decisions and
        outcomes. Recall the definition above that an LLM is, in fact,
        stateless, these past decision and outcomes have to be stored in a
        memory so that they would be passed to the LLM when necessary.
        Furthermore, this also means that every time we call the LLM, we have to
        tell the LLM that its role is to be "a helpful assistant for the DKU
        community", for example.
      </p>
      <p>
        Regarding RAG, it means that ChatDKU can query a database of DKU-related
        information that could be injected into the LLM calls when necessary.
      </p>
      <p>
        DKU-specific knowledge is only provided to ChatDKU via RAG and prompt
        engineering at this stage, we might consider fine-tuning the LLM model
        in the future, or even fine-tuning the model for each agent component
        specifically.
      </p>
      <p>Here are the components of ChatDKU agent:</p>
      <h3 className="text-xl font-bold mt-2 mb-1">Tools</h3>
      <ul className="my-3">
        Tools are the foundation of agent, agent decides how to call the tool to
        achieve the user's requirements by planning. ChatDKU has two types of
        tools: Retrieve tools and API tools. Now we have two retrieve tools:
        Vector Retriever and Keyword Retriever,t he former is good at general
        questions while the latter is good at keyword search. We also plan to
        introduce other retrieve tools in the futrue, starting with graphrag,
        which is good at summarizing and comparing problems. Some API tools will
        also be introduced, such as the mail tool.
      </ul>
      <h3 className="text-xl font-bold mt-2 mb-1">Tool Memory</h3>
      <ul className="my-3">
        Tool memory is the module that stores memory during one round of Q&A of
        the agent, including retrieved results, user queries, chat history, chat
        summaries, tool call history, etc.
      </ul>
      <h3 className="text-xl font-bold mt-2 mb-1">Judge</h3>
      <ul className="my-3">
        The judgment module is used to determine whether the information that is
        now known (the information that has been retrieved) can answer the
        user's question.
      </ul>
      <h3 className="text-xl font-bold mt-2 mb-1">Query Rewrite</h3>
      <ul className="my-3">
        The Query Rewrite module is used to rewrite queries to make it easier to
        search for relevant results.
      </ul>
      <h3 className="text-xl font-bold mt-2 mb-1">Planner</h3>
      <ul className="my-3">
        Planner is the main thinking module of agent, which is responsible for
        intelligently calling tool to provide services for users.
      </ul>
      <h3 className="text-xl font-bold mt-2 mb-1">Synthesizer</h3>
      <ul className="my-3">
        The Synthesizer module is used to summarize all the known information
        and give response to the user's question.
      </ul>

      <p>
        Then, we'll detail the direction of information flow when a user sends a
        message to ChatDKU:
      </p>
      <ol>
        <li>
          To speed up the response latency, we first call all retrieve tools in
          parallel when generating the response in the first round.
        </li>

        <li>
          The retrieved results from the retrieve tools will be stored in the
          tool memory module.
        </li>

        <li>
          Next, we'll use the Judge module to determine if the given information
          can answer the user's question. If it can, we'll return the result.If
          it can't, we'll let the agent do some self-reflection.
        </li>

        <li>
          Since the query and the retrieved results are highly correlated, if
          the user's query is not explicit, the relevant results may not be
          retrieved. So, after a round of poor retrieved results, we call the
          query rewrite module to rewrite the query to get more relevant search
          results.
        </li>

        <br />

        <li>
          Next, the ChatDKU agent will use the rewritten query, existing tool
          memory, and available tools to generate a new plan for calling tools
          to get more relevant retrieval results.
        </li>

        <br />

        <li>
          After that, the agent will call tools again and repeat the above steps
          until the Judge module thinks it can give an appropriate answer.
          Finally, the synthesizer module is used to provide the user with a
          response.
        </li>
      </ol>

      <h2 className="text-xl font-bold mt-2 mb-1">Hallucination</h2>
      <p>
        Hallucination is when the LLM outputs counterfactual information. As the
        LLM is basically a predictor for the most probable next token, this is
        unavoidable. According to the{" "}
        <a
          className="text-blue-700 decoration-0"
          target="_blank"
          href="https://huggingface.co/spaces/vectara/leaderboard"
        >
          Hughes Hallucination Evaluation Model (HHEM) leaderboard
        </a>
        ,Meta-Llama-3.1-70B-Instruct and Meta-Llama-3.1-8B-Instruct each has a
        Hallucination Rate of 5 % and 5.5 % respectively, which is indeed higher
        than the current top model in the leaderboard GPT-4o, which has a
        hallucination rate of 1.5 %. However, this is still better than some
        widely used models such as Gemini-1.5-flash at 6.6 % and
        Claude-3-5-Sonnet at 8.6 %.
      </p>
      <p>
        We would try to minimize the risk of hallucination by prompting the LLM
        to follow the retrieved information as much as possible, and encouraging
        it to say "I don't know" or ask for clarifications from the user when it
        is unable to answer the question as opposed to generating an answer that
        "appears" to be correct. Simultaneous, the usage of prompting techniques
        such as{" "}
        <a
          className="text-blue-700 decoration-0"
          target="_blank"
          href="https://arxiv.org/abs/2201.11903"
        >
          chain-of-thought
        </a>{" "}
        could elicit explicit reasoning so the LLM might make better use of the
        knowledge injected into the prompt.
      </p>
      <p>
        We would also prompt the LLM to cite its sources in forms of URL for
        webpages or title and page number for documents, thus making the
        correctness of the answer simple to verify and the user could easily
        detect cases of hallucinations.
      </p>

      <h2 className="text-xl font-bold mt-2 mb-1">AI Safety</h2>
      <p>
        Similar to hallucination, there is no absolute guarantee that an LLM
        would not produce any harmful output. There are two common techniques to
        circumvent safety features of an LLM, prompt injection and jailbreaks.
        Prompt injection is basically telling the LLM to ignore the previous
        instructions and do something else, where the previous instructions in
        this case is usually the instructions provided by the developer.
        Jailbreaks are to tell the LLM to assume a role that, for example, "obey
        no rules or ethics". This could thus leading to the LLM outputting
        harmful content as that role despite prompts or fine-tuning that
        discourages such behaviors.
      </p>
      <p>
        Nevertheless, measures could be taken to minimize the risk of LLM
        outputting harmful content. According to{" "}
        <a
          className="text-blue-700 decoration-0"
          target="_blank"
          href="https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md#responsibility--safety"
        >
          Llama 3.1's model card
        </a>
        , it has been aligned for its safety in generic use cases. It is also
        stated by Meta that "Large language models, including Llama 3.1, are not
        designed to be deployed in isolation but instead should be deployed as
        part of an overall AI system with additional safety guardrails as
        required." Thus, safeguards that are designed to be used in companion
        with Llama such as{" "}
        <a
          className="text-blue-700 decoration-0"
          target="_blank"
          href="https://llama.meta.com/trust-and-safety/#safeguard-model"
        >
          Llama Guard and Prompt Guard
        </a>
        could be also used in the system to minimize the risks. Llama Guard can
        detect harmful behaviors such as those that could cause injuries, and
        Prompt Guard can detect prompt attacks such as prompt injection and
        jailbreak. Additionally, the tool calling ability of ChatDKU is
        constrained by an additional permission system that would not allow the
        user to execute operations beyond its privileges even if the LLM has
        been compromised. The execution of external capabilities, such as
        mail-sending, would also require the explicit confirmation by the user.
      </p>
      <p>
        It should be also noted that{" "}
        <a
          className="text-blue-700 decoration-0"
          target="_blank"
          href="https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md#intended-use"
        >
          Meta discourages Llama 3.1's use outside of its supported languages
        </a>
        , which does not include Chinese. It does, however, mention that
        fine-tuning Llama 3.1 to support languages beyond those officially
        supported is acceptable as long as they comply with the Llama 3.1
        Community License and the Acceptable Use Policy.
      </p>
      <p>
        Meta has evaluated Llama 3.1 with{" "}
        <a
          className="text-blue-700 decoration-0"
          target="_blank"
          href="https://arxiv.org/abs/2408.01605"
        >
          CYBERSECEVAL 3
        </a>
        , which evaluates Llama 3.1's risks in different areas, including its
        susceptibility to prompt injection and been utilized to help conduct
        cyberattacks. This evaluation, however, does not include its risk of
        generating harmful content, which could be evaluated by benchmarks such
        as{" "}
        <a
          className="text-blue-700 decoration-0"
          target="_blank"
          href="https://arxiv.org/abs/2402.04249"
        >
          HarmBench
        </a>
        . While HarmBench only evaluated Llama 2 models, we could also adopt it
        to Llama 3.1.
      </p>

      <h2 className="text-xl font-bold mt-2 mb-1">Information Flow</h2>
      <p>
        The user information that ChatDKU has access to is limited to the
        conversation history of the users and their identity in the Duke
        Shibboleth system. At the very minimum, when a user sends a message in a
        multi-round conversation, such a message is given to ChatDKU. To
        maintain the history of a single conversation, the LLM has to know the
        history of the conversation (with the oldest entries stored as
        summaries) so that it could understand if the user is referencing
        something earlier in the conversation. Thus, the history of the
        conversation could either be stored on the server for the current
        session, or on the user's device, though it would be accessible to the
        server every time the user sends a message. To maintain the history of
        multiple isolated conversations, they could be stored on the user's
        device or the server. However, only by storing the history on the server
        can the users continue or view a conversation on a different device.
        Also, to improve ChatDKU and conduct research, we would like to store
        all user conversations, but they do not need to be traceable to the
        specific individuals that initiated the conversations.
      </p>
      <p>
        The use of Duke Shibboleth system is not implemented in the current
        phrase. However, it would be integrated in the future so that we can
        both maintain a conversation history for the user and authenticate the
        user to access information that are not appropriate for the general
        public.
      </p>
      <p>
        All the information injected into the LLM would be visible to the
        ChatDKU developers one way or another if we are in control of the
        instance unless we implement some kind of homomorphic encryption scheme,
        which would be rather complicated to do. This is due to that even if you
        protect the data in storage, it would still be in plain text in RAM or
        VRAM. You have to deploy ChatDKU separately if you have to handle very
        sensitive information.
      </p>

      <h2 className="text-xl font-bold mt-2 mb-1">Database Permissions</h2>
      <p>
        Suppose that you want to have data that are accessible to only student,
        faculty, or staff, or some, or all of them, I would recommend the
        approach of adding three permission attributes to the entries in the
        database:
      </p>
      <table className=" text-left w-full text-sm border-collapse border my-2 border-gray-200 dark:border-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-800">
          <tr>
            <th
              colSpan={3}
              className="p-1 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700"
            >
              Permission
            </th>
            <th
              rowSpan={2}
              className="p-1 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700"
            >
              Data
            </th>
          </tr>
          <tr>
            <th className="p-1  text-left text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              Student
            </th>
            <th className="p-1  text-left text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              Faculty
            </th>
            <th className="p-1  text-left text-sm font-medium text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              Staff
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              true
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              false
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              true
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              example data 1
            </td>
          </tr>
          <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              false
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              true
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              true
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              example data 2
            </td>
          </tr>
          <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              true
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              true
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              false
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              example data 3
            </td>
          </tr>
          <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              false
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              false
            </td>
            <td className="p-1  text-sm text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
              true
            </td>
            <td className="p-1  text-sm  border border-gray-200 dark:border-gray-700">
              example data 4
            </td>
          </tr>
        </tbody>
      </table>

      <p>
        Thus, student would only be able to access the first and the third row,
        for example. The role of the user would be determined by the NetID
        account used, and would not be susceptible to the LLM prompt attacks.
        This is better than the alternative approaches of, for example,
        maintaining three separate databases, where each query has to be
        repeated for each accessible database.
      </p>

      <h2 className="text-xl font-bold mt-2 mb-1">Extensibility</h2>
      <p>
        As we currently do not use fine-tuning, for ChatDKU to answer questions
        regarding other information, it is sufficient to just add the relevant
        documents and webpages. We currently support only structured (those with
        headings, subheadings, etc.) or unstructured texts. Tables in the texts
        are supported, but the performance of interpreting tabular data has to
        be further evaluated. Relational data such as a database or graph is yet
        to be supported, however, they are expected to be added in the future as
        the handling of course prerequisites requires the interpretation of
        course dependency information.
      </p>
      <p>
        However, the capabilities for ChatDKU to conduct complex and
        interconnected reasoning as yet to be developed and evaluated. So it may
        not be good enough to be a TA for a course, for example.
      </p>
    </div>
  );
}
