#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
python="${PYTHON:-python3}"

"$python" - <<'PY'
import pathlib, re, sys, tomllib
m = tomllib.loads(pathlib.Path("plugin.toml").read_text())
allowed = {"id", "version", "description", "skills", "prompts", "commands", "capabilities", "local_only", "mcp"}
assert set(m) <= allowed, f"unknown keys: {set(m) - allowed}"
assert m["id"] == "corunis", m["id"]
assert re.fullmatch(r"\d+\.\d+\.\d+", m["version"]), m["version"]
assert m["description"].strip()
assert m["capabilities"] == ["mcp-server"], m["capabilities"]
assert m.get("local_only") is True, "corunis must declare local_only = true"
mcp = m["mcp"]
assert set(mcp) <= {"command", "args", "env"}, mcp
command = pathlib.Path(mcp["command"])
assert not command.is_absolute() and ".." not in command.parts and command.is_file(), command
prefix = m["id"].upper().replace("-", "_") + "_"
for name, host in mcp.get("env", {}).items():
    assert host.startswith(prefix) or host.startswith("LOCAL_STUDIO_PLUGIN_" + prefix), (name, host)
skills = pathlib.Path(m.get("skills", "skills"))
names = {}
for d in sorted(p for p in skills.iterdir() if p.is_dir()):
    f = d / "SKILL.md"
    assert f.is_file(), f"missing {f}"
    text = f.read_text()
    name = re.search(r"^name:\s*(\S+)", text, re.M).group(1)
    description = re.search(r"^description:\s*(.*)$", text, re.M).group(1)
    assert len(description) <= 200 and ": " not in description, f"{f}: description too long or has ': '"
    names[name] = f
for tier in "SML":
    assert (skills / "corunis" / "tiers" / f"{tier}.md").is_file(), f"missing tier card {tier}"
cmds = {c["name"]: c for c in m["commands"]}
assert cmds["brain"]["skill"] == "corunis", cmds
for c in cmds.values():
    assert c.get("skill") in names, f"command {c['name']}: missing skill {c.get('skill')}"
print(f"ok   plugin.toml: id corunis, mcp {command}, skills {sorted(names)}, commands {sorted('/' + n for n in cmds)}")
PY

"$python" - <<'PY'
import pathlib, subprocess
files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True, check=True).stdout.split()
bad = []
for name in files:
    path = pathlib.Path(name)
    if not path.is_file() or path.suffix in {".png", ".jpg", ".pdf", ".docx", ".lock", ".sqlite"}:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for number, line in enumerate(text.splitlines(), 1):
        if "\u2013" in line or "\u2014" in line:
            bad.append(f"{name}:{number}")
assert not bad, "em or en dashes in: " + ", ".join(bad[:20])
print(f"ok   no em or en dashes in {len(files)} files")
PY

"$python" tests/plugin/mcp_smoke.py

studio="${LOCAL_STUDIO:-}"
if [ -z "$studio" ] && [ -x "$HOME/.cache/ls-linux-target-gantrel/release/local-studio" ]; then
  studio="$HOME/.cache/ls-linux-target-gantrel/release/local-studio"
fi
if [ -n "$studio" ] && "$studio" plugin capabilities >/dev/null 2>&1; then
  scratch="$(mktemp -d)"
  trap 'rm -rf "$scratch"' EXIT
  mkdir "$scratch/corunis"
  git ls-files -co --exclude-standard -z | (cd "$root" && xargs -0 tar cf -) | tar xf - -C "$scratch/corunis"
  "$studio" plugin validate "$scratch/corunis"
  echo "ok   local-studio plugin validate ($studio)"
else
  echo "skip local-studio plugin validate: no local-studio binary with the plugin command (set LOCAL_STUDIO)"
fi
