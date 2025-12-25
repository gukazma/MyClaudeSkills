---
name: cpp-build-discipline
description: Enforce incremental C++ development by requiring compilation verification after completing logical code units. Use when writing C++ code to prevent error accumulation. Triggers mandatory build checks after functional units are complete, blocking further development until errors are fixed. Supports multi-agent coordination with serialized build queue. Works with cpp-build-optimizer for filtered output.
---

# C++ Build Discipline

Enforce incremental development: verify compilation after each logical unit, fix errors before continuing.

## Core Rule

**After completing a logical code unit, MUST verify compilation. On failure, STOP and fix before writing new code.**

## Trigger Conditions

### Triggers Build (cmake --build)

| Condition | Action |
|-----------|--------|
| Logical function unit complete | Build |
| Header (.h/.hpp) modified AND corresponding .cpp modified | Build |
| Refactoring complete | Build |

### Triggers Configure + Build (cmake -B build)

| Condition | Action |
|-----------|--------|
| New source file added (.cpp/.h/.hpp) | Configure + Build |
| `vcpkg.json` modified | Configure + Build |
| `conanfile.txt` / `conanfile.py` modified | Configure + Build |
| `CMakeLists.txt` modified | Configure + Build |
| Any package manager config changed | Configure + Build |

### No Trigger

| Condition | Reason |
|-----------|--------|
| Comment/documentation only changes | No code impact |
| Header-only changes (no .cpp touched) | Defer until .cpp modified |
| Refactoring in progress | Wait for completion |

## Workflow

```
1. Write code for logical unit
2. Unit complete?
   - No  → Continue writing
   - Yes → Go to step 3
3. New files or config changed?
   - Yes → cmake configure first
   - No  → Skip to step 4
4. Run build with cpp-build-optimizer filter
5. Build result?
   - Success → Continue to next unit
   - Failure → STOP. Fix errors. Rebuild. Loop until pass.
```

## Build Commands

Use cpp-build-optimizer for filtered output:

```bash
# Standard build check
cmake --build build 2>&1 | python scripts/compile_filter.py

# After new files or config changes
cmake -B build -S . 2>&1 | python scripts/compile_filter.py && \
cmake --build build 2>&1 | python scripts/compile_filter.py
```

## Logical Unit Definition

A logical unit is a cohesive piece of functionality:

- Single function/method implementation
- Class with constructor and core methods
- Related changes across multiple files for one feature
- Bug fix touching multiple locations
- API endpoint with handler and helpers

**Key**: Changes serve ONE purpose and are testable together.

## Refactoring Mode

Auto-detect refactoring operations:

| Pattern | Detection |
|---------|-----------|
| Batch rename (variable/function/class) | Multiple files, same pattern replacement |
| Move/extract function | Delete from one file, add to another |
| Interface change | Signature change propagated to callers |
| File reorganization | Multiple file moves/renames |

**During refactoring**: Defer compilation until complete.
**After refactoring**: Mandatory full build verification.

## Error Handling

On build failure:

1. Display error output (filtered by cpp-build-optimizer)
2. **HARD STOP** - Do not write new code
3. Analyze and fix each error
4. Rebuild
5. Repeat until all errors resolved
6. Only then continue to next logical unit

## Multi-Agent Coordination

When multiple agents work in parallel on the same codebase, compilation verification must be serialized.

### Queue Protocol

```
Agent A completes unit → Request build slot → Wait if occupied → Build → Release slot
Agent B completes unit → Request build slot → Wait if occupied → Build → Release slot
```

### Rules

| Rule | Description |
|------|-------------|
| **One build at a time** | Only one agent can run compilation at any moment |
| **FIFO queue** | Agents queue in order of completion, first-come-first-served |
| **Hold until pass** | Agent holds build slot until compilation succeeds |
| **Block on failure** | Failed agent must fix errors before releasing slot |

### Workflow with Multiple Agents

```
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Agent A │  │ Agent B │  │ Agent C │
└────┬────┘  └────┬────┘  └────┬────┘
     │            │            │
     ▼            ▼            ▼
  Complete    Complete     Complete
   Unit 1      Unit 2       Unit 3
     │            │            │
     ▼            │            │
 ┌────────┐      │            │
 │ BUILD  │ ◄────┼────────────┤
 │ (A)    │   waiting      waiting
 └────┬───┘      │            │
     │ pass      │            │
     ▼           ▼            │
  Continue  ┌────────┐        │
            │ BUILD  │ ◄──────┤
            │ (B)    │     waiting
            └────┬───┘        │
                │ pass        │
                ▼             ▼
             Continue    ┌────────┐
                        │ BUILD  │
                        │ (C)    │
                        └────┬───┘
                            │ pass
                            ▼
                         Continue
```

### Conflict Resolution

| Scenario | Resolution |
|----------|------------|
| Two agents modify same file | Later agent must merge/resolve before build |
| Build fails due to other agent's code | Coordinate with responsible agent to fix |
| Deadlock (circular dependency) | Escalate to user for manual resolution |

### Communication Pattern

Before building, announce:
```
[BUILD QUEUE] Agent X requesting build slot for: <unit description>
[BUILD START] Agent X starting compilation
[BUILD DONE] Agent X completed (success/failure), releasing slot
```

## State Tracking

Track mentally:

- Modified headers pending .cpp verification
- Refactoring in progress (defer builds)
- New files added (needs configure)
- Package config changes (needs configure)
- **Build queue position** (multi-agent scenarios)
- **Other agents' pending changes** (conflict awareness)

## Integration with cpp-build-optimizer

This skill decides **WHEN** to build. cpp-build-optimizer handles **HOW** output is displayed.

| cpp-build-discipline | cpp-build-optimizer |
|---------------------|---------------------|
| Trigger timing | Output filtering |
| Error blocking | Token reduction |
| Unit completion detection | Error categorization |
| Configure vs build decision | Level escalation |

## Quick Reference

```
MUST BUILD after:
  [x] Function/method complete
  [x] Class structure complete
  [x] Feature spanning multiple files complete
  [x] Header + .cpp both modified
  [x] Refactoring complete

MUST CONFIGURE + BUILD after:
  [x] New .cpp/.h file added
  [x] vcpkg.json changed
  [x] conanfile.txt/py changed
  [x] CMakeLists.txt changed

SKIP BUILD for:
  [ ] Comments only
  [ ] Docs only
  [ ] Header only (no .cpp yet)
  [ ] Mid-refactoring

ON FAILURE:
  STOP → FIX → REBUILD → PASS → CONTINUE

MULTI-AGENT:
  [x] One build at a time (serialized)
  [x] FIFO queue for build requests
  [x] Announce: [BUILD QUEUE/START/DONE]
  [x] Hold slot until build passes
  [x] Resolve conflicts before building
```
