#!/usr/bin/env python3
"""Terminal UI for the ChatDKU agent.

Run:
    python -m chatdku.core.tui
"""

from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path

import pyfiglet
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, Static

from chatdku.core.agent import build_agent

_LOGO_PATH = Path(__file__).parent / "ascii_logo"


def _build_splash() -> Table:
    """Build the startup splash: ANSI logo beside a figlet 'ChatDKU' title."""
    try:
        logo_text = Text.from_ansi(_LOGO_PATH.read_text())
    except OSError:
        logo_text = Text("")

    figlet_str = "\n" * 4 + pyfiglet.figlet_format("ChatDKU", font="slant")
    title_text = Text(figlet_str, style="bold #4aa7ff")

    grid = Table.grid(padding=(0, 2))
    grid.add_column(no_wrap=True)
    grid.add_column(no_wrap=True)
    grid.add_row(logo_text, title_text)
    return grid


class Message(Static):
    """A single chat bubble with a rounded, color-coded border."""

    DEFAULT_CSS = """
    Message {
        border: round #3a3f4b;
        background: transparent;
        padding: 0 1;
        margin: 0 2;
        width: auto;
        max-width: 90%;
        height: auto;
    }
    Message.user     { border: round #7fe684; color: #d6f5d6; }
    Message.agent    { border: round #4aa7ff; color: #d6e6ff; }
    Message.system   { border: round #5c616d; color: #9aa0ab; }
    Message.pending  { border: round #4a4f5a; color: #7c8290; }
    """

    def __init__(self, role: str, content: str) -> None:
        super().__init__(self._format(role, content), markup=False)
        self.role = role
        self.add_class(role)

    @staticmethod
    def _format(role: str, content: str) -> str:
        label = {
            "user": "You",
            "agent": "ChatDKU",
            "system": "System",
            "pending": "ChatDKU",
        }.get(role, role)
        return f"[{label}]\n{content}"

    def update_content(self, role: str, content: str) -> None:
        self.update(self._format(role, content))


class ChatDKUApp(App):
    ENABLE_COMMAND_PALETTE = True
    COLOR_SYSTEM = "truecolor"

    CSS = """
    Screen { layout: vertical; background: transparent; }
    Header { background: #1a1d23; color: #c7cbd4; }
    Footer { background: #1a1d23; color: #8a909c; }
    #log { height: 1fr; background: transparent; }
    #input {
        dock: bottom;
        margin: 0 1 1 1;
        border: round #3a3f4b;
        background: transparent;
        color: #d6dae2;
    }
    #input:focus { border: round #7ab7ff; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear", "Clear"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.agent = None  # built lazily in a worker
        self.queue: deque[str] = deque()
        self.busy = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield VerticalScroll(id="log")
        yield Input(
            placeholder="Ask about DKU…  (Enter to send, Ctrl+C to quit)", id="input"
        )
        yield Footer()

    async def on_mount(self) -> None:
        self.title = "ChatDKU"
        self.sub_title = "TUI"
        await self._post("system", "Booting agent… (this may take a few seconds)")
        self.query_one("#input", Input).focus()
        self.run_worker(self._boot, thread=True, exclusive=True, group="boot")

    def _boot(self) -> None:
        self.agent = build_agent(streaming=False)
        self.call_from_thread(self._boot_done)

    async def _boot_done(self) -> None:
        log = self.query_one("#log", VerticalScroll)
        await log.mount(Static(_build_splash()))
        log.scroll_end(animate=False)
        await self._post("system", "Ready.")

    async def _post(self, role: str, content: str) -> Message:
        msg = Message(role, content)
        log = self.query_one("#log", VerticalScroll)
        await log.mount(msg)
        log.scroll_end(animate=False)
        return msg

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        await self._post("user", text)
        self.queue.append(text)
        if not self.busy:
            await self._drain()

    async def _drain(self) -> None:
        while self.queue:
            query = self.queue.popleft()
            self.busy = True
            pending = await self._post("pending", "thinking…")
            # Wait for boot before answering.
            while self.agent is None:
                await asyncio.sleep(0.1)
            loop = asyncio.get_running_loop()
            try:
                answer = await loop.run_in_executor(None, self._run_agent, query)
            except Exception as e:
                answer = f"[error] {e}"
            pending.update_content("agent", answer)
            pending.remove_class("pending")
            pending.add_class("agent")
            self.query_one("#log", VerticalScroll).scroll_end(animate=False)
        self.busy = False

    def _run_agent(self, query: str) -> str:
        result = self.agent(current_user_message=query)
        response = result.response
        if isinstance(response, str):
            return response
        return "".join(response)

    async def action_clear(self) -> None:
        log = self.query_one("#log", VerticalScroll)
        await log.remove_children()


def main() -> None:
    ChatDKUApp().run()


if __name__ == "__main__":
    main()
