# ringlook

Cross-distro Linux tool that shows what is running in each approximate CPU privilege ring (0–3), the **full file location** of the program, a danger flag, and all loaded `.so` / memory mappings (nothing is filtered or hidden).

Works on virtually any modern Linux distribution that has Python 3 (Debian, Ubuntu, Fedora, RHEL, CentOS, Rocky, Alma, Arch, openSUSE, Alpine, Gentoo, etc.).

## Features

- **Ring 0 is only visible when run as root** (`sudo ringlook`)
- Kill works for **every ring including 0** when you have root (use extreme caution)
- File location (real path of the binary) is always shown
- Loaded libraries / `.so` are **never hidden or filtered** – including ones sometimes used by rootkits
- Pure Python 3 + standard library (`curses`) – no pip packages required
- Works with both Python 3.6+ (most current distros ship 3.8–3.12)


## One-command install

From the directory that contains the files:

```bash
./install.sh          # user install (~/.local) – no root needed
sudo ./install.sh     # system-wide (/usr/local) – available for everyone
```

After that you can simply type:

```bash
ringlook
ringlook --list
sudo ringlook          # unlocks ring 0
```

## Requirements

- Linux (uses `/proc`)
- Python 3
- `curses` module (normally included with Python on all major distros)

If `curses` is missing (rare):

| Distro family                  | Install command                    |
|--------------------------------|------------------------------------|
| Debian / Ubuntu / Mint         | `sudo apt install python3`         |
| Fedora / RHEL / Rocky / Alma   | `sudo dnf install python3`         |
| Arch / Manjaro                 | `sudo pacman -S python`            |
| openSUSE                       | `sudo zypper install python3`      |
| Alpine                         | `sudo apk add python3`             |

(The `curses` binding ships with the standard `python3` package on these systems.)

## Quick start (no install)

```bash
# From the directory that contains ringlook.py
python3 ringlook.py              # interactive TUI
python3 ringlook.py --list       # plain text listing
python3 ringlook.py --help

# Full access (ring 0 unlocked)
sudo python3 ringlook.py
sudo python3 ringlook.py --list
```

You can also use the small launcher script:

```bash
chmod +x ringlook
./ringlook
sudo ./ringlook
```

## Install system-wide (recommended for daily use)

Copy the files to a location that is on every user’s `PATH`. The commands below work on all common distros:

```bash
# 1. Create a directory for the tool
sudo mkdir -p /usr/local/lib/ringlook

# 2. Copy the files
sudo cp ringlook.py ringlook /usr/local/lib/ringlook/
sudo chmod 755 /usr/local/lib/ringlook/ringlook /usr/local/lib/ringlook/ringlook.py

# 3. Create a system-wide command
sudo ln -sf /usr/local/lib/ringlook/ringlook /usr/local/bin/ringlook
```

After that you can run from anywhere:

```bash
ringlook
ringlook --list
sudo ringlook          # unlocks ring 0
```

### Alternative locations (also distro-agnostic)

- User-only (no root needed for install):

  ```bash
  mkdir -p ~/.local/bin ~/.local/lib/ringlook
  cp ringlook.py ringlook ~/.local/lib/ringlook/
  chmod +x ~/.local/lib/ringlook/ringlook ~/.local/lib/ringlook/ringlook.py
  ln -sf ~/.local/lib/ringlook/ringlook ~/.local/bin/ringlook
  # make sure ~/.local/bin is in your PATH (most distros already do this)
  ```

- Or simply add the project directory to your `PATH` in `~/.bashrc` / `~/.zshrc`:

  ```bash
  export PATH="/path/to/ringlook:$PATH"
  ```

## Usage

```
ringlook              Interactive TUI
sudo ringlook         Same + full ring 0 (kernel) view and kill
ringlook --list       One-shot text listing of all rings
ringlook -h / --help  Help
```

### Interactive keys

| Key               | Action                                                              |
|-------------------|---------------------------------------------------------------------|
| `←` `→` / `h` `l` | Change ring (0–3)                                                   |
| `↑` `↓` / `j` `k` | Move selection                                                      |
| `Enter`           | Detail view – full file location + **all** loaded `.so` / mappings  |
| `K`               | Kill selected process (SIGTERM then SIGKILL). Works for ring 0 when root |
| `r`               | Refresh list                                                        |
| `q` / `Esc`       | Quit                                                                |

## Ring approximation (Linux)

| Ring | Meaning                                      | Visibility              |
|------|----------------------------------------------|-------------------------|
| 0    | Kernel threads                               | only with `sudo`/root   |
| 1    | Root / elevated user-space processes         | always                  |
| 2    | Unused on almost all modern Linux systems    | always                  |
| 3    | Normal non-root user processes               | always                  |

## Notes on rootkits / hidden libraries

- The tool reads `/proc/<pid>/maps` and lists **every** mapped file it can see.
- No `.so` is filtered or suppressed, even ones that malware or rootkits sometimes use to hide activity.
- You still only see what the kernel exposes; a sophisticated rootkit that hooks the kernel can hide things from `/proc` itself.

## Warning

Killing processes (especially anything in ring 0) can crash services or panic the whole machine.  
Use only when you understand the risk. The tool is for visibility and controlled management, not a security scanner.

## Compatibility summary

| Component              | Requirement                | Status on major distros      |
|------------------------|----------------------------|------------------------------|
| OS                     | Linux with `/proc`         | All                          |
| Python                 | 3.6+                       | All current releases         |
| curses                 | Standard library           | Bundled with python3 package |
| Privileges for ring 0  | root / sudo                | Standard                     |
| External packages      | None                       | Fully self-contained         |

Tested conceptually against the package layouts of Debian/Ubuntu, Fedora, Arch, openSUSE and Alpine. No distro-specific code or paths are required.
