import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rai_scan.classifier.size import human_size
from rai_scan.color import (
    BOLD,
    accent,
    badge,
    banner,
    box,
    danger,
    info,
    key_value,
    muted,
    subheading,
    success,
    warning,
)
from rai_scan.removal.engine import preview, purge_trash, remove_agents
from rai_scan.removal.rollback import rollback_last
from rai_scan.report import as_html, as_json, as_list, as_markdown, components
from rai_scan.scanner import scan_system


def _menu_header(manifest: Dict[str, Any]) -> None:
    agents = manifest.get("agents", [])
    ai = manifest.get("ai_related", [])
    total = human_size(manifest.get("total_reclaimable_bytes", 0))
    ai_size = human_size(manifest.get("possible_ai_related_bytes", 0))

    print()
    print(banner("  \u2691 rai-scan  "))
    print(muted("\u2500" * 60))
    print(
        "   {}  {}  |  {}  {}".format(
            success("\u25cf {} agents".format(len(agents))),
            muted("{} reclaimable".format(total)),
            muted("{} AI-related".format(len(ai))),
            muted("\u2014 {}".format(ai_size)),
        )
    )
    print()


def _print_menu(items: List[Tuple[str, str]]) -> None:
    """Print menu items in two columns."""
    width = 80
    try:
        import shutil

        width = shutil.get_terminal_size(fallback=(80, 20)).columns
    except Exception:
        pass
    half = (width - 4) // 2
    pairs = []
    i = 0
    while i < len(items):
        if i + 1 < len(items):
            pairs.append((items[i], items[i + 1]))
            i += 2
        else:
            pairs.append((items[i], None))
            i += 1
    for left, right in pairs:
        n1, t1 = left
        line = "   {}  {}".format(accent(n1.rjust(2)), t1)
        if right:
            n2, t2 = right
            line += " " * max(2, half - len(line))
            line += " {}  {}".format(accent(n2.rjust(2)), t2)
        print(line)


def recommendations(manifest: Dict[str, Any]) -> List[Tuple[str, str, bool]]:
    """Return agent id, explanation, and whether it is a likely leftover."""
    result = []
    for agent in manifest.get("agents", []):
        has_install = bool(agent.get("packages")) or any(
            item["type"] == "binary" for item in agent.get("artifacts", [])
        )
        reasons = []
        likely_leftover = not has_install
        if likely_leftover:
            reasons.append("no executable or installed package was found; may be leftover data")
        if agent.get("total_bytes", 0) >= 1024**3:
            reasons.append("large storage use: {}".format(human_size(agent["total_bytes"])))
        elif agent.get("total_bytes", 0) >= 500 * 1024**2:
            reasons.append("significant storage use: {}".format(human_size(agent["total_bytes"])))
        if any(_is_system_path(item["path"]) for item in agent.get("artifacts", [])):
            reasons.append("contains system-installed files; extra caution required")
        if not reasons:
            reasons.append("installed agent with modest storage use")
        result.append((agent["id"], "; ".join(reasons), likely_leftover))
    return result


def _is_system_path(value: str) -> bool:
    try:
        Path(value).resolve(strict=False).relative_to(Path.home().resolve())
        return False
    except ValueError:
        return True


def _agent_row(agent: Dict[str, Any], number: int, width: int = 80) -> str:
    size = human_size(agent["total_bytes"])
    comps = components(agent)
    line = "  {}. {}  {}  {}".format(
        accent(str(number)),
        subheading(agent["display_name"]),
        muted(comps),
        success(size.rjust(10)),
    )
    return line


