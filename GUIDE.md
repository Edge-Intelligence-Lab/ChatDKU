# Introduction

This is a set of guides intended for you to get ready to contribute to our project.
This guide is intended for **newcomers**, as well as, our **members**.
I (Temuulen) will be explaining our core dependencies as well as any other useful stuff you should learn about before getting into coding. 

> [!IMPORTANT]
> This is a work in progess. Please tell me what you don't understand about this guide and our project and I will add it to this document for future use. 

When I was coming into this project, even though it was structured very clearly, it was hard to get my head around everything.
I felt like the code was just very messy and there were just a lot of things that did not have clear explanations.

And most of our code is like that even today. However, with this guide I hope you will at least have some support and start contributing faster. 

> Please remember that at first you will be learning *slow* to **develop** faster in the future by following this guide.

Here are some list of members and their respective roles they **self-assigned** themselves into:
- Anar: Frontend (React.js), Syllabi SQL agent tool
- Munish: Backend (Flask, Django), System health monitoring
- Temuulen: Agent logic (DSPy), Document ingestion Logic (Transferring to ZhiWei)

## Basics

### 1. Python

First, obviously you need to know python. While we don't require you to be a pythonic expert, a quality code is generally preferred. So, what makes a code ***good code***?

This is completely subjective, but there are some qualities that you can start from:
- Functions have [docstrings](https://numpydoc.readthedocs.io/en/latest/format.html) 
- Account for future contributers to understand the code
- Obvious naming practices and using python naming practices.

I mean I can go on and on about coding practices. What you need to understand is that you need to build scalable code, accounting for any other person to review your code and understand it.

### 2. Git

> [!IMPORTANT]
> I cannot emphasize enough on how to use git properly.
> While these things seem very annoying at first, believe me that they will help.
> When I come back to DKU next Spring, I plan to give every member a crash course on a new GIT workflow. Please read all the articles I will be linking to.

Git is a version control system that intelligently tracks changes in files. 
Git is particularly useful when you and a group of people are all making changes to the same files at the same time.

Typically, to do this in a Git-based workflow, you would:

- Create a branch to ***show the intent of your work***.
- Create issues ***before*** you do the work/code.
- Make edits to the files independently and safely on your own personal branch.
- Close or update issues [with your commits or Merge Requests](https://docs.gitlab.com/user/project/issues/managing_issues/#closing-issues-automatically)
- Let Git intelligently merge your specific changes back into the main copy of files, so that your changes don't impact other people's updates.
- Let Git keep track of your and other people's changes, so you all stay working on the most up-to-date version of the project.

> [!IMPORTANT]
> Our `Main` branch is a **SACRED** branch. DO NOT PUSH CODE WITHOUT PROPER REVIEW FROM OTHER MEMBERS.

Please read these articles:
- [Github Flow](https://docs.github.com/en/get-started/using-github/github-flow)
- [Always start with an issue](https://web.archive.org/web/20230214040753/https://about.gitlab.com/blog/2016/03/03/start-with-an-issue/) 
    - Try creating an issue now on what you want to do next.
    - Also if you don't see our issue board under the projects tab in our repo. Please contact Mingxi and ask to be added to the Project issue board.
- [Write good commit messages!](https://cbea.ms/git-commit/)
- [Issue board](https://about.gitlab.com/blog/announcing-the-gitlab-issue-board/)
    - While we are not using Gitlab, Github has the same feature called "Project".
- [It's all connected in Gitlab](https://about.gitlab.com/2016/03/08/gitlab-tutorial-its-all-connected/) 
    - Again, Github has the equilavent features at [here](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls) 

As you incorperate these steps into your developer journey, you will be better equipped for real world team-coding.
All the industry experts follow some form of stardards using GIT. You should learn to use it properly while you are here with us. 

And [here is a longer video](https://www.youtube.com/watch?v=1ffBJ4sVUb4) that gives you more in-depth details on how GIT works. 

Here is an [interactive](https://learngitbranching.js.org/?locale=en_US) Git simulator for you to practice. 

### 3. Using the Terminal

Using the terminal, you can do a lot of stuff with it. I assure you that to get better at it you just have to use it daily. At first you might google a lot of stuff, and that is **okay!**.
All of us started out like that. Here are some of the common commands I use when working with CHATDKU:
- `ssh`: Used to connect to our server
- `git`: Working with github
- `sftp`: ssh like file transferring
- `nvidia-smi`: Used to inspect GPUs

Again, just google these stuff and learn. Good luck! It will be worth it.

## Role-specific guides

Please be careful when interacting with Docker. It hosts our Embedding Model, Vector Database, and Redis Database.

### Agent Logic

- DSPy for interacting with the LLM: https://dspy.ai/learn/
- For creating tools: https://github.com/Glitterccc/ChatDKU/issues/122
- Arize Phoenix for observability: https://arize.com/docs/phoenix

### Document ingestion

- Llamaindex for document ingestion: https://developers.llamaindex.ai/python/framework/getting_started/concepts
- ChromaDB for vector store: https://docs.trychroma.com/docs/overview/introduction
- Redis for keyword search: https://redis.io/docs/latest/develop/

