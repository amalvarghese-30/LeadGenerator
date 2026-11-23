# Project Agent Guidelines — Candid Digital CRM

## Engineering Runtime Protocol: Gravitas
Always apply the **Gravitas** engineering protocol (`.agents/skills/gravitas/SKILL.md`) for all implementation, debugging, refactoring, and code changes in this repository.

### The 6 Core Invariants:
1. **Ground before mutating:** Always read the target code, callers, and tests before modifying any file. Never act on assumed state.
2. **Stay in declared scope:** Only modify files directly required for the task. Leave unrelated files untouched.
3. **Completion requires evidence:** Never claim a fix, feature, or refactor is completed without actual observed verification output (running tests, build commands, or typecheck). If you did not verify, explicitly state that you did not verify.
4. **Never exact-retry a failure:** If a tool call, test, or build command fails, diagnose the root cause and change strategy. Do not repeat identical failed commands.
5. **Satisfy acceptance criteria:** Verify all stated requirements before marking a task complete.
6. **Transparent caveats:** Report what passed with real terminal output, and explicitly note any edge cases or items that could not be verified.
