Good move. The best way to avoid slow conversations and confusion is to have a **portable project setup doc** so any machine (like your work computer) can run the system exactly the same way.

Below is a **clean project bootstrap guide** for your Unity-Agent + AinaQuest workflow.

You can save this as something like:

```
Unity-Agent-Setup.md
```

in your repo.

---

# Unity Agent + AinaQuest Full Setup (Work Computer)

This guide sets up the **agentic Unity development system** used to assist development of the **AinaQuest Unity card game**.

The system consists of:

1. **Unity Project**
2. **Unity Agent (Python orchestration system)**
3. **Discord Bot interface**
4. **Git integration**
5. **Patch proposal / approval system**

---

# 1. Repositories

Clone both repos.

```
git clone git@github.com:tclum/unity-agent.git
git clone git@github.com:tclum/ainaquest.git
```

Example directory layout:

```
~/Projects
    unity-agent
    ainaquest
```

---

# 2. Python Environment

Navigate to the Unity Agent repo:

```
cd unity-agent
```

Create a virtual environment.

```
python3 -m venv venv
```

Activate it.

Mac/Linux:

```
source venv/bin/activate
```

Windows:

```
venv\Scripts\activate
```

---

# 3. Install Dependencies

Install the Python dependencies.

```
pip install -r requirements.txt
```

Main libraries used:

- discord.py
- python-dotenv
- openai (if LLM enabled)
- rich
- requests

---

# 4. Environment Variables

Create a `.env` file in the root of `unity-agent`.

```
unity-agent/.env
```

Example:

```
DISCORD_BOT_TOKEN=MTQ4NTM3NTI3MDIyNjYyODc1OQ.GVWSN7.ZaCEArpbIJ57cDyJjc-QKRcGfR8gzzGSCwiCRo
OPENAI_API_KEY=YOUR_API_KEY_OPTIONAL
```

Notes:

- `DISCORD_BOT_TOKEN` **required**
- `OPENAI_API_KEY` optional but required for LLM patch generation

---

# 5. Unity Project Configuration

Inside:

```
unity-agent/projects
```

There should be a configuration file for the AinaQuest project.

Example:

```
projects/ainaquest.json
```

Example configuration:

```json
{
  "project_id": "ainaquest",
  "project_root": "/Users/YOUR_USERNAME/Projects/ainaquest",
  "unity_project": true
}
```

Update the **path** to match your machine.

Example on your work computer:

```
/Users/workusername/Projects/ainaquest
```

---

# 6. Storage Directory

The agent stores tasks and proposals locally.

Directory:

```
unity-agent/storage
```

Files created automatically:

```
storage/tasks.json
storage/proposals.json
```

---

# 7. Running the Agent

Start the system from the `unity-agent` root.

```
python main.py
```

You should see:

```
[Orchestrator] Started.
[Discord] Logged in as Unity Agent
```

---

# 8. Discord Commands

Once running, control the agent from Discord.

### Set project

```
/project ainaquest
```

### Create a task

```
/task fix results ui bug
```

### View tasks

```
/queue
```

### View patch proposals

```
/proposals
```

### Inspect a proposal

```
/proposal 5
```

### Apply a patch

```
/approve 5
```

### Reject a patch

```
/reject 5
```

---

# 9. Patch Pipeline

The system uses a controlled patch workflow.

```
task
↓
planner
↓
code_agent
↓
LLM patch proposal
↓
validator
↓
proposal_store
↓
Discord proposal
↓
human approval
↓
git commit
```

No code changes are applied automatically.

All patches require `/approve`.

---

# 10. Git Integration

When a proposal is approved:

```
/approve 5
```

The agent will:

1. apply the patch
2. create a backup of the original file
3. commit the change

Example commit:

```
agent approved patch proposal 5
```

---

# 11. Unity Project Location

Your Unity project should remain in:

```
ainaquest/
```

Unity project structure:

```
ainaquest
  Assets
    Scripts
      UI
      Core
      Managers
  ProjectSettings
  Packages
```

Key scripts the agent often edits:

```
Assets/Scripts/UI/ResultsUI.cs
Assets/Scripts/UI/HumanTurnUI.cs
Assets/Scripts/UI/RevealUI.cs
Assets/Scripts/UI/FieldUI.cs
Assets/Scripts/UI/PlayerAreaUI.cs
```

---

# 12. Unity Log Detection

The agent reads the Unity log to diagnose issues.

Mac path:

```
~/Library/Logs/Unity/Editor.log
```

The agent scans this file for:

```
NullReferenceException
MissingReferenceException
Error
ResultsUI
ShowResults
```

---

# 13. Important Agent Modules

Key directories:

```
unity-agent/core
unity-agent/agents
unity-agent/integrations
```

Important files:

```
agents/code_agent.py
core/proposal_store.py
core/proposal_validator.py
core/diff_preview.py
core/project_search.py
integrations/discord_bot.py
```

---

# 14. Typical Workflow

Example debugging flow:

```
/task fix results ui bug
```

Agent:

1. scans Unity logs
2. scans codebase
3. generates patch proposal
4. posts proposal to Discord

You then:

```
/proposal 5
```

Review diff.

If good:

```
/approve 5
```

If incorrect:

```
/reject 5
```

---

# 15. Recommended Directory Layout

Example development layout:

```
~/Projects
   unity-agent
   ainaquest
```

---

# 16. Updating Code

Pull latest updates:

```
git pull
```

Then restart the agent.

---

# 17. Restarting the Agent

Stop:

```
CTRL+C
```

Restart:

```
python main.py
```

---

# 18. Future Improvements Planned

Current roadmap:

1. stronger validator rules
2. multi-file analysis before patching
3. Unity-aware code understanding
4. scene hierarchy inspection
5. prefab analysis
6. automatic reproduction of Unity errors
7. safer patch diff heuristics

---

# 19. Repos

Unity Agent:

```
https://github.com/tclum/unity-agent
```

AinaQuest Game:

```
https://github.com/tclum/ainaquest
```

---

# 20. Quick Test

After setup run:

```
/projects
/project ainaquest
/task fix results ui bug
```

If the bot replies and the orchestrator processes the task, the system is working.

---

If you'd like, I can also give you a **much better dev setup** that will make this system _10× easier to maintain_:

- a **single mono-repo layout**
- automatic project path detection
- automatic Unity log detection
- a **one command startup script**

That removes almost all machine-specific setup.
