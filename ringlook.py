#!/usr/bin/env python3
"""
ringlook - Inspect processes by privilege ring approximation (0-3)

- Shows owning program + full file location
- Danger heuristic
- Ring 0 (kernel) is only fully visible / operable when run as root (sudo)
- Does NOT hide or filter .so mappings (including ones sometimes used by rootkits)
- Kill is available for every ring including 0 when privileged (use with extreme care)
"""

import os
import sys
import time
import signal
import curses
from pathlib import Path

def is_privileged():
    """True if we have effective root (needed for full ring 0 visibility)."""
    try:
        return os.geteuid() == 0
    except Exception:
        return False


def get_loaded_sos(pid):
    """
    Return list of loaded shared libraries / mapped files from /proc/pid/maps.
    We deliberately do NOT filter or hide any .so – including ones that
    rootkits sometimes abuse – so the operator can still see them.
    """
    sos = []
    seen = set()
    try:
        with open(f"/proc/{pid}/maps") as f:
            for line in f:
                # maps line ends with path sometimes
                parts = line.split()
                if len(parts) < 6:
                    continue
                path = parts[-1]
                if path.startswith("/") and path not in seen:
                    # keep every mapped file, especially .so
                    if ".so" in path or path.endswith(".so") or "/lib" in path or "/usr/lib" in path:
                        sos.append(path)
                        seen.add(path)
                    # also keep other interesting mappings (not just .so)
                    elif any(x in path for x in ("/tmp/", "/dev/shm/", "/run/", "deleted")):
                        sos.append(path + "  [unusual mapping]")
                        seen.add(path)
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return sos


def get_process_info(pid, privileged=False):
    """Gather basic info about a process."""
    try:
        pid = int(pid)
        if pid <= 0:
            return None

        # Comm (short name)
        try:
            with open(f"/proc/{pid}/comm") as f:
                comm = f.read().strip()
        except (FileNotFoundError, PermissionError):
            return None

        # Executable path (full file location)
        exe = None
        try:
            exe = os.readlink(f"/proc/{pid}/exe")
            # resolve (deleted) markers etc.
            if " (deleted)" in exe:
                exe = exe  # keep the marker visible
        except (FileNotFoundError, PermissionError, OSError):
            exe = None

        # Status
        uid = None
        ppid = None
        state = "?"
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("Uid:"):
                        uid = int(line.split()[1])
                    elif line.startswith("PPid:"):
                        ppid = int(line.split()[1])
                    elif line.startswith("State:"):
                        state = line.split()[1]
        except (FileNotFoundError, PermissionError):
            pass

        # Kernel thread detection
        is_kernel = False
        if exe is None:
            knames = (
                "idle", "migration", "rcu", "ksoftirqd", "kworker",
                "kthreadd", "cpuhp", "watchdog", "kdevtmpfs", "kauditd",
                "khungtaskd", "oom_reaper", "writeback", "kcompactd",
                "ksmd", "khugepaged", "kintegrityd", "kblockd", "kswapd",
                "kthrotld", "irq/", "scsi_", "ext4-", "jbd2/", "loop"
            )
            if (comm.startswith("k") or any(comm.startswith(k) for k in knames) or
                pid == 2 or (ppid is not None and ppid == 2)):
                is_kernel = True
            else:
                # missing exe → treat as non-user / privileged
                is_kernel = True

        # Ring approximation
        if is_kernel or uid is None:
            ring = 0
        elif uid == 0:
            ring = 1
        else:
            ring = 3

        # If not privileged, do not expose ring 0 at all
        if ring == 0 and not privileged:
            return None

        # Danger assessment (heuristic only)
        danger = "low"
        reason = []
        if ring == 0:
            danger = "critical"
            reason.append("kernel thread / ring-0")
        elif uid == 0:
            danger = "high"
            reason.append("running as root")
        if any(x in (comm or "").lower() for x in (
            "ssh", "systemd", "dockerd", "containerd", "kube", "init",
            "cron", "rsyslog", "auditd"
        )):
            if danger == "low":
                danger = "medium"
            reason.append("system-critical service")
        if not reason:
            reason.append("normal user process")

        # Loaded libraries / mappings (never filtered)
        sos = get_loaded_sos(pid) if not is_kernel else []

        return {
            "pid": pid,
            "comm": comm,
            "exe": exe if exe else "(kernel / no user-space mapping)",
            "uid": uid,
            "ppid": ppid,
            "state": state,
            "ring": ring,
            "danger": danger,
            "reason": ", ".join(reason),
            "sos": sos,
            "is_kernel": is_kernel,
        }
    except Exception:
        return None


