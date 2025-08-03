https://latent.space/p/self-improvement

## Task Manager Prompt

You are an AI Engineer agent with the ability to spin up many instances of yourself in parallel. This allows you to tackle a lot of tasks at once, but also creates some delegation issues. All the different instances are usually in separate git worktrees and cannot see eachother's work.

To make yourself more productive, you should create a new local tool that allows you and your instances to be in sync. This tool will only be accessed by yourself through cli, so make sure it ergonomically fits that use case. It should feel like a unix utility.

Think through what interfaces it would need, possible failure modes, and the way your agents will interact with it. Some use cases to keep in mind:

- You have a new task to work on, and want to create subtasks to hand off. Some of those subtasks might depend on eachother, and you want to make sure the agent who is blocked doesn't attempt to start until the other one is completed.
- While doing a task, you notice there could be an improvement to be done in the codebase but it is out of scope for your current changes. You do want to make a note of it for the future though. It should be easy for you to add the task and reference what file it referred to. 
- Whenever a task is done, the tracker should be updated. Also, all other outstanding tasks should be reviewed in case the new changes impact those in some way. For example one task might be looking to add a feature to an endpoint, but a task that just finished has now removed that endpoint. The agent working on that task should be notified in some way.

Also keep in mind the usual needs of tasks management like assignee, status, etc. 

Create a folder called `task-manager` in this folder and do all of your work inside of it.

## Codebase Analyzer Prompt

Opus 4 Result: https://github.com/FanaHOVA/codex-opus4/commit/8f1ce2946c6d7950657831ede94db429e7cb8905
GPT-5 Result: https://github.com/FanaHOVA/codex-gpt5/commit/25bbee8b30929d7433f7adfa3f3826997b9a3615

You are an AI Engineer agent with the ability to spin up many instances of yourself in parallel. Sometimes it leads to inconsistent code styles and approaches, which make it hard to maintain the codebase in the long run.

Every codebase you work in has explicit and implicit rules on how to write code. Your job is to analyze a codebase and extract different heuristics on how code should be written. You should then formalize it within a set of rules that can be automatically be checked against in the future. 

For things like linting, types, etc you can rely on existing popular tools like ESLint, Rubocop, etc depending on the language you are working in. Remember that these systems often allow you to create custom rules, so take advantage of that.

For more qualitative things, you can look at tools like https://danger.systems/, or even build your own tool for it. This would include rules like keeping controllers slim and isolating their logic to service objects, making sure we always have an index in a column that expects high query volume, etc.

Given that you will be doing this task across many codebases, start by creating a thorough plan document using Markdown that you can give your future self when presented with a new codebase to work with.  
