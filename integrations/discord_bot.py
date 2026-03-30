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


# ─── Formatting helpers ─────────────────────────────────────────────────────

def _format_validation_block(proposal: dict) -> str:
    validation = proposal.get("validation") or {}
    is_valid = validation.get("is_valid", True)
    errors = validation.get("errors", [])
    warnings = validation.get("warnings", [])
    evidence_reasons = validation.get("evidence_reasons", [])

    lines = []

    if is_valid:
        if warnings:
            lines.append(f"Validation: passed with {len(warnings)} warning(s)")
        else:
            lines.append("Validation: passed")
    else:
        lines.append("Validation: failed")

    if evidence_reasons:
        lines.append("Evidence:")
        for reason in evidence_reasons:
            lines.append(f"- {reason}")

    if errors:
        lines.append("Errors:")
        for err in errors:
            lines.append(f"- {err}")

    if warnings:
        lines.append("Warnings:")
        for warn in warnings:
            lines.append(f"- {warn}")

    return "\n".join(lines)


def _format_proposal_line(proposal: dict) -> str:
    validation = proposal.get("validation") or {}
    warnings = validation.get("warnings", [])
    errors = validation.get("errors", [])

    validation_suffix = ""
    if errors:
        validation_suffix = f" | validation failed ({len(errors)} error(s))"
    elif warnings:
        validation_suffix = f" | {len(warnings)} warning(s)"

    return (
        f"#{proposal['id']} | task {proposal['task_id']} | "
        f"[{proposal['status']}] {proposal['summary']}{validation_suffix}"
    )


async def _create_task(ctx, description: str, task_type: str, label: str):
    """Shared helper for all task creation commands."""
    project_id = get_active_project()

    created_task = add_task(
        project_id=project_id,
        title=description,
        task_type=task_type,
        channel_id=ctx.channel.id,
    )

    await ctx.send(
        f"Task #{created_task['id']} created.\n"
        f"Type: `{label}`\n"
        f"Project: `{project_id}`\n"
        f"Title: {created_task['title']}"
    )


# ─── Bot events ─────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    set_bot_instance(bot)
    print(f"[Discord] Logged in as {bot.user}")


# ─── Project commands ────────────────────────────────────────────────────────

@bot.command(name="projects")
async def projects(ctx):
    items = list_projects()
    if not items:
        await ctx.send("No projects found.")
        return
    await ctx.send("Available projects:\n" + "\n".join(f"- {p}" for p in items))


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


# ─── Task commands ───────────────────────────────────────────────────────────

@bot.command(name="task")
async def task(ctx, *, description: str):
    """
    Code task — bug fixes, logic changes, script patches.
    Example: /task fix null reference in GameManager
    """
    await _create_task(ctx, description, task_type="code", label="Code")


@bot.command(name="taskprefab")
async def taskprefab(ctx, *, description: str):
    """
    Prefab/asset task — Inspector wiring, ScriptableObject field values,
    prefab component changes, field references.
    Example: /taskprefab set Kalo base points to 30
    Example: /taskprefab assign artwork to all cards
    Example: /taskprefab wire Background reference in CardButtonPrefab
    """
    await _create_task(ctx, description, task_type="prefab", label="Prefab/Asset")


@bot.command(name="taskart")
async def taskart(ctx, *, description: str):
    """
    Art task — generative art, artwork creation, visual design.
    Example: /taskart generate card art for Kalo in watercolor style
    """
    await _create_task(ctx, description, task_type="art", label="Art")


@bot.command(name="taskdata")
async def taskdata(ctx, *, description: str):
    """
    Data task — bulk card data updates, game settings, balance changes.
    Alias for prefab tasks focused on ScriptableObject data.
    Example: /taskdata set all native card base points to 15
    Example: /taskdata set Guinea Grass card type to Invasive
    """
    await _create_task(ctx, description, task_type="prefab", label="Data")


# ─── Queue command ───────────────────────────────────────────────────────────

@bot.command(name="queue")
async def queue(ctx):
    tasks = load_tasks()
    if not tasks:
        await ctx.send("No tasks in queue.")
        return

    lines = []
    for t in tasks[-10:]:
        lines.append(
            f"#{t['id']} | {t['project_id']} | [{t['status']}] [{t.get('type','?')}] {t['title']}"
        )
    await ctx.send("\n".join(lines))


# ─── Proposal commands ───────────────────────────────────────────────────────

@bot.command(name="approve")
async def approve(ctx, proposal_id: int):
    proposal = get_proposal(proposal_id)

    if proposal is None:
        await ctx.send(f"Proposal `{proposal_id}` not found.")
        return

    if proposal["status"] != "pending":
        await ctx.send(f"Proposal `{proposal_id}` is not pending.")
        return

    validation = proposal.get("validation") or {}
    is_valid = validation.get("is_valid", True)

    if not is_valid:
        await ctx.send(
            f"Proposal `{proposal_id}` cannot be approved because validation failed.\n\n"
            f"{_format_validation_block(proposal)}"
        )
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
    validation_text = _format_validation_block(proposal)

    await ctx.send(
        f"Approved and applied proposal `{proposal_id}`.\n"
        f"File: {proposal['file_path']}\n"
        f"Backup: {backup_path if backup_path else 'not needed'}\n\n"
        f"{validation_text}"
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
        lines.append(_format_proposal_line(p))
    await ctx.send("\n".join(lines))


@bot.command(name="proposal")
async def proposal(ctx, proposal_id: int):
    proposal = get_proposal(proposal_id)

    if proposal is None:
        await ctx.send(f"Proposal `{proposal_id}` not found.")
        return

    validation_text = _format_validation_block(proposal)

    await ctx.send(
        f"Proposal #{proposal['id']}\n"
        f"Task ID: {proposal['task_id']}\n"
        f"Project: {proposal['project_id']}\n"
        f"File: {proposal['file_path']}\n"
        f"Status: {proposal['status']}\n"
        f"Summary: {proposal['summary']}\n\n"
        f"{validation_text}"
    )


# ─── Help command ────────────────────────────────────────────────────────────

@bot.command(name="commands")
async def show_commands(ctx):
    await ctx.send(
        "**Unity Agent Commands**\n\n"
        "**Task Commands:**\n"
        "`/task <description>` — Code fix, bug patch, script logic change\n"
        "`/taskprefab <description>` — Inspector wiring, prefab fields, asset references\n"
        "`/taskdata <description>` — ScriptableObject data, card values, game settings\n"
        "`/taskart <description>` — Generative art, visual design\n\n"
        "**Proposal Commands:**\n"
        "`/approve <id>` — Apply a high-risk patch proposal\n"
        "`/reject <id>` — Discard a patch proposal\n"
        "`/proposals` — List recent proposals\n"
        "`/proposal <id>` — View proposal details\n\n"
        "**Project Commands:**\n"
        "`/project` — Show active project\n"
        "`/project <id>` — Switch active project\n"
        "`/projects` — List all projects\n"
        "`/queue` — View task queue\n"
    )


def run_bot():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN missing in .env")
    bot.run(token)
