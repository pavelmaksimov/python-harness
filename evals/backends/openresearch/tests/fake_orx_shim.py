#!/usr/bin/env python3
"""Fake ``orx`` executable for the backend test suite.

Installed on PATH by ``fake_orx.install``; state lives in
``$FAKE_ORX_STATE/state.json``. Every invocation appends its effective argv
(without ``--no-telemetry``) to ``argv.jsonl`` so tests can audit exactly which
commands the backend issued. Output formats mirror the real orx 0.2.4 surfaces
the adapter consumes (``projects --json``, ``project view`` tree, ``exp status``
fields, the ``runs`` table and ``logs``).
"""
import json
import os
import pathlib
import re
import sys

STATE_DIR = pathlib.Path(os.environ["FAKE_ORX_STATE"])
STATE = json.loads((STATE_DIR / "state.json").read_text(encoding="utf-8"))
ARGV = [argument for argument in sys.argv[1:] if argument != "--no-telemetry"]


def save():
    (STATE_DIR / "state.json").write_text(
        json.dumps(STATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record():
    with (STATE_DIR / "argv.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(ARGV, ensure_ascii=False) + "\n")


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(3)


def flags(supported):
    parsed = {}
    index = 0
    while index < len(ARGV):
        token = ARGV[index]
        if token in supported:
            if supported[token]:
                parsed[token] = ARGV[index + 1]
                index += 2
                continue
            parsed[token] = True
        index += 1
    return parsed


def slugify(title):
    return "orx/" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def project_or_fail(project_id):
    for project in STATE["projects"]:
        if project["id"] == project_id:
            return project
    fail(f"unknown project {project_id}")


def node_or_fail(node_id):
    node = STATE["experiments"].get(node_id)
    if node is None:
        fail(f"unknown experiment {node_id}")
    return node


def do_version():
    print(f"orx {STATE['version']}")


def do_telemetry():
    if len(ARGV) < 2:
        fail("telemetry needs a subcommand")
    if ARGV[1] == "off":
        STATE["telemetry"] = "off"
        save()
    if STATE["telemetry"] == "off":
        print("Anonymous usage analytics: off (disabled via `orx telemetry off`)")
    else:
        print("Anonymous usage analytics: on")


def do_projects():
    if "--json" in ARGV:
        print(json.dumps([
            {"baselineBranch": project.get("baselineBranch", "main"),
             "id": project["id"], "name": project["name"], "paperId": None,
             "path": project["path"]}
            for project in STATE["projects"]
        ], ensure_ascii=False))
    else:
        for project in STATE["projects"]:
            print(f"{project['id']}  {project['name']}  {project['path']}")


def do_view():
    project = project_or_fail(ARGV[2])
    print(f"{project['name']} (local)")
    print(f"  id:      {project['id']}")
    print(f"  repo:    {project['path']}")
    print(f"  branch:  {project.get('baselineBranch', 'main')} (baseline)")
    print("Experiments")
    for node_id, node in STATE["experiments"].items():
        root = " [root]" if node.get("root") else ""
        print(f"  {node_id}  {node['title']}{root}  ({node['branch']})")


def do_create():
    project_id = ARGV[1] if len(ARGV) > 1 and not ARGV[1].startswith("--") else None
    if project_id is None:
        fail("project id is required")
    project = project_or_fail(project_id)
    options = flags({"--title": True, "--parent": True, "--baseline": False,
                     "--run-command": True, "--description": True})
    if "--title" not in options:
        fail("--title is required")
    STATE["counter"] += 1
    node_id = f"{project['prefix']}{STATE['counter']}"
    STATE["experiments"][node_id] = {
        "title": options["--title"],
        "branch": slugify(options["--title"]),
        "root": bool(options.get("--baseline")),
        "parent": options.get("--parent"),
        "run_command": options.get("--run-command", project.get("run_command", "")),
        "desc": "",
    }
    save()
    print(f"created experiment {node_id}")
    print(f"branch {STATE['experiments'][node_id]['branch']}")


def do_desc():
    node = node_or_fail(ARGV[2])
    if "--set" in ARGV:
        node["desc"] = ARGV[ARGV.index("--set") + 1]
        save()
    elif "--stdin" in ARGV:
        node["desc"] = sys.stdin.read()
        save()
    else:
        print(node.get("desc", ""))


def do_status():
    node = node_or_fail(ARGV[2])
    print(f"{node['title']}  ({node.get('node_state', 'idle')})  [local]")
    print(f"  id:       {ARGV[2]}")
    print(f"  branch:   {node['branch']}")
    print(f"  parent:   {node.get('parent') or '— (root experiment)'}")
    print(f"  command:  {node.get('run_command', '')}")
    last = node.get("last_run")
    if last:
        print(f"  last run: {last['id']} ({last['status']}, commit "
              f"{last.get('commit', 'a' * 8)}, ran 1s, updated now)")
    else:
        print("  last run: —")


def do_run():
    node = node_or_fail(ARGV[2])
    options = flags({"--backend": True, "--timeout": True})
    if options.get("--backend") != "local":
        fail("the fake orx only implements --backend local")
    index = sum(1 for run in STATE.get("runs", [])
                if run["experiment"] == ARGV[2]) + 1
    run_id = f"{ARGV[2]}_run_{index}"
    artifact_dir = pathlib.Path(STATE["artifact_root"]) / f"{ARGV[2]}-run-{index}"
    log_lines = ["subject output line"]
    if STATE.get("run_fails"):
        status = "failed"
        log_lines.append("simulated integration failure")
    else:
        status = "done"
        selection = re.search(r"--selection (\S+)", node.get("run_command", ""))
        fingerprint = selection.group(1) if selection else ""
        artifact_dir.mkdir(parents=True, exist_ok=True)
        for name, content in STATE["artifact_files"].items():
            (artifact_dir / name).write_text(
                content.replace("__FINGERPRINT__", fingerprint), encoding="utf-8")
        if not STATE.get("omit_marker"):
            log_lines.append(f"HARNESS_EVAL_ARTIFACT={artifact_dir}")
        log_lines.append("run completed successfully")
    STATE.setdefault("logs", {})[run_id] = "\n".join(log_lines) + "\n"
    node["node_state"] = "idle"
    node["last_run"] = {"id": run_id, "status": status}
    STATE.setdefault("runs", []).append(
        {"id": run_id, "status": status, "experiment": ARGV[2]})
    save()


def do_wait():
    node_or_fail(ARGV[2])
    print("done")


def do_runs():
    project_or_fail(ARGV[1])
    experiment = ARGV[ARGV.index("--experiment") + 1] if "--experiment" in ARGV else None
    print("ID                    STATUS  EXPERIMENT                             "
          "COMMIT   DURATION  UPDATED")
    print("────────────────────  ──────  ─────────────────────────────────────  "
          "───────  ────────  ───────")
    for run in reversed(STATE.get("runs", [])):
        if experiment and run["experiment"] != experiment:
            continue
        print(f"{run['id']}  {run['status'].upper()}  {run['experiment']}  "
              f"{'a' * 8}  1s  now")


def do_logs():
    log = STATE.get("logs", {}).get(ARGV[1])
    if log is None:
        fail(f"unknown run {ARGV[1]}")
    print(log)


record()
if not ARGV:
    fail("no command given")
if ARGV[0] in ("--version", "-V"):
    do_version()
elif ARGV[0] == "telemetry":
    do_telemetry()
elif ARGV[0] == "projects":
    do_projects()
elif ARGV[0] == "project" and len(ARGV) > 1 and ARGV[1] == "view":
    do_view()
elif ARGV[0] == "create-experiment":
    do_create()
elif ARGV[0] == "exp" and len(ARGV) > 1:
    dispatch = {"desc": do_desc, "status": do_status, "run": do_run,
                "wait": do_wait,
                "cancel": lambda: fail("cancel refused by the fake orx")}
    if ARGV[1] not in dispatch:
        fail(f"unknown exp command {ARGV[1]}")
    dispatch[ARGV[1]]()
elif ARGV[0] == "runs":
    do_runs()
elif ARGV[0] == "logs":
    do_logs()
else:
    fail(f"unknown command {ARGV[0]}")
