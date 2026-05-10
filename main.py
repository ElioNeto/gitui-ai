#!/usr/bin/env python3
"""
GitUI-AI — TUI para Git com commit gerado por IA
Requer: pip install textual gitpython httpx python-dotenv
"""

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Static, Button, Input, Label,
    ListView, ListItem, Log, TabbedContent, TabPane,
    TextArea
)
from textual.containers import (
    Horizontal, Vertical, ScrollableContainer
)
from textual.screen import ModalScreen
from textual.reactive import reactive
from textual import on, work
from textual.binding import Binding

import git
import os
import sys
import httpx
import asyncio
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─────────────────── helpers git ──────────────────

def get_repo(path: str = "."):
    try:
        return git.Repo(path, search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        return None


def get_diff(repo, staged: bool = True) -> str:
    try:
        if staged:
            return repo.git.diff("--cached", "--stat") + "\n" + repo.git.diff("--cached")
        else:
            return repo.git.diff("--stat") + "\n" + repo.git.diff()
    except Exception as e:
        return f"Erro ao obter diff: {e}"


def get_project_context(repo) -> str:
    ctx = []
    root = Path(repo.working_dir)
    for name in ["README.md", "README.rst", "pyproject.toml", "package.json", "Cargo.toml"]:
        f = root / name
        if f.exists():
            ctx.append(f.read_text(errors="ignore")[:800])
            break
    return "\n".join(ctx)[:1200]


# ─────────────────── IA commit (síncrono, chamado em thread) ──────────────────

def ai_generate_commit_sync(diff: str, context: str) -> str:
    """Wrapper síncrono — roda asyncio.run() em thread separada."""
    return asyncio.run(_ai_generate_commit_async(diff, context))


async def _ai_generate_commit_async(diff: str, context: str) -> str:
    groq_key      = os.getenv("GROQ_API_KEY")
    gemini_key    = os.getenv("GEMINI_API_KEY")
    openai_key    = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not any([groq_key, gemini_key, openai_key, anthropic_key]):
        return (
            "⚠️  Nenhuma API key configurada.\n"
            "Opções GRATUITAS (sem cartão):\n"
            "  GROQ_API_KEY   → console.groq.com\n"
            "  GEMINI_API_KEY → aistudio.google.com"
        )

    system_prompt = (
        "You are a Git expert. Generate ONE commit message following Conventional Commits "
        "(type(scope): concise description, max 72 chars). "
        "Optionally add a short body. Base yourself ONLY on the provided diff."
    )
    user_prompt = f"""Project context:
{context or "Not available"}

Git diff (staged):
{diff[:3000]}

Generate the commit message:"""

    try:
        # ── 1. Groq (GRATUITO) ──
        if groq_key:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 200,
                        "temperature": 0.3,
                    },
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()

        # ── 2. Google Gemini (GRATUITO) ──
        elif gemini_key:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"gemini-2.0-flash:generateContent?key={gemini_key}",
                    json={
                        "contents": [{
                            "parts": [{"text": system_prompt + "\n\n" + user_prompt}]
                        }],
                        "generationConfig": {"maxOutputTokens": 200, "temperature": 0.3},
                    },
                )
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        # ── 3. OpenAI (pago) ──
        elif openai_key:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 200,
                        "temperature": 0.3,
                    },
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()

        # ── 4. Anthropic (pago) ──
        elif anthropic_key:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 200,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
                r.raise_for_status()
                return r.json()["content"][0]["text"].strip()

    except Exception as e:
        return f"Erro IA ({type(e).__name__}): {e}"

    return "Nenhum provedor configurado."


# ─────────────────── Modals ──────────────────

class BranchModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Fechar")]

    def compose(self) -> ComposeResult:
        from textual.containers import Container
        with Container(id="modal-container"):
            yield Label("🌿 Nova branch", id="modal-title")
            yield Input(placeholder="nome-da-branch", id="branch-input")
            with Horizontal(id="modal-buttons"):
                yield Button("Criar", variant="success", id="create-btn")
                yield Button("Cancelar", variant="error", id="cancel-btn")

    @on(Button.Pressed, "#create-btn")
    def create_branch(self):
        name = self.query_one("#branch-input", Input).value.strip()
        if name:
            self.dismiss(name)

    @on(Button.Pressed, "#cancel-btn")
    def cancel(self):
        self.dismiss(None)


class RemoteModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Fechar")]

    def compose(self) -> ComposeResult:
        from textual.containers import Container
        with Container(id="modal-container"):
            yield Label("🔗 Adicionar Remote", id="modal-title")
            yield Input(placeholder="nome (ex: origin)", id="remote-name")
            yield Input(placeholder="URL do repositório", id="remote-url")
            with Horizontal(id="modal-buttons"):
                yield Button("Adicionar", variant="success", id="add-btn")
                yield Button("Cancelar", variant="error", id="cancel-btn")

    @on(Button.Pressed, "#add-btn")
    def add_remote(self):
        name = self.query_one("#remote-name", Input).value.strip()
        url = self.query_one("#remote-url", Input).value.strip()
        if name and url:
            self.dismiss((name, url))

    @on(Button.Pressed, "#cancel-btn")
    def cancel(self):
        self.dismiss(None)


# ─────────────────── App principal ──────────────────

class GitUIApp(App):
    CSS_PATH = "style.tcss"
    TITLE = "GitUI-AI"
    SUB_TITLE = "Git TUI com IA"

    BINDINGS = [
        Binding("q", "quit", "Sair"),
        Binding("r", "refresh", "Refresh"),
        Binding("f5", "refresh", "Refresh", show=False),
        Binding("c", "focus_commit", "Commit"),
        Binding("p", "git_push", "Push"),
        Binding("u", "git_pull", "Pull"),
        Binding("b", "new_branch", "Nova Branch"),
        Binding("a", "stage_all", "Stage all"),
        Binding("s", "ai_suggest", "Sugestão IA"),
        Binding("question_mark", "show_help", "Ajuda"),
    ]

    current_branch: reactive = reactive("")
    ai_loading: reactive = reactive(False)

    def __init__(self, path: str = "."):
        super().__init__()
        self.repo_path = path
        self.repo = get_repo(path)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            with Vertical(id="left-panel"):
                yield Static("📁 REPOSITÓRIO", classes="panel-title")
                yield Static("", id="repo-info")
                yield Static("🌿 BRANCHES", classes="panel-title")
                yield ScrollableContainer(ListView(id="branch-list"), id="branch-scroll")
                yield Static("🔗 REMOTES", classes="panel-title")
                yield ScrollableContainer(ListView(id="remote-list"), id="remote-scroll")

            with Vertical(id="center-panel"):
                with TabbedContent(id="main-tabs"):
                    with TabPane("📝 Staging", id="staging-tab"):
                        yield Static("UNSTAGED / UNTRACKED", classes="section-title")
                        yield ScrollableContainer(ListView(id="unstaged-list"), id="unstaged-scroll")
                        with Horizontal(id="staging-actions"):
                            yield Button("+ Stage All", id="stage-all-btn", variant="success")
                            yield Button("- Unstage All", id="unstage-all-btn", variant="warning")
                        yield Static("STAGED", classes="section-title")
                        yield ScrollableContainer(ListView(id="staged-list"), id="staged-scroll")

                    with TabPane("💬 Commit", id="commit-tab"):
                        yield Static("Mensagem de commit (editável)", classes="section-title")
                        yield TextArea("", id="commit-msg")
                        with Horizontal(id="commit-actions"):
                            yield Button("✨ Sugestão IA", id="ai-btn", variant="primary")
                            yield Button("✔ Commit", id="commit-btn", variant="success")
                            yield Button("🗑 Limpar", id="clear-btn")
                        yield Static("", id="ai-status")

                    with TabPane("📜 Log", id="log-tab"):
                        yield ScrollableContainer(Log(id="git-log", auto_scroll=False), id="log-scroll")
                        with Horizontal(id="log-actions"):
                            yield Button("🔄 Atualizar", id="refresh-log-btn")

                    with TabPane("🔍 Diff", id="diff-tab"):
                        yield ScrollableContainer(Log(id="diff-view", auto_scroll=False), id="diff-scroll")
                        with Horizontal(id="diff-actions"):
                            yield Button("Staged diff", id="staged-diff-btn", variant="primary")
                            yield Button("Working diff", id="working-diff-btn")

            with Vertical(id="right-panel"):
                yield Static("⚡ AÇÕES RÁPIDAS", classes="panel-title")
                with Vertical(id="quick-actions"):
                    yield Button("⬆ Push", id="push-btn", variant="primary")
                    yield Button("⬇ Pull", id="pull-btn", variant="primary")
                    yield Button("🔀 Fetch", id="fetch-btn")
                    yield Button("🌿 Nova Branch", id="new-branch-btn")
                    yield Button("🔗 Add Remote", id="add-remote-btn")
                    yield Button("📦 Stash", id="stash-btn")
                    yield Button("📤 Pop Stash", id="stash-pop-btn")
                yield Static("📊 STATUS", classes="panel-title")
                yield ScrollableContainer(Log(id="status-log", auto_scroll=False), id="status-scroll")

        yield Footer()

    def on_mount(self) -> None:
        self.refresh_all()

    def action_refresh(self) -> None:
        self.refresh_all()

    def refresh_all(self) -> None:
        if not self.repo:
            self.query_one("#repo-info", Static).update("[red]Nenhum repositório Git encontrado.[/red]")
            return
        self._update_repo_info()
        self._update_branches()
        self._update_remotes()
        self._update_staging()
        self._update_git_log()
        self._update_status()

    def _update_repo_info(self):
        repo = self.repo
        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = "HEAD detached"
        self.current_branch = branch
        ahead = behind = 0
        try:
            ahead = len(list(repo.iter_commits(f"origin/{branch}..HEAD")))
            behind = len(list(repo.iter_commits(f"HEAD..origin/{branch}")))
        except Exception:
            pass
        info = (
            f"[bold cyan]{Path(repo.working_dir).name}[/bold cyan]\n"
            f"Branch: [green]{branch}[/green]\n"
            f"↑{ahead} ahead  ↓{behind} behind\n"
            f"[dim]{repo.working_dir}[/dim]"
        )
        self.query_one("#repo-info", Static).update(info)
        self.sub_title = f"branch: {branch}"

    def _update_branches(self):
        lv = self.query_one("#branch-list", ListView)
        lv.clear()
        if not self.repo:
            return
        try:
            current = self.repo.active_branch.name
        except Exception:
            current = ""
        for b in self.repo.branches:
            mark = "→ " if b.name == current else "  "
            color = "green" if b.name == current else "white"
            lv.append(ListItem(Static(f"[{color}]{mark}{b.name}[/{color}]")))

    def _update_remotes(self):
        lv = self.query_one("#remote-list", ListView)
        lv.clear()
        if not self.repo:
            return
        for r in self.repo.remotes:
            lv.append(ListItem(Static(f"[cyan]{r.name}[/cyan] [dim]{r.url}[/dim]")))
        if not self.repo.remotes:
            lv.append(ListItem(Static("[dim]Nenhum remote configurado[/dim]")))

    def _update_staging(self):
        repo = self.repo
        if not repo:
            return
        unstaged_lv = self.query_one("#unstaged-list", ListView)
        staged_lv = self.query_one("#staged-list", ListView)
        unstaged_lv.clear()
        staged_lv.clear()
        for item in repo.index.diff(None):
            color = {"M": "yellow", "D": "red", "A": "green"}.get(item.change_type, "white")
            unstaged_lv.append(ListItem(Static(f"[{color}]{item.change_type}[/{color}] {item.a_path}")))
        for f in repo.untracked_files:
            unstaged_lv.append(ListItem(Static(f"[dim]?[/dim] {f}")))
        try:
            for item in repo.index.diff("HEAD"):
                color = {"M": "yellow", "D": "red", "A": "green"}.get(item.change_type, "white")
                staged_lv.append(ListItem(Static(f"[{color}]{item.change_type}[/{color}] {item.a_path}")))
        except Exception:
            for entry in repo.index.entries:
                staged_lv.append(ListItem(Static(f"[green]A[/green] {entry[0]}")))

    def _update_git_log(self):
        log_widget = self.query_one("#git-log", Log)
        log_widget.clear()
        if not self.repo:
            return
        try:
            for c in self.repo.iter_commits(max_count=50):
                dt = datetime.fromtimestamp(c.committed_date).strftime("%d/%m %H:%M")
                sha = c.hexsha[:7]
                msg = c.message.splitlines()[0][:60]
                author = c.author.name[:15]
                log_widget.write_line(f"[yellow]{sha}[/yellow] [dim]{dt}[/dim] [cyan]{author:<15}[/cyan] {msg}")
        except Exception as e:
            log_widget.write_line(f"[red]Erro: {e}[/red]")

    def _update_status(self):
        status_log = self.query_one("#status-log", Log)
        status_log.clear()
        if not self.repo:
            return
        try:
            status = self.repo.git.status("--short")
            for line in status.splitlines():
                if line.startswith("M"):
                    status_log.write_line(f"[yellow]{line}[/yellow]")
                elif line.startswith(("A", "?")):
                    status_log.write_line(f"[green]{line}[/green]")
                elif line.startswith("D"):
                    status_log.write_line(f"[red]{line}[/red]")
                else:
                    status_log.write_line(line)
            if not status.strip():
                status_log.write_line("[dim]✓ Working tree limpo[/dim]")
        except Exception as e:
            status_log.write_line(f"[red]{e}[/red]")

    # ── Staging ──

    def action_stage_all(self) -> None:
        self._stage_all()

    @on(Button.Pressed, "#stage-all-btn")
    def _stage_all(self) -> None:
        if not self.repo:
            return
        try:
            self.repo.git.add("-A")
            self.notify("✅ Todos os arquivos staged", severity="information")
            self.refresh_all()
        except Exception as e:
            self.notify(f"Erro: {e}", severity="error")

    @on(Button.Pressed, "#unstage-all-btn")
    def _unstage_all(self) -> None:
        if not self.repo:
            return
        try:
            self.repo.git.reset("HEAD")
            self.notify("⚠️ Tudo unstaged", severity="warning")
            self.refresh_all()
        except Exception as e:
            self.notify(f"Erro: {e}", severity="error")

    # ── Commit ──

    def action_focus_commit(self) -> None:
        self.query_one("#main-tabs").active = "commit-tab"
        self.query_one("#commit-msg", TextArea).focus()

    @on(Button.Pressed, "#clear-btn")
    def clear_commit(self) -> None:
        self.query_one("#commit-msg", TextArea).text = ""

    @on(Button.Pressed, "#commit-btn")
    def do_commit(self) -> None:
        msg = self.query_one("#commit-msg", TextArea).text.strip()
        if not msg:
            self.notify("Digite uma mensagem de commit", severity="warning")
            return
        if not self.repo:
            return
        try:
            self.repo.index.commit(msg)
            self.notify(f"✅ Commit: {msg[:50]}", severity="information")
            self.query_one("#commit-msg", TextArea).text = ""
            self.refresh_all()
        except Exception as e:
            self.notify(f"Erro no commit: {e}", severity="error")

    # ── IA (thread worker — evita conflito com event loop do Textual) ──

    def action_ai_suggest(self) -> None:
        self.query_one("#main-tabs").active = "commit-tab"
        self._run_ai_suggest()

    @on(Button.Pressed, "#ai-btn")
    def _run_ai_suggest(self) -> None:
        if self.ai_loading:
            return
        self.ai_loading = True
        self.query_one("#ai-status", Static).update("[yellow]⏳ Consultando IA...[/yellow]")
        self._ai_worker()

    @work(thread=True, exclusive=True)
    def _ai_worker(self) -> None:
        if not self.repo:
            self.call_from_thread(
                self.query_one("#ai-status", Static).update,
                "[red]Sem repositório.[/red]"
            )
            self.ai_loading = False
            return
        diff = get_diff(self.repo, staged=True)
        if not diff.strip() or diff.strip() == "\n":
            diff = get_diff(self.repo, staged=False)
        context = get_project_context(self.repo)
        msg = ai_generate_commit_sync(diff, context)
        self.call_from_thread(self._apply_ai_msg, msg)
        self.ai_loading = False

    def _apply_ai_msg(self, msg: str) -> None:
        self.query_one("#commit-msg", TextArea).text = msg
        self.query_one("#ai-status", Static).update(
            "[green]✅ Sugestão aplicada! Revise e edite antes de commitar.[/green]"
        )
        self.notify("✨ Mensagem gerada pela IA", severity="information")

    # ── Push / Pull / Fetch (thread workers) ──

    def action_git_push(self) -> None:
        self._do_push()

    @on(Button.Pressed, "#push-btn")
    def _do_push(self) -> None:
        if not self.repo:
            return
        self._push_worker()

    @work(thread=True, exclusive=True)
    def _push_worker(self) -> None:
        self.call_from_thread(self.notify, "⬆ Fazendo push...", severity="information")
        try:
            self.repo.remote("origin").push()
            self.call_from_thread(self.notify, "✅ Push concluído!", severity="information")
        except Exception as e:
            self.call_from_thread(self.notify, f"Erro push: {e}", severity="error")
        self.call_from_thread(self.refresh_all)

    def action_git_pull(self) -> None:
        self._do_pull()

    @on(Button.Pressed, "#pull-btn")
    def _do_pull(self) -> None:
        if not self.repo:
            return
        self._pull_worker()

    @work(thread=True, exclusive=True)
    def _pull_worker(self) -> None:
        self.call_from_thread(self.notify, "⬇ Fazendo pull...", severity="information")
        try:
            self.repo.remote("origin").pull()
            self.call_from_thread(self.notify, "✅ Pull concluído!", severity="information")
        except Exception as e:
            self.call_from_thread(self.notify, f"Erro pull: {e}", severity="error")
        self.call_from_thread(self.refresh_all)

    @on(Button.Pressed, "#fetch-btn")
    def _do_fetch(self) -> None:
        if not self.repo:
            return
        self._fetch_worker()

    @work(thread=True, exclusive=True)
    def _fetch_worker(self) -> None:
        self.call_from_thread(self.notify, "🔀 Fazendo fetch...", severity="information")
        try:
            for remote in self.repo.remotes:
                remote.fetch()
            self.call_from_thread(self.notify, "✅ Fetch concluído!", severity="information")
        except Exception as e:
            self.call_from_thread(self.notify, f"Erro fetch: {e}", severity="error")
        self.call_from_thread(self.refresh_all)

    # ── Diff ──

    @on(Button.Pressed, "#staged-diff-btn")
    def show_staged_diff(self) -> None:
        self.query_one("#main-tabs").active = "diff-tab"
        diff_view = self.query_one("#diff-view", Log)
        diff_view.clear()
        if not self.repo:
            return
        try:
            diff = self.repo.git.diff("--cached", "--color=never")
            for line in diff.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    diff_view.write_line(f"[green]{line}[/green]")
                elif line.startswith("-") and not line.startswith("---"):
                    diff_view.write_line(f"[red]{line}[/red]")
                elif line.startswith("@@"):
                    diff_view.write_line(f"[cyan]{line}[/cyan]")
                else:
                    diff_view.write_line(line)
        except Exception as e:
            diff_view.write_line(f"[red]{e}[/red]")

    @on(Button.Pressed, "#working-diff-btn")
    def show_working_diff(self) -> None:
        self.query_one("#main-tabs").active = "diff-tab"
        diff_view = self.query_one("#diff-view", Log)
        diff_view.clear()
        if not self.repo:
            return
        try:
            diff = self.repo.git.diff("--color=never")
            for line in diff.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    diff_view.write_line(f"[green]{line}[/green]")
                elif line.startswith("-") and not line.startswith("---"):
                    diff_view.write_line(f"[red]{line}[/red]")
                elif line.startswith("@@"):
                    diff_view.write_line(f"[cyan]{line}[/cyan]")
                else:
                    diff_view.write_line(line)
        except Exception as e:
            diff_view.write_line(f"[red]{e}[/red]")

    # ── Branch / Remote ──

    def action_new_branch(self) -> None:
        self.push_screen(BranchModal(), self._on_branch_created)

    @on(Button.Pressed, "#new-branch-btn")
    def _open_branch_modal(self) -> None:
        self.push_screen(BranchModal(), self._on_branch_created)

    def _on_branch_created(self, name) -> None:
        if name and self.repo:
            try:
                self.repo.create_head(name).checkout()
                self.notify(f"✅ Branch criada: {name}", severity="information")
                self.refresh_all()
            except Exception as e:
                self.notify(f"Erro: {e}", severity="error")

    @on(Button.Pressed, "#add-remote-btn")
    def _open_remote_modal(self) -> None:
        self.push_screen(RemoteModal(), self._on_remote_added)

    def _on_remote_added(self, data) -> None:
        if data and self.repo:
            name, url = data
            try:
                self.repo.create_remote(name, url)
                self.notify(f"✅ Remote adicionado: {name}", severity="information")
                self._update_remotes()
            except Exception as e:
                self.notify(f"Erro: {e}", severity="error")

    # ── Stash ──

    @on(Button.Pressed, "#stash-btn")
    def _do_stash(self) -> None:
        if not self.repo:
            return
        try:
            self.repo.git.stash()
            self.notify("📦 Stash criado", severity="information")
            self.refresh_all()
        except Exception as e:
            self.notify(f"Erro: {e}", severity="error")

    @on(Button.Pressed, "#stash-pop-btn")
    def _do_stash_pop(self) -> None:
        if not self.repo:
            return
        try:
            self.repo.git.stash("pop")
            self.notify("📤 Stash restaurado", severity="information")
            self.refresh_all()
        except Exception as e:
            self.notify(f"Erro: {e}", severity="error")

    # ── Log / Help ──

    @on(Button.Pressed, "#refresh-log-btn")
    def refresh_log(self) -> None:
        self._update_git_log()

    def action_show_help(self) -> None:
        self.notify(
            "q=sair  r=refresh  c=commit  p=push  u=pull  b=branch  a=stage-all  s=IA  ?=ajuda",
            severity="information",
            timeout=8,
        )


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    GitUIApp(path=path).run()


if __name__ == "__main__":
    main()
