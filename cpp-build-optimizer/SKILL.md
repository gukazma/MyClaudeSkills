---
name: cpp-build-optimizer
description: Token-efficient C++ build output processing for CMake/vcpkg/MSVC/GCC/Clang projects. Use when detecting CMakeLists.txt in project, running cmake configure/build commands, or when user requests C++ compilation. Reduces build log tokens by 80-95% through intelligent filtering while preserving actionable error information.
---

# C++ Build Optimizer

Minimize token usage when compiling C++ projects by filtering verbose build output.

## Quick Reference

### Running Builds with Filtering

```bash
# Basic build with summary output (Level 2)
cmake --build build 2>&1 | python scripts/compile_filter.py

# Minimal output - just success/fail counts
cmake --build build 2>&1 | python scripts/compile_filter.py --level 1

# Auto-escalate on complex errors
cmake --build build 2>&1 | python scripts/compile_filter.py --full-on-error

# JSON output for parsing
cmake --build build 2>&1 | python scripts/compile_filter.py --json
```

### Output Levels

| Level | Content | ~Tokens | Use When |
|-------|---------|---------|----------|
| 1 | Success/fail + counts | 20-50 | Quick status check |
| 2 | Error summaries + deduplicated warnings | 100-500 | Default for most builds |
| 3 | Errors with code context | 500-2000 | Debugging specific issues |
| 4 | Full output | All | Last resort only |

## Workflow

### Step 1: Configure (First Time)

```bash
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
```

Filter configure output:
```bash
cmake -B build -S . 2>&1 | python scripts/compile_filter.py --level 2
```

### Step 2: Build with Filtering

Always pipe build output through the filter:

```bash
cmake --build build --config Release 2>&1 | python scripts/compile_filter.py
```

### Step 3: Handle Errors

On build failure, the filter outputs error summaries. Process errors by type:

**Syntax errors** (missing semicolons, brackets): Fix directly from summary.

**Undefined symbols**: Check includes and forward declarations.

**Type mismatches**: Review function signatures.

**Include errors**: Verify paths in CMakeLists.txt or vcpkg.json.

**Template errors**: Complex - may need `--level 4` for full context.

**Linker errors**: Check library linkage in CMakeLists.txt.

### Step 4: Escalate Only When Needed

If Level 2 summary insufficient:

```bash
# Try Level 3 first (adds context lines)
cmake --build build 2>&1 | python scripts/compile_filter.py --level 3

# Only if still unclear, use Level 4
cmake --build build 2>&1 | python scripts/compile_filter.py --level 4
```

## Smart Escalation

Use `--full-on-error` flag for automatic escalation based on error type:

| Error Type | Auto Action |
|------------|-------------|
| Syntax | Stay at current level |
| Undefined identifier | Stay at current level |
| Type mismatch | Stay at current level |
| Include/header | Escalate to Level 3 |
| Linker | Escalate to Level 3 |
| Template | Escalate to Level 4 |
| Multiple types | Escalate to Level 3 |

## Output Format Examples

### Level 1 (Minimal)
```
Build: FAILED
Errors: 3
Warnings: 12 (5 unique)
Time: 00:01:23
```

### Level 2 (Summary)
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
  ... and 3 more warning types
```

### JSON Output
```json
{
  "success": false,
  "error_count": 3,
  "warning_count": 12,
  "error_types": {"undefined": 1, "type": 1, "syntax": 1},
  "vcpkg": {"total_packages": 8, "installed": [...], "failed": []}
}
```

## vcpkg Integration

vcpkg output is automatically summarized:

- Package download/extract logs: Hidden
- Dependency resolution: Hidden
- Build progress: Shown as "Installing X/Y packages"
- Failed packages: Listed explicitly

## CMake Integration

CMake output filtering:

- Compiler detection: Hidden
- Feature checks: Hidden
- Found packages: Hidden (unless missing)
- Missing packages: Shown
- Configuration errors: Shown

## Token Savings

Typical savings by project size:

| Project | Raw Output | Filtered (L2) | Savings |
|---------|------------|---------------|---------|
| Small (10 files) | 2,000 | 200 | 90% |
| Medium (100 files) | 15,000 | 400 | 97% |
| Large (500+ files) | 50,000+ | 600 | 99% |

## Troubleshooting

**Filter not detecting errors**: Ensure stderr is captured with `2>&1`.

**Missing context**: Use `--level 3` or `--level 4`.

**vcpkg not summarized**: Ensure vcpkg output is in the piped stream.

**Windows PowerShell**: Use `2>&1` or run in cmd.exe.