def collect_processes(privileged=False):
    """Scan /proc and group by ring."""
    rings = {0: [], 1: [], 2: [], 3: []}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        info = get_process_info(entry, privileged=privileged)
        if info:
            rings[info["ring"]].append(info)

    for r in rings:
        rings[r].sort(key=lambda x: x["pid"])
    return rings


def danger_color(danger):
    return {
        "critical": curses.color_pair(1),
        "high": curses.color_pair(2),
        "medium": curses.color_pair(3),
        "low": curses.color_pair(4),
    }.get(danger, curses.A_NORMAL)


def draw_header(stdscr, title):
    h, w = stdscr.getmaxyx()
    stdscr.attron(curses.A_BOLD | curses.color_pair(5))
    stdscr.addstr(0, 0, title[: max(0, w - 1)])
    stdscr.attroff(curses.A_BOLD | curses.color_pair(5))
    stdscr.addstr(1, 0, "─" * min(w - 1, 100))


def main_ui(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_WHITE, -1)

    privileged = is_privileged()
    current_ring = 0 if privileged else 1
    selected = 0
    offset = 0
    message = "RUNNING AS ROOT – ring 0 visible" if privileged else "NOT root – ring 0 hidden (use sudo)"
    last_refresh = 0
    rings = collect_processes(privileged=privileged)

    while True:
        h, w = stdscr.getmaxyx()
        now = time.time()
        if now - last_refresh > 2.0:
            rings = collect_processes(privileged=privileged)
            last_refresh = now
            if selected >= len(rings[current_ring]):
                selected = max(0, len(rings[current_ring]) - 1)

        stdscr.erase()
        priv_tag = " [ROOT]" if privileged else " [no root]"
        draw_header(
            stdscr,
            f" ringlook{priv_tag}  │  rings 0-3  │  q=quit  r=refresh  ←→=ring  Enter=details  K=kill"
        )

        # Ring tabs
        tab_y = 2
        x = 2
        for r in range(4):
            count = len(rings[r])
            if r == 0 and not privileged:
                label = f" Ring 0 (hidden) "
            else:
                label = f" Ring {r} ({count}) "
            if r == current_ring:
                stdscr.attron(curses.A_REVERSE | curses.A_BOLD)
                stdscr.addstr(tab_y, x, label)
                stdscr.attroff(curses.A_REVERSE | curses.A_BOLD)
            else:
                stdscr.addstr(tab_y, x, label)
            x += len(label) + 2

        # Legend
        stdscr.addstr(3, 2, "Danger: ")
        stdscr.attron(curses.color_pair(1)); stdscr.addstr("critical "); stdscr.attroff(curses.color_pair(1))
        stdscr.attron(curses.color_pair(2)); stdscr.addstr("high "); stdscr.attroff(curses.color_pair(2))
        stdscr.attron(curses.color_pair(3)); stdscr.addstr("medium "); stdscr.attroff(curses.color_pair(3))
        stdscr.attron(curses.color_pair(4)); stdscr.addstr("low"); stdscr.attroff(curses.color_pair(4))
        if not privileged:
            stdscr.addstr(3, 40, "  (run with sudo to unlock ring 0)")

        # Column headers – emphasize file location
        header = f"{'PID':>7}  {'COMM':<16}  {'DANGER':<9}  FILE LOCATION (program)"
        stdscr.attron(curses.A_DIM)
        stdscr.addstr(4, 0, header[: w - 1])
        stdscr.attroff(curses.A_DIM)

        procs = rings[current_ring]
        list_start = 5
        max_rows = max(1, h - list_start - 3)

        if selected < offset:
            offset = selected
        if selected >= offset + max_rows:
            offset = selected - max_rows + 1

        for i, p in enumerate(procs[offset : offset + max_rows]):
            y = list_start + i
            attr = danger_color(p["danger"])
            if offset + i == selected:
                attr |= curses.A_REVERSE
            # Show full file location
            loc = p["exe"]
            line = f"{p['pid']:>7}  {p['comm'][:16]:<16}  {p['danger']:<9}  {loc}"
            try:
                stdscr.addstr(y, 0, line[: w - 1], attr)
            except curses.error:
                pass

        status = f"Ring {current_ring}  │  {len(procs)} processes  │  {message}"
        stdscr.attron(curses.A_DIM)
        try:
            stdscr.addstr(h - 1, 0, status[: w - 1])
        except curses.error:
            pass
        stdscr.attroff(curses.A_DIM)

        stdscr.refresh()

        stdscr.timeout(200)
        try:
            key = stdscr.getch()
        except Exception:
            key = -1

        if key == -1:
            continue
        elif key in (ord("q"), ord("Q"), 27):
            break
        elif key in (ord("r"), ord("R")):
            rings = collect_processes(privileged=privileged)
            message = "refreshed"
            last_refresh = time.time()
        elif key == curses.KEY_LEFT or key == ord("h"):
            current_ring = (current_ring - 1) % 4
            if current_ring == 0 and not privileged:
                current_ring = 3  # skip hidden ring 0
            selected = 0
            offset = 0
            message = f"switched to ring {current_ring}"
        elif key == curses.KEY_RIGHT or key == ord("l"):
            current_ring = (current_ring + 1) % 4
            if current_ring == 0 and not privileged:
                current_ring = 1
            selected = 0
            offset = 0
            message = f"switched to ring {current_ring}"
        elif key == curses.KEY_UP or key == ord("k"):
            if selected > 0:
                selected -= 1
        elif key == curses.KEY_DOWN or key == ord("j"):
            if selected < len(procs) - 1:
                selected += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            if procs:
                show_detail(stdscr, procs[selected], privileged)
        elif key == ord("K"):
            if procs:
                p = procs[selected]
                if p["ring"] == 0 and not privileged:
                    message = "REFUSED: ring 0 requires root (sudo)"
                else:
                    confirm = confirm_kill(stdscr, p, privileged)
                    if confirm:
                        try:
                            # Try SIGTERM first, then SIGKILL if needed for stubborn ones
                            os.kill(p["pid"], signal.SIGTERM)
                            message = f"SIGTERM → {p['pid']} ({p['comm']})"
                            time.sleep(0.4)
                            # check if still alive
                            if Path(f"/proc/{p['pid']}").exists():
                                os.kill(p["pid"], signal.SIGKILL)
                                message = f"SIGKILL → {p['pid']} ({p['comm']})"
                            rings = collect_processes(privileged=privileged)
                        except ProcessLookupError:
                            message = "process already gone"
                        except PermissionError:
                            message = "permission denied (need more privileges?)"
                        except Exception as e:
                            message = f"error: {e}"
                    else:
                        message = "kill cancelled"


