# Introduction

This is a set of guides intended for you to get ready to contribute to our project.
This guide is intended for **newcomers**, as well as, our **members**.
I (Temuulen) will be explaining our core dependencies as well as any other useful stuff you should learn about before getting into coding.

> [!IMPORTANT]
> This is a work in progress. Please tell me what you don't understand about this guide and our project and I will add it to this document for future use.

When I was coming into this project, even though it was structured very clearly, it was hard to get my head around everything.
I felt like the code was just very messy and there were just a lot of things that did not have clear explanations.

And most of our code is like that even today. However, with this guide I hope you will at least have some support and start contributing faster.

> Please remember that at first you will be learning _slow_ to **develop** faster in the future by following this guide.

Here are some list of members and their respective roles they **self-assigned** themselves into. Ask them questions based on their responsibilities:

- Anar: Frontend (React.js), Syllabi SQL agent tool
- Munish: Backend (Flask, Django), System health monitoring
- Temuulen: Agent logic (DSPy), Prometheus Monitoring
- Zhiwei: Document ingestion Logic

**The current Project Manager (PM)**: Temuulen.

# Onboarding Schedule

Your onboarding journey should follow this schedule and milestones:

## Milestone 1: Getting Started (First Week)

- Join the relevant groupchats (Contact PM):
    - ChatDKU Main 
    - ChatDKU Dev-Only 
    - Edge Intelligence Labs
