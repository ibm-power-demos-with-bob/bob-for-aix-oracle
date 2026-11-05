---
name: oracle-aix-setup
description: >-
  Install or update the Oracle community `db` skill content under
  .agents/skills/oracle-aix/operations/
metadata:
  user-invocable: true
  disable-model-invocation: true
---

Install (or refresh) the Oracle community `db` skill from https://github.com/oracle/skills
into `.agents/skills/oracle-aix/operations/` of this workspace, so the `oracle-aix` skill can
use it for platform-neutral Oracle topics (SQL, PL/SQL, RMAN, Data Guard, performance,
security, ORDS, SQLcl).

Follow these steps exactly:

1. Detect the shell. Use the bash version on macOS, Linux, or Git Bash, and the PowerShell
   version on Windows PowerShell.
2. Tell the user that the command clones a public GitHub repository and **replaces** any
   existing `.agents/skills/oracle-aix/operations/` directory. That directory holds only
   cloned content and is git-ignored. Then run the script.
3. Report the top-level entries now present under `.agents/skills/oracle-aix/operations/`
   (for example `performance/`, `security/`, `backup/`), and confirm the `.gitignore` entry.

This command installs documentation content only and runs no Oracle binaries. When you later
use the installed `operations/` topic files (`sqlplus`, `rman`, `srvctl`, SQLcl, ORDS, ...),
first verify `ORACLE_HOME`, `ORACLE_SID`, `ORACLE_BASE`, `PATH`, `LIBPATH`, and `TNS_ADMIN`
(if used) with the "Oracle environment pre-flight check" in `.agents/skills/oracle-aix/SKILL.md`.
Mention this to the user in your final report.

All paths are resolved from the repository root before changing directory. Every command
uses absolute paths, so the copy can't land in the temporary clone.

### bash (macOS / Linux / Git Bash)

```bash
set -eu
REPO_ROOT=$(git rev-parse --show-toplevel)
DEST="$REPO_ROOT/.agents/skills/oracle-aix/operations"
ENTRY='.agents/skills/oracle-aix/operations/'
TMP_DIR=$(mktemp -d)

git clone --quiet --depth 1 --filter=blob:none --sparse \
  https://github.com/oracle/skills.git "$TMP_DIR/skills"
git -C "$TMP_DIR/skills" sparse-checkout set db
test -d "$TMP_DIR/skills/db" || { echo "db/ not found in oracle/skills" >&2; exit 1; }

rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$TMP_DIR/skills/db/." "$DEST/"
rm -rf "$TMP_DIR"

touch "$REPO_ROOT/.gitignore"
grep -qxF "$ENTRY" "$REPO_ROOT/.gitignore" || printf '%s\n' "$ENTRY" >> "$REPO_ROOT/.gitignore"
ls "$DEST"
```

### PowerShell (Windows)

```powershell
$ErrorActionPreference = 'Stop'
$repoRoot = (git rev-parse --show-toplevel).Trim()
$dest     = Join-Path $repoRoot '.agents/skills/oracle-aix/operations'
$entry    = '.agents/skills/oracle-aix/operations/'
$tmp      = Join-Path ([IO.Path]::GetTempPath()) ("oracle-skills-" + [guid]::NewGuid())

git clone --quiet --depth 1 --filter=blob:none --sparse https://github.com/oracle/skills.git $tmp
if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
git -C $tmp sparse-checkout set db
if (-not (Test-Path (Join-Path $tmp 'db'))) { throw "db/ not found in oracle/skills" }

if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force (Join-Path $tmp 'db/*') $dest
Remove-Item -Recurse -Force $tmp

$gitignore = Join-Path $repoRoot '.gitignore'
if (-not (Test-Path $gitignore)) { New-Item -ItemType File -Path $gitignore | Out-Null }
if (-not (Select-String -Path $gitignore -SimpleMatch -Pattern $entry -Quiet)) {
  Add-Content -Path $gitignore -Value $entry
}
Get-ChildItem $dest | Select-Object -ExpandProperty Name
```