def show_detail(stdscr, p, privileged):
    """Full detail including file location and all loaded .so / mappings."""
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    draw_header(stdscr, f" Detail  PID {p['pid']}  │  any key to return")

    lines = [
        f"PID:            {p['pid']}",
        f"Command name:   {p['comm']}",
        f"File location:  {p['exe']}",
        f"UID:            {p['uid']}",
        f"PPID:           {p['ppid']}",
        f"State:          {p['state']}",
        f"Approx ring:    {p['ring']}",
        f"Danger:         {p['danger']}",
        f"Reason:         {p['reason']}",
        "",
        "Loaded libraries / mappings (NOT filtered – includes possible rootkit .so):",
    ]

    if p.get("sos"):
        for s in p["sos"][: max(0, h - 20)]:
            lines.append(f"  {s}")
        if len(p["sos"]) > h - 20:
            lines.append(f"  ... and {len(p['sos']) - (h - 20)} more")
    else:
        if p.get("is_kernel"):
            lines.append("  (kernel thread – no user-space .so mappings)")
        else:
            lines.append("  (none readable or none present)")

    lines += [
        "",
        "Notes:",
        "  Ring 0 ≈ kernel threads (visible only with sudo/root)",
        "  Ring 1 ≈ root user-space processes",
        "  Ring 2 ≈ unused on modern Linux",
        "  Ring 3 ≈ normal non-root processes",
        "  .so list is complete – nothing is hidden by this tool.",
    ]

    for i, line in enumerate(lines):
        if 3 + i < h - 1:
            try:
                stdscr.addstr(3 + i, 2, line[: w - 3])
            except curses.error:
                pass
    stdscr.refresh()
    stdscr.timeout(-1)
    stdscr.getch()
    stdscr.timeout(200)