def _agent_details(agent: Dict[str, Any], number: int) -> str:
    lines = [
        "  {}. {} ({})".format(accent(str(number)), subheading(agent["display_name"]), muted(agent["id"])),
        "     {}  {}  {}".format(
            key_value("Size", human_size(agent["total_bytes"])),
            key_value("Confidence", agent["confidence"]),
            key_value("Components", components(agent)),
        ),
    ]
    lines.extend(
        "     {}".format(muted(item["path"])) for item in agent.get("artifacts", [])
    )
    for package in agent.get("packages", []):
        exe_note = " [{}]".format(package["executable"]) if package.get("executable") else ""
        lines.append(
            "     {} {} package: {} {}{}".format(
                muted("\u2514"),
                package["manager"],
                package["name"],
                package.get("version", ""),
                exe_note,
            ).rstrip()
        )
    for daemon in agent.get("daemons", []):
        scope = " (system)" if daemon.get("scope") == "system" else ""
        lines.append(
            "     {} daemon: {}{} [{}]".format(
                muted("\u2514"), daemon["name"], scope, daemon["type"]
            )
        )
    return "\n".join(lines)


def _choose_agents(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    agents = manifest.get("agents", [])
    if not agents:
        print()
        print(warning("  No confirmed AI agents were found."))
        return []
    print()
    print(box("  Select agents to remove  "))
    print()
    for number, agent in enumerate(agents, 1):
        print(_agent_row(agent, number))

    suggested = {
        agent_id
        for agent_id, _reason, likely_leftover in recommendations(manifest)
        if likely_leftover
    }
    print()
    if suggested:
        print("  {} {}".format(info("Auto-select:"), muted("type 'a' for likely leftovers (no binary/package)")))
    print("  {} {}".format(muted("Cancel:"), muted("type 'q'")))
    print()
    prompt = info("  \u25b6 Enter numbers").format() + " (e.g. 1 3 5" + (", a" if suggested else "") + "): "
    answer = input(prompt).strip().lower()
    if not answer or answer == "q":
        return []
    if answer.startswith("a") and suggested:
        selected = [agent for agent in agents if agent["id"] in suggested]
        print(success("  \u2713 Auto-selected {} agent(s)".format(len(selected))))
        return selected

    selected = []
    for value in answer.replace(",", " ").split():
        try:
            index = int(value) - 1
        except ValueError:
            print(danger("  Invalid selection: {}".format(value)))
            return []
        if index < 0 or index >= len(agents):
            print(danger("  Selection out of range: {}".format(value)))
            return []
        if agents[index] not in selected:
            selected.append(agents[index])
    return selected


def _confirm_dangerous(action: str, keyword: str, extra: str = "") -> bool:
    """Dangerous confirmation with emphasis."""
    print()
    print(danger("  \u26a0 {}".format(action)))
    if extra:
        print(warning("  {}".format(extra)))
    print()
    answer = input("  Type {} to confirm: ".format(badge(keyword, BOLD))).strip()
    return answer == keyword


def _removal_wizard(manifest: Dict[str, Any], permanent: bool = False) -> None:
    print(info("  \u21bb Refreshing scan before removal..."))
    manifest = scan_system(include_root=bool(manifest.get("include_root")))
    selected = _choose_agents(manifest)
    if not selected:
        return
    print()
    print(box("  Removal preview \u2014 no changes made  "))
    print()
    print(preview(selected))
    print()
    total = human_size(sum(agent["total_bytes"] for agent in selected))
    print("  Total selected: {}".format(success(total)))
    print()

    system_paths = [
        item["path"]
        for agent in selected
        for item in agent.get("artifacts", [])
        if _is_system_path(item["path"])
    ]
    system_packages = [
        "{} package {}".format(item["manager"], item["name"])
        for agent in selected
        for item in agent.get("packages", [])
        if item.get("scope") == "system"
    ]
    system_daemons = [
        item["name"]
        for agent in selected
        for item in agent.get("daemons", [])
        if item.get("scope") == "system"
    ]
    include_root = False
    if system_paths or system_packages or system_daemons:
        print(danger("  System-level items included:"))
        for path in system_paths:
            print("    {}".format(path))
        for pkg in system_packages:
            print("    {}".format(pkg))
        for name in system_daemons:
            print("    systemd system unit: {}".format(name))
        include_root = input("\n  Allow system paths? Type ROOT: ").strip() == "ROOT"
        if not include_root:
            print(warning("  Cancelled."))
            return
        print()

    if permanent:
        if not _confirm_dangerous(
            "PERMANENTLY DELETE selected files",
            "PERMANENT",
            "This CANNOT be undone. Files will not go to trash.",
        ):
            print(warning("  Cancelled. No changes made."))
            return
    else:
        if not _confirm_dangerous(
            "Move selected files to recoverable trash?",
            "YES",
        ):
            print(warning("  Cancelled. No changes made."))
            return

    record, errors = remove_agents(selected, include_root, permanent)
    print()
    print(success("  \u2713 Removal session recorded: {}".format(record["session_id"])))
    if errors:
        print(danger("  \u2717 Some operations failed:"))
        for error in errors:
            print("    - {}".format(error))


def _show_recommendations(manifest: Dict[str, Any]) -> None:
    print()
    print(box("  Recommendations  "))
    print()
    for agent_id, reason, likely_leftover in recommendations(manifest):
        tag = danger(" LEFTOVER ") if likely_leftover else info(" REVIEW ")
        print("  [{}] {}: {}".format(tag, subheading(agent_id), muted(reason)))
    if manifest.get("ai_related"):
        print()
        print(warning("  Possible AI-related data (informational, never auto-selected):"))
        for item in manifest["ai_related"]:
            print(
                "    {} \u2014 {} ({})".format(
                    item["path"], human_size(item["size_bytes"]), item["agent_hint"]
                )
            )


def _export(manifest: Dict[str, Any]) -> None:
    print()
    print(box("  Export report  "))
    print()
    print("  1. JSON")
    print("  2. Markdown")
    print("  3. HTML")
    print("  0. Cancel")
    print()
    choice = input("  Choose format: ").strip()
    formats = {
        "1": ("json", as_json),
        "2": ("md", as_markdown),
        "3": ("html", as_html),
    }
    selected = formats.get(choice)
    if not selected:
        return
    extension, renderer = selected
    filename = "rai-scan-{}.{}".format(datetime.now().strftime("%Y%m%d-%H%M%S"), extension)
    path = Path.cwd() / filename
    path.write_text(renderer(manifest) + "\n", encoding="utf-8")
    print(success("  \u2713 Report saved to {}".format(path)))


def _purge_trash() -> None:
    print()
    print(danger("  \u26a0 Purge trash"))
    print(muted("  This permanently deletes all files in ~/.rai-scan/trash/"))
    if not _confirm_dangerous("", "PURGE", "THIS CANNOT BE UNDONE."):
        print(warning("  Cancelled."))
        return
    deleted, errors = purge_trash()
    if errors:
        print(danger("  Purged {} entries with {} errors.".format(deleted, errors)))
    else:
        print(success("  \u2713 Purged {} entries from trash.".format(deleted)))


def _rollback() -> None:
    print()
    print(box("  Roll back last removal  "))
    if not _confirm_dangerous("Restore the last removal session?", "YES"):
        print(warning("  Cancelled."))
        return
    try:
        record = rollback_last()
    except Exception as exc:
        print(danger("  Rollback failed: {}".format(exc)))
        return
    print(success("  \u2713 Restored session {}.".format(record["session_id"])))
    if record.get("rollback_errors"):
        print(danger("  Rollback was partial:"))
        for error in record["rollback_errors"]:
            print("    - {}".format(error))


def _uninstall() -> bool:
    project_dir = Path(__file__).resolve().parents[2]
    script = project_dir / "uninstall.sh"
    if not script.is_file():
        print(danger("  Uninstall script not found: {}".format(script)))
        return False
    print()
    print(box("  Uninstall rai-scan  "))
    print()
    print("  This removes the rai-scan command and its private Python environment.")
    print("  The project source directory will be kept: {}".format(project_dir))
    print()
    purge = input("  Also permanently delete ~/.rai-scan state? [y/N]: ").strip().lower() == "y"
    print()
    print(muted("  Planned uninstall:"))
    command = [str(script), "--dry-run"]
    if purge:
        command.append("--purge-state")
    subprocess.run(command, check=False)
    print()
    if not _confirm_dangerous(
        "Proceed with uninstall?" if not purge else "Proceed with uninstall and state purge?",
        "UNINSTALL",
    ):
        print(warning("  Cancelled. Nothing was removed."))
        return False
    command = [str(script)]
    if purge:
        command.append("--purge-state")
    result = subprocess.run(command, check=False)
    return result.returncode == 0


def run(manifest: Dict[str, Any]) -> int:
    menu_items = [
        ("1", "Fresh scan"),
        ("2", "Show simple results"),
        ("3", "Show detailed results"),
        ("4", "Recommendations"),
        ("5", "Safe removal wizard"),
        ("6", "Permanent removal wizard"),
        ("7", "Export report"),
        None,  # separator
        ("8", "Roll back last removal"),
        ("9", "Purge trash"),
        ("10", "Help & safety info"),
        ("11", "Uninstall"),
        None,
        ("0", "Exit"),
    ]
    # figure out box width
    num_w = max(len(n) for n, _ in [m for m in menu_items if m]) + 2
    box_inner = 50  # fixed inner width for a consistent look
    hr = muted("\u2500" * box_inner)

    def menu_line(num: str, label: str) -> str:
        left = " " * (num_w - len(num))
        pad = box_inner - num_w - len(label) - 4
        return "  \u2502 {} {} {} {}\u2502".format(
            muted(left), accent(num), label, " " * pad
        )

    while True:
        _menu_header(manifest)
        print("  \u250c" + hr + "\u2510")
        for item in menu_items:
            if item is None:
                print("  \u251c" + hr + "\u2524")
            else:
                print(menu_line(item[0], item[1]))
        print("  \u2514" + hr + "\u2518")
        print()
        choice = input("  \u25b6 Option: ").strip().lstrip("0")
        print()

        if choice == "1":
            print(info("  Scanning..."))
            manifest = scan_system()
            print(success("  \u2713 Fresh scan complete."))

        elif choice == "2":
            print(as_list(manifest))

        elif choice == "3":
            print(as_list(manifest, verbose=True))

        elif choice == "4":
            _show_recommendations(manifest)

        elif choice == "5":
            _removal_wizard(manifest, permanent=False)
            manifest = scan_system()

        elif choice == "6":
            _removal_wizard(manifest, permanent=True)
            manifest = scan_system()

        elif choice == "7":
            _export(manifest)

        elif choice == "8":
            _rollback()
            manifest = scan_system()

        elif choice == "9":
            _purge_trash()

        elif choice == "10":
            print()
            print(box("  rai-scan safety  "))
            print()
            print("  \u2713 Known signatures keep confirmed and low-confidence findings separate.")
            print("  \u2713 Every removal prints a full preview and requires YES.")
            print("  \u2713 System-scoped operations require a second SYSTEM confirmation.")
            print("  \u2713 Removal always performs a fresh scan before making changes.")
            print("  \u2713 Files move to ~/.rai-scan/trash/ \u2014 nothing is deleted immediately.")
            print("  \u2713 Changes use a signed write-ahead journal; rollback restores everything.")
            print("  \u2713 Paths are revalidated immediately before each operation.")
            print("  \u2713 State is owner-only (0700/0600). Symlinks are rejected.")
            print("  \u2717 Permanent removal deletes directly and CANNOT be undone.")
            print("  \u2717 Purge trash permanently deletes all files in ~/.rai-scan/trash/.")

        elif choice == "11":
            if _uninstall():
                print(success("  Uninstall complete. Exiting rai-scan."))
                return 0

        elif choice == "" or choice == "0":
            print(muted("  Goodbye."))
            return 0

        else:
            print(warning("  Invalid option. Choose 0\u201311."))
