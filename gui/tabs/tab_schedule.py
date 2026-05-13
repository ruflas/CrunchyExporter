"""
Schedule tab — register / remove a daily auto-sync task.

On Windows : Windows Task Scheduler (schtasks)
On Linux/Mac: crontab

The scheduled command runs the bundled CLI entry point:
    python <project_root>/src/main.py -c <config.yaml> sync --target <target>

No external project required — src/ ships with this repository.
"""

import sys
import platform
import subprocess
from pathlib import Path
import customtkinter as ctk

from gui import i18n

_TASK_NAME = "CrunchyExporter"
_TARGETS   = ["all", "anilist", "mal", "xml"]


class ScheduleTab:
    def __init__(self, frame: ctk.CTkFrame, app) -> None:
        self.app = app
        self.frame = frame
        self._build(frame)
        self._refresh_status()

    # ------------------------------------------------------------------ build

    def _build(self, f: ctk.CTkFrame) -> None:
        f.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            f, text=i18n.t("schedule_title"),
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))

        ctk.CTkLabel(
            f, text=i18n.t("schedule_desc"),
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
            justify="left", anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 14))

        # Options frame
        opts = ctk.CTkFrame(f, corner_radius=8)
        opts.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))
        opts.columnconfigure(1, weight=1)

        # Time
        ctk.CTkLabel(opts, text=i18n.t("schedule_time_label") + ":",
                     anchor="e").grid(row=0, column=0, sticky="e",
                                      padx=(14, 8), pady=(12, 6))
        self._time_var = ctk.StringVar(value="08:00")
        ctk.CTkEntry(opts, textvariable=self._time_var,
                     width=80, height=32).grid(row=0, column=1, sticky="w",
                                               padx=(0, 14), pady=(12, 6))

        # Target selector — mirrors the CLI's --target option exactly
        ctk.CTkLabel(opts, text=i18n.t("schedule_target_label") + ":",
                     anchor="e").grid(row=1, column=0, sticky="e",
                                      padx=(14, 8), pady=(0, 12))
        self._target_var = ctk.StringVar(value="all")
        ctk.CTkOptionMenu(
            opts,
            variable=self._target_var,
            values=_TARGETS,
            width=120,
            command=lambda _: self._update_cmd_preview(),
        ).grid(row=1, column=1, sticky="w", padx=(0, 14), pady=(0, 12))

        # Buttons
        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 10))

        ctk.CTkButton(
            btn_row, text=i18n.t("schedule_create_btn"), width=200,
            command=self._on_create,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text=i18n.t("schedule_remove_btn"), width=200,
            fg_color=("gray60", "gray40"),
            hover_color=("gray50", "gray30"),
            command=self._on_remove,
        ).pack(side="left", padx=(12, 0))

        # Status
        status_row = ctk.CTkFrame(f, fg_color="transparent")
        status_row.grid(row=4, column=0, sticky="w", padx=16, pady=(0, 10))

        ctk.CTkLabel(status_row, text=i18n.t("schedule_status_label"),
                     font=ctk.CTkFont(weight="bold")).pack(side="left")
        self._status_dot = ctk.CTkLabel(
            status_row, text="  ●", text_color="#888888",
            font=ctk.CTkFont(size=12))
        self._status_dot.pack(side="left", padx=(6, 0))
        self._status_lbl = ctk.CTkLabel(
            status_row, text="—", font=ctk.CTkFont(size=12))
        self._status_lbl.pack(side="left", padx=(4, 0))

        # Command preview
        ctk.CTkLabel(f, text=i18n.t("schedule_cmd_label"),
                     anchor="w",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray60")).grid(
            row=5, column=0, sticky="w", padx=16, pady=(4, 2))

        self._cmd_lbl = ctk.CTkLabel(
            f, text="",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=("gray45", "gray55"),
            anchor="w", justify="left",
        )
        self._cmd_lbl.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 4))

        note_key = "schedule_note_win" if platform.system() == "Windows" \
                   else "schedule_note_unix"
        ctk.CTkLabel(
            f, text=i18n.t(note_key),
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60"),
            anchor="w",
        ).grid(row=7, column=0, sticky="w", padx=16, pady=(8, 0))

        # Keep preview in sync when time changes
        self._time_var.trace_add("write", lambda *_: self._update_cmd_preview())
        self._update_cmd_preview()

    # ------------------------------------------------------------------ helpers

    def _build_cmd(self) -> str:
        python = sys.executable
        target = self._target_var.get()

        if getattr(sys, "frozen", False):
            # Bundled exe: call ourselves in headless mode — no temp paths
            return f'"{python}" --headless-sync --target {target}'
        else:
            src_main = self.app.project_root / "src" / "main.py"
            cfg_path = self.app.config_path
            return f'"{python}" "{src_main}" -c "{cfg_path}" sync --target {target}'

    def _update_cmd_preview(self) -> None:
        self._cmd_lbl.configure(text=self._build_cmd())

    def _refresh_status(self) -> None:
        active, run_time = _query_task()
        if active:
            self._status_dot.configure(text_color="#4caf50")
            self._status_lbl.configure(
                text=i18n.t("schedule_active", time=run_time))
        else:
            self._status_dot.configure(text_color="#888888")
            self._status_lbl.configure(text=i18n.t("schedule_inactive"))

    # ------------------------------------------------------------------ actions

    def _on_create(self) -> None:
        from tkinter import messagebox

        etp_rt = self.app.cfg.get("crunchyroll", {}).get("etp_rt", "").strip()
        if not etp_rt:
            messagebox.showwarning("Warning", i18n.t("schedule_err_no_cookie"))
            return

        run_at = self._time_var.get().strip()
        try:
            h, m = run_at.split(":")
            assert 0 <= int(h) <= 23 and 0 <= int(m) <= 59
        except Exception:
            messagebox.showerror("Error", "Invalid time. Use HH:MM (e.g. 08:00).")
            return

        ok, msg = _schedule_create(self._build_cmd(), run_at)
        if ok:
            messagebox.showinfo("OK", i18n.t("schedule_created", time=run_at))
        else:
            messagebox.showerror("Error", i18n.t("schedule_err_create", error=msg))
        self._refresh_status()

    def _on_remove(self) -> None:
        from tkinter import messagebox
        ok, msg = _schedule_remove()
        if ok:
            messagebox.showinfo("OK", i18n.t("schedule_removed"))
        else:
            messagebox.showerror("Error", i18n.t("schedule_err_remove", error=msg))
        self._refresh_status()