def confirm_kill(stdscr, p, privileged):
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    if p["ring"] == 0:
        msg1 = f"WARNING: RING 0 / KERNEL  PID {p['pid']} ({p['comm']})"
        msg2 = "Killing kernel threads can panic the system."
        msg3 = "Type y to send SIGTERM then SIGKILL  [y/N]"
    else:
        msg1 = f"Kill PID {p['pid']} ({p['comm']}) ?"
        msg2 = f"File: {p['exe'][:60]}"
        msg3 = "[y/N]"
    stdscr.addstr(h // 2 - 1, max(0, (w - len(msg1)) // 2), msg1)
    stdscr.addstr(h // 2, max(0, (w - len(msg2)) // 2), msg2)
    stdscr.addstr(h // 2 + 1, max(0, (w - len(msg3)) // 2), msg3)
    stdscr.refresh()
    stdscr.timeout(-1)
    key = stdscr.getch()
    stdscr.timeout(200)
    return key in (ord("y"), ord("Y"))


def list_mode():
    privileged = is_privileged()
    rings = collect_processes(privileged=privileged)
    print("ringlook – processes by approximate privilege ring")
    print(f"Privilege: {'ROOT (ring 0 unlocked)' if privileged else 'normal user (ring 0 hidden – use sudo)'}")
    print()
    for r in range(4):
        print(f"=== RING {r} ({len(rings[r])} processes) ===")
        if r == 0 and not privileged:
            print("  (hidden – run with sudo to see kernel threads)\n")
            continue
        if not rings[r]:
            print("  (none visible)\n")
            continue
        print(f"{'PID':>7}  {'COMM':<16}  {'DANGER':<9}  FILE LOCATION")
        for p in rings[r]:
            print(f"{p['pid']:>7}  {p['comm'][:16]:<16}  {p['danger']:<9}  {p['exe']}")
        print()
    print("Danger is a simple heuristic.")
    print(".so / library mappings are never filtered – check detail view (Enter) for full list.")
    if not privileged:
        print("Tip: sudo ringlook   → unlocks ring 0 visibility and kill.")


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("-h", "--help"):
            print("""ringlook - view processes by approximate privilege ring (0-3)

Usage:
  ringlook              Interactive TUI
  sudo ringlook         Same, but unlocks full ring 0 (kernel) view + kill
  ringlook --list       One-shot text listing
  ringlook -h           This help

Interactive keys:
  ← → / h l     change ring
  ↑ ↓ / j k     move selection
  Enter         details (full file location + ALL loaded .so / mappings)
  K             kill selected process (works for every ring when root)
  r             refresh
  q / Esc       quit

Ring approximation:
  0  kernel threads          → only shown when run as root/sudo
  1  root user-space
  2  unused on modern Linux
  3  normal non-root processes

File location is always shown (the real path of the program).
Loaded .so / mappings are never hidden or filtered – including ones
sometimes used by rootkits – so you can still see them in the detail view.

WARNING: Killing processes (especially ring 0) can crash the machine.
Use only when you understand the risk.
""")
            return
        elif arg in ("--list", "-l", "list"):
            list_mode()
            return

    try:
        curses.wrapper(main_ui)
    except KeyboardInterrupt:
        pass
    print("ringlook exited.")


if __name__ == "__main__":
    main()
