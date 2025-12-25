# MyClaudeSkills Project Overview

**Repository**: https://github.com/gukazma/MyClaudeSkills
**Purpose**: Custom Claude Code skills for C++ development workflow optimization

## Skills

### 1. cpp-build-optimizer
Token-efficient C++ build output filter.
- Reduces build log tokens by 80-95%
- 4-level progressive output verbosity
- Smart escalation based on error types
- Supports CMake/vcpkg/MSVC/GCC/Clang

### 2. cpp-build-discipline
Enforces incremental development discipline.
- Mandatory build verification after logical code units
- Hard block on errors until fixed
- Auto-detects refactoring mode
- Triggers cmake configure on config changes
- Cooperates with cpp-build-optimizer

## Project Structure

```
MyClaudeSkills/
├── README.md              # English documentation
├── README_zh.md           # Chinese documentation
├── cpp-build-optimizer/
│   ├── SKILL.md
│   └── scripts/
│       └── compile_filter.py
├── cpp-build-optimizer.skill
├── cpp-build-discipline/
│   └── SKILL.md
└── cpp-build-discipline.skill
```

## Skill Cooperation

The two skills work together:
- cpp-build-discipline decides WHEN to compile
- cpp-build-optimizer decides HOW to filter output

## Documentation

Bilingual README with language switcher at top:
```markdown
[English](README.md) | [中文](README_zh.md)
```