# ------------------------------------------------------------------ platform helpers
# Ported directly from CrunchyExporter-cli/src/main.py
# (_schedule_windows / _schedule_cron) — same schtasks/crontab calls.

def _schedule_create(cmd: str, run_at: str) -> tuple[bool, str]:
    if platform.system() == "Windows":
        return _win_create(cmd, run_at)
    return _cron_create(cmd, run_at)


def _schedule_remove() -> tuple[bool, str]:
    if platform.system() == "Windows":
        return _win_remove()
    return _cron_remove()


def _query_task() -> tuple[bool, str]:
    if platform.system() == "Windows":
        return _win_query()
    return _cron_query()


# ---- Windows ----------------------------------------------------------------

def _win_create(cmd: str, run_at: str) -> tuple[bool, str]:
    r = subprocess.run(
        ["schtasks", "/Create", "/TN", _TASK_NAME,
         "/TR", cmd, "/SC", "DAILY", "/ST", run_at, "/F"],
        capture_output=True, text=True,
    )
    return r.returncode == 0, r.stderr.strip()


def _win_remove() -> tuple[bool, str]:
    r = subprocess.run(
        ["schtasks", "/Delete", "/TN", _TASK_NAME, "/F"],
        capture_output=True, text=True,
    )
    return r.returncode == 0, r.stderr.strip()


def _win_query() -> tuple[bool, str]:
    r = subprocess.run(
        ["schtasks", "/Query", "/TN", _TASK_NAME, "/FO", "LIST"],
        capture_output=True,
        text=True,
        encoding="oem",     # schtasks outputs in the Windows OEM code page
        errors="replace",
    )
    if r.returncode != 0:
        return False, ""

    # The label varies by Windows locale; check case-insensitively
    keywords = ("start time", "hora de inicio", "startzeit", "heure de début",
                "ora di inizio", "開始時刻")
    for line in r.stdout.splitlines():
        if any(kw in line.lower() for kw in keywords):
            # Line looks like  "Start Time:    8:00:00 AM"
            # Split only on the first colon (the label separator)
            after_label = line.split(":", 1)[-1].strip()
            # after_label is now  "8:00:00 AM"  or  "08:00:00"
            parts = after_label.split(":")
            if len(parts) >= 2:
                hour   = parts[0].strip().zfill(2)
                minute = parts[1].strip()[:2]
                return True, f"{hour}:{minute}"

    return True, "?"


# ---- Unix / cron ------------------------------------------------------------

def _cron_create(cmd: str, run_at: str) -> tuple[bool, str]:
    hour, minute = run_at.split(":")
    entry = f"{minute} {hour} * * * {cmd}  # CrunchyExporter"
    lines = _cron_lines()
    lines.append(entry)
    return _cron_write(lines)


def _cron_remove() -> tuple[bool, str]:
    return _cron_write(_cron_lines())


def _cron_query() -> tuple[bool, str]:
    for line in _cron_lines():
        if "CrunchyExporter" in line:
            parts = line.split()
            if len(parts) >= 2:
                return True, f"{parts[1].zfill(2)}:{parts[0].zfill(2)}"
    return False, ""


def _cron_lines() -> list[str]:
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = r.stdout if r.returncode == 0 else ""
    return [l for l in existing.splitlines() if "CrunchyExporter" not in l]


def _cron_write(lines: list[str]) -> tuple[bool, str]:
    r = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n",
                       text=True, capture_output=True)
    return r.returncode == 0, r.stderr.strip()
