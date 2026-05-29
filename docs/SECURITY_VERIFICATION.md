# Security Verification — DD blockers re-proven

Date: 2026-05-29. Each item below was executed, not asserted. Commands and real output included.

## 1. Text-to-SQL file exfiltration — BLOCKED

The DD proved that `run_select` (the exact path the chat endpoint calls for spreadsheet
questions) would execute arbitrary DuckDB file functions and leak the live API key. The fix
opens every DuckDB connection with `config={"enable_external_access": False, "lock_configuration": True}`
(`app/spreadsheet/store.py::_connect`).

Re-running the **same attacks through the real `run_select`** now:

```
DuckDB connection config in effect: {'enable_external_access': False, 'lock_configuration': True}

[read backend/.env]          ✓ BLOCKED  PermissionException: ... file system operations are disabled by configuration
[read /etc/passwd]           ✓ BLOCKED  PermissionException: ... file system operations are disabled by configuration
[filesystem glob]            ✓ BLOCKED  PermissionException: ... file system operations are disabled by configuration
[read_csv on .env]           ✓ BLOCKED  PermissionException: ... file system operations are disabled by configuration
[stacked SET re-enable]      ✓ BLOCKED  InvalidInputException: Cannot change configuration option
                                         "enable_external_access" - the configuration has been locked
[ATTACH external db]         ✓ BLOCKED  PermissionException: ... file system operations are disabled by configuration
[legit aggregate (control)]  ⚠ EXECUTED rows=[[2]]   (proves legit SQL still works)
```

Before the fix `read_text('.env')` returned `GEMINI_API_KEY=AIza…` in plaintext; it now raises
`PermissionException`. The stacked-statement bypass (`SELECT 1; SET enable_external_access=true; …`)
is independently defeated by `lock_configuration=true`. Filesystem reads, `read_csv`, `glob`, and
`ATTACH` are all denied; only ordinary table queries run.

Reproduce:
```bash
cd backend && .venv/bin/python -c "
from app.spreadsheet.store import run_select
for sql in [
  \"SELECT content FROM read_text('/etc/passwd')\",
  \"SELECT file FROM glob('/etc/*')\",
  'SELECT 1; SET enable_external_access=true; SELECT 1',
]:
    try: print('EXECUTED', run_select(sql))
    except Exception as e: print('BLOCKED', type(e).__name__)
"
```

## 2. Leaked API key is not committed anywhere

Searched for the literal key `AIzaSy…dt4k` (the value that leaked during the original probe):

| Search | Command | Result |
|---|---|---|
| Tracked files @ HEAD | `git grep -- "<key>"` | **not found** |
| Any Gemini key in tracked files | `git grep -I "AIzaSy"` | **not found** |
| Entire git history (all commits, `-S` pickaxe) | `git log --all -S "<key>"` | **never appears in any commit** |
| The DD artifact | `grep -c "<key>" docs/DUE_DILIGENCE.md` | **0** |
| `.env` (which does hold the key) | `git check-ignore backend/.env` / `git ls-files backend/.env` | **gitignored and untracked** |

The key lives only in `backend/.env`, which is gitignored and has never been committed. The DD
artifact references it as `AIza…` (redacted), never in full.

> Outstanding (owner action, not code): the leaked key should still be **rotated** in Google AI
> Studio and the new value put in `backend/.env` — it was exposed once during the original probe,
> even though the exfiltration path is now closed and the value is not in version control.
