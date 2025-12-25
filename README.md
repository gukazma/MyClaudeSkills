# MyClaudeSkills

[English](README.md) | [中文](README_zh.md)

Custom Claude Code skills collection for optimizing development workflows.

## Skills

### cpp-build-optimizer

Token-efficient C++ build output filter for CMake/vcpkg/MSVC/GCC/Clang.

**Features:**
- Reduces build log token consumption by 80-95%
- 4-level progressive output verbosity
- Smart escalation based on error types
- Warning deduplication
- vcpkg/CMake progress compression
- JSON output support

### cpp-build-discipline

Enforces incremental C++ development by requiring compilation verification after logical code units.

**Features:**
- Mandatory build verification after completing functional units
- Hard block on errors - must fix before continuing
- Auto-detects refactoring mode (defers builds until complete)
- Triggers cmake configure on new files or package config changes
- **Multi-agent coordination with serialized build queue**
- Works together with cpp-build-optimizer for filtered output

**Trigger Conditions:**

| Condition | Action |
|-----------|--------|
| Logical function unit complete | Build |
| Header + corresponding .cpp modified | Build |
| Refactoring complete | Build |
| New source file added | Configure + Build |
| vcpkg.json / conanfile / CMakeLists.txt changed | Configure + Build |

**Core Rule:** `Build Failed → STOP → Fix → Rebuild → Pass → Continue`

**Multi-Agent:** When multiple agents work in parallel, builds are serialized via FIFO queue. Each agent announces `[BUILD QUEUE/START/DONE]` and holds the slot until compilation passes.

## Installation

### Method 1: Direct Copy

```bash
# Clone repository
git clone https://github.com/gukazma/MyClaudeSkills.git

# Copy skills to Claude skills directory
cp -r MyClaudeSkills/cpp-build-optimizer ~/.claude/skills/
cp -r MyClaudeSkills/cpp-build-discipline ~/.claude/skills/
```

### Method 2: Symbolic Link

```bash
git clone https://github.com/gukazma/MyClaudeSkills.git
ln -s $(pwd)/MyClaudeSkills/cpp-build-optimizer ~/.claude/skills/cpp-build-optimizer
ln -s $(pwd)/MyClaudeSkills/cpp-build-discipline ~/.claude/skills/cpp-build-discipline
```

### Windows Users

```powershell
git clone https://github.com/gukazma/MyClaudeSkills.git
Copy-Item -Recurse MyClaudeSkills\cpp-build-optimizer $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse MyClaudeSkills\cpp-build-discipline $env:USERPROFILE\.claude\skills\
```

## Usage

### Auto Trigger

- **cpp-build-optimizer**: Activates when Claude detects `CMakeLists.txt` in project
- **cpp-build-discipline**: Activates when writing C++ code, enforcing build checks

### Manual Usage (cpp-build-optimizer)

```bash
# Default Level 2 summary output
cmake --build build 2>&1 | python ~/.claude/skills/cpp-build-optimizer/scripts/compile_filter.py

# Minimal output (success/fail only)
cmake --build build 2>&1 | python compile_filter.py --level 1

# Smart escalation mode
cmake --build build 2>&1 | python compile_filter.py --full-on-error

# JSON format output
cmake --build build 2>&1 | python compile_filter.py --json
```

### Output Levels

| Level | Content | Token Cost | Use Case |
|-------|---------|------------|----------|
| 1 | Success/fail + counts | 20-50 | Quick status check |
| 2 | Error summary + deduplicated warnings | 100-500 | Daily builds (default) |
| 3 | Errors + code context | 500-2000 | Debugging specific issues |
| 4 | Full output | All | Last resort |

### Output Example

**Level 2 (Default):**

```
Build: FAILED
Errors: 3
Warnings: 12 (5 unique)
Time: 00:01:23

vcpkg: Installed 8/8 packages

Errors:
  src/main.cpp:42:5: [C2065] 'undefined_var': undeclared identifier
  src/utils.cpp:18:12: [C2440] cannot convert 'int' to 'std::string'
  src/parser.cpp:156:1: [C2143] syntax error: missing ';' before '}'

Warnings (deduplicated):
  src/old_api.cpp:23: [C4996] deprecated function (x7)
  src/math.cpp:45: [C4244] conversion from 'double' to 'int' (x3)
```

### Smart Escalation Rules

| Error Type | Auto Action |
|------------|-------------|
| Syntax error | Stay at current level |
| Undefined identifier | Stay at current level |
| Type mismatch | Stay at current level |
| Header/include error | Escalate to Level 3 |
| Linker error | Escalate to Level 3 |
| Template error | Escalate to Level 4 |
| Multiple error types | Escalate to Level 3 |

## Token Savings

| Project Size | Raw Log | Filtered (L2) | Savings |
|--------------|---------|---------------|---------|
| Small (10 files) | 2,000 | 200 | 90% |
| Medium (100 files) | 15,000 | 400 | 97% |
| Large (500+ files) | 50,000+ | 600 | 99% |

## Supported Toolchains

- **Compilers**: MSVC, GCC, Clang
- **Build Systems**: CMake, Ninja, Make
- **Package Managers**: vcpkg, Conan

## License

MIT