- Join the Edge Intelligence Labs Github Organization (Contact PM)
- Join the ChatDKU Repo as a Collaborator (Contact PM)
- [SSH into the Edge Intelligence Labs Server 3](https://github.com/Edge-Intelligence-Lab/Guidance) 
- Clone the [ChatDKU Repo](https://github.com/Edge-Intelligence-Lab/ChatDKU) on both your local machine and Lab Server
- Contact PM about environment variables
- Download the dependencies through `uv`
    - Use `uv sync` inside the project root to download the dependencies
- Run the ChatDKU CLI Agent
    - You an run the [TUI](chatdku/core/tui.py) 
    - Or you can run the [Agent directly](chatdku/core/agent.py)

- Read GitHub docs about:
    - Creating [Issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue)
    - Creating [Branches](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-and-deleting-branches-within-your-repository)
    - Creating [Pull Requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)

## Milestone 2: Introduction to the Project (Second Week)

- Read through the docs referenced in this guide
- Figure out which sub-team you want to join
    - Agent Team
    - Backend Team
    - Frontend Team
    - Data Ingestion Team
    - Evaluation Team
- Contact PM about your decision
- Create your first Issue and propose a mini feature (Discuss with PM)

## Milestone 3: First Issue (Third Week)

- Fix your first issue
- At the end of the week, create a Pull Request with the appropriate tags. Assign yourself as the `Assignee`, and assign the PM as the `Reviewer`.

## Milestone 4: Code review (Fourth Week)

- Back and forth conversation of reviews on the Pull Request
- Demo your mini feature

# Basics

### 1. Python

First, obviously you need to know python. While we don't require you to be a pythonic expert, a quality code is generally preferred. So, what makes a code **_good code_**?

This is completely subjective, but there are some qualities that you can start from:

- Functions have [docstrings](https://numpydoc.readthedocs.io/en/latest/format.html)
- Account for future contributors to understand the code
- Obvious naming practices and using python naming practices.

Relevant articles:
- [Clean Code](https://medium.com/@luisacarrion/general-coding-guidelines-clean-code-from-day-1-9ab0804e5d91) 
- [No siler Bullet](https://courses.cs.duke.edu/compsci408/fall25/readings/no_silver_bullet.pdf)
I mean I can go on and on about coding practices. What you need to understand is that you need to build scalable code, accounting for any other person (me) to review your code and understand it.

### 2. Git

> [!IMPORTANT]
> I cannot emphasize enough on how to use git properly.
> While these things seem very annoying at first, believe me that they will help.

Git is a version control system that intelligently tracks changes in files.
Git is particularly useful when you and a group of people are all making changes to the same files at the same time.

Typically, to do this in a Git-based workflow, you would:

- Create a branch to **_show the intent of your work_**.
- Create issues **_before_** you do the work/code.
- Make edits to the files independently and safely on your own personal branch.
- Close or update issues [with your commits or Merge Requests](https://docs.gitlab.com/user/project/issues/managing_issues/#closing-issues-automatically)
- Let Git intelligently merge your specific changes back into the main copy of files, so that your changes don't impact other people's updates.
- Let Git keep track of your and other people's changes, so you all stay working on the most up-to-date version of the project.

> [!IMPORTANT]
> Our `Main` branch is a **SACRED** branch. DO NOT PUSH CODE WITHOUT PROPER REVIEW FROM OTHER MEMBERS.

Please read these articles:

- [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)
- [Always start with an issue](https://web.archive.org/web/20230214040753/https://about.gitlab.com/blog/2016/03/03/start-with-an-issue/)
  - Try creating an issue now on what you want to do next.
  - Also if you don't see our issue board under the projects tab in our repo. Please contact Mingxi and ask to be added to the Project issue board.
- [Write good commit messages!](https://cbea.ms/git-commit/)
- [Issue board](https://about.gitlab.com/blog/announcing-the-gitlab-issue-board/)
  - While we are not using GitLab, GitHub has the same feature called "Project".
- [It's all connected in Gitlab](https://about.gitlab.com/2016/03/08/gitlab-tutorial-its-all-connected/)
  - Again, GitHub has the equivalent features at [here](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls)

As you incorporate these steps into your developer journey, you will be better equipped for real world team-coding.
All the industry experts follow some form of standards using GIT. You should learn to use it properly while you are here with us.

And [here is a longer video](https://www.youtube.com/watch?v=1ffBJ4sVUb4) that gives you more in-depth details on how GIT works.

Here is an [interactive](https://learngitbranching.js.org/?locale=en_US) Git simulator for you to practice.

### 3. Using the Terminal

Using the terminal, you can do a lot of stuff with it. I assure you that to get better at it you just have to use it daily. At first you might google a lot of stuff, and that is **okay!**.
All of us started out like that. Here are some of the common commands I use when working with CHATDKU:

- `ssh`: Used to connect to our server
- `git`: Working with GitHub
- `sftp`: ssh like file transferring
- `nvidia-smi`: Used to inspect GPUs

Again, just google these stuff and learn. Good luck! It will be worth it.

## Role-specific Guides

Please be careful when interacting with Docker. It hosts our Embedding Model, Vector Database, and Redis Database.

### Agent Logic

- DSPy for interacting with the LLM: https://dspy.ai/learn/
- For creating tools: https://github.com/Glitterccc/ChatDKU/issues/122
- Arize Phoenix for observability: https://arize.com/docs/phoenix

### Iterating on the agent with `devsync.sh`

Edit code on your laptop, then push and run it on the shared dev server in one
command. From the repo root:

```bash
./devsync.sh                                    # runs the agent
```

```bash
./devsync.sh chatdku/core/tools/your_file.py    # runs any file you're hacking on
```

The script rsyncs your working tree, runs `uv sync`, and drops you into a live
session on the remote. Your `.venv/`, `.env`, and `.git/` are left alone.

See [Documentations/DevSync.md](Documentations/DevSync.md) for configuration,
Windows-specific notes, and troubleshooting. If you're new, also skim
[Documentations/Shared-Secrets.md](Documentations/Shared-Secrets.md) — once an
admin adds you to `chatdku_devs`, all project secrets load into your remote
shell automatically, no `.env` copying needed.

### Document Ingestion

- Llamaindex for document ingestion: https://developers.llamaindex.ai/python/framework/getting_started/concepts
- ChromaDB for vector store: https://docs.trychroma.com/docs/overview/introduction
- Redis for keyword search: https://redis.io/docs/latest/develop/
