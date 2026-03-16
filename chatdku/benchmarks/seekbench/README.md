# Evaluation: Seekbench

This project is based on the paper **Do LLM Agents Know How to Ground, Recover, and Assess? Evaluating Epistemic Competence in Information-Seeking Agents**. We have tried replicating the paper to adjust to ChatDKU scenario.

- You can find the original paper [here](https://openreview.net/forum?id=r0L9GwlnzP)
- You can find the github repo [here](https://github.com/SHAO-Jiaqi757/SeekBench/tree/main)


- [Evaluation: Seekbench](#evaluation-seekbench)
  - [Workflow](#workflow)



## Workflow

### Generate Traces

Generate Traces based on **DKU** specific questions. As of writing this `readme.md` file, it accepts list with json. Eg:

```
[
    {
        'question':'....',
        'max_iteration':int
    },

    ...
]

```
`question` represents the **Question** to be answered
`max_iteration` is the maximum number of loops allowed to the agent.



