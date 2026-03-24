import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from core.project_manager import get_active_project, set_active_project
from core.task_queue import add_task, load_tasks
from core.config_loader import (
    list_projects,
    project_exists,
    load_project_config,
)
from core.proposal_store import (
    get_proposal,
    update_proposal_status,
    list_proposals,
)
from core.proposal_applier import apply_proposal_file
from integrations.git_manager import git_commit_files
from integrations.discord_notifier import set_bot_instance

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    set_bot_instance(bot)
    print(f"[Discord] Logged in as {bot.user}")


@bot.command(name="projects")
async def projects(ctx):
    items = list_projects()

    if not items:
        await ctx.send("No projects found.")
        return

    await ctx.send(
        "Available projects:\n" + "\n".join(f"- {p}" for p in items)
    )


@bot.command(name="project")
async def project(ctx, project_id: str = None):
    if project_id is None:
        await ctx.send(f"Active project: `{get_active_project()}`")
        return

    if not project_exists(project_id):
        await ctx.send(f"Project `{project_id}` not found.")
        return

    set_active_project(project_id)
    await ctx.send(f"Active project set to `{project_id}`")


@bot.command(name="task")
async def task(ctx, *, description: str):
    project_id = get_active_project()

    created_task = add_task(
        project_id=project_id,
        title=description,
        channel_id=ctx.channel.id
    )

    await ctx.send(
        f"Task #{created_task['id']} created.\n"
        f"Project: `{project_id}`\n"
        f"Title: {created_task['title']}"
    )


@bot.command(name="queue")
async def queue(ctx):
    tasks = load_tasks()

    if not tasks:
        await ctx.send("No tasks in queue.")
        return

    lines = []
    for t in tasks[-10:]:
        lines.append(
            f"#{t['id']} | {t['project_id']} | [{t['status']}] {t['title']}"
        )

    await ctx.send("\n".join(lines))


@bot.command(name="approve")
async def approve(ctx, proposal_id: int):
    proposal = get_proposal(proposal_id)

    if proposal is None:
        await ctx.send(f"Proposal `{proposal_id}` not found.")
        return

    if proposal["status"] != "pending":
        await ctx.send(f"Proposal `{proposal_id}` is not pending.")
        return

    backup_path = apply_proposal_file(
        proposal["file_path"],
        proposal["new_content"]
    )

    project_config = load_project_config(proposal["project_id"])
    git_commit_files(
        project_config,
        [proposal["file_path"]],
        f"agent approved patch proposal {proposal_id}"
    )

    update_proposal_status(proposal_id, "applied")

    await ctx.send(
        f"Approved and applied proposal `{proposal_id}`.\n"
        f"File: {proposal['file_path']}\n"
        f"Backup: {backup_path if backup_path else 'not needed'}"
    )


@bot.command(name="reject")
async def reject(ctx, proposal_id: int):
    proposal = get_proposal(proposal_id)

    if proposal is None:
        await ctx.send(f"Proposal `{proposal_id}` not found.")
        return

    if proposal["status"] != "pending":
        await ctx.send(f"Proposal `{proposal_id}` is not pending.")
        return

    update_proposal_status(proposal_id, "rejected")

    await ctx.send(f"Rejected proposal `{proposal_id}`.")


@bot.command(name="proposals")
async def proposals(ctx, status: str = None):
    items = list_proposals(status=status)

    if not items:
        await ctx.send("No proposals found.")
        return

    lines = []
    for p in items[-10:]:
        lines.append(
            f"#{p['id']} | task {p['task_id']} | [{p['status']}] {p['summary']}"
        )

    await ctx.send("\n".join(lines))


def run_bot():
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        raise ValueError("DISCORD_BOT_TOKEN missing in .env")

    bot.run(token)