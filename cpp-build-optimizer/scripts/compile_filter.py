#!/usr/bin/env python3
"""
C++ Build Output Filter - Token-efficient compilation log processor.

Usage:
    python compile_filter.py [options] < build_output.log
    cmake --build build 2>&1 | python compile_filter.py

Options:
    --level 1|2|3|4    Output detail level (default: 2)
    --json             Output as JSON for programmatic use
    --full-on-error    Auto-escalate to level 4 on unresolved errors
"""

import sys
import re
import json
import argparse
from dataclasses import dataclass, field, asdict
from typing import Optional
from collections import defaultdict
from enum import IntEnum


class Level(IntEnum):
    MINIMAL = 1      # Success/Fail + counts only
    SUMMARY = 2      # Error locations + deduplicated warnings
    CONTEXT = 3      # Errors with surrounding context
    FULL = 4         # Complete output


@dataclass
class CompileError:
    file: str
    line: int
    column: int
    code: str           # Error code like C2065, E0020
    message: str
    context_before: list = field(default_factory=list)
    context_after: list = field(default_factory=list)
    severity: str = "error"

    def summary(self) -> str:
        loc = f"{self.file}:{self.line}"
        if self.column:
            loc += f":{self.column}"
        code_str = f"[{self.code}] " if self.code else ""
        return f"{loc}: {code_str}{self.message}"


@dataclass
class Warning:
    file: str
    line: int
    code: str
    message: str
    count: int = 1


@dataclass
class VcpkgProgress:
    total_packages: int = 0
    installed: list = field(default_factory=list)
    failed: list = field(default_factory=list)


@dataclass
class CMakeProgress:
    generator: str = ""
    build_type: str = ""
    found_packages: list = field(default_factory=list)
    missing_packages: list = field(default_factory=list)
    errors: list = field(default_factory=list)


@dataclass
class BuildResult:
    success: bool = False
    exit_code: int = 0
    errors: list = field(default_factory=list)
    warnings: dict = field(default_factory=dict)  # message -> Warning
    vcpkg: VcpkgProgress = field(default_factory=VcpkgProgress)
    cmake: CMakeProgress = field(default_factory=CMakeProgress)
    build_time: str = ""
    raw_lines: list = field(default_factory=list)

    # Error type classification for smart escalation
    error_types: dict = field(default_factory=lambda: defaultdict(list))


class BuildOutputParser:
    """Parse and filter C++ build output from various tools."""

    # MSVC error pattern: file(line,col): error C1234: message
    MSVC_ERROR = re.compile(
        r'^(.+?)\((\d+)(?:,(\d+))?\)\s*:\s*(error|fatal error)\s+(C\d+):\s*(.+)$'
    )
    MSVC_WARNING = re.compile(
        r'^(.+?)\((\d+)(?:,(\d+))?\)\s*:\s*warning\s+(C\d+):\s*(.+)$'
    )

    # GCC/Clang pattern: file:line:col: error: message
    GCC_ERROR = re.compile(
        r'^(.+?):(\d+):(\d+):\s*(error|fatal error):\s*(.+)$'
    )
    GCC_WARNING = re.compile(
        r'^(.+?):(\d+):(\d+):\s*warning:\s*(.+?)(?:\s*\[-W[\w-]+\])?$'
    )

    # CMake patterns
    CMAKE_ERROR = re.compile(r'^CMake Error.*?:\s*(.+)$', re.IGNORECASE)
    CMAKE_FOUND = re.compile(r'--\s+Found\s+(\w+):', re.IGNORECASE)
    CMAKE_NOT_FOUND = re.compile(r'Could NOT find\s+(\w+)', re.IGNORECASE)
    CMAKE_GENERATOR = re.compile(r'--\s+Selecting .+ generator:\s+(.+)$')
    CMAKE_BUILD_TYPE = re.compile(r'--\s+Build type:\s+(.+)$', re.IGNORECASE)

    # vcpkg patterns
    VCPKG_INSTALLING = re.compile(r'Installing\s+\d+/(\d+)\s+(.+?)(?::|\.\.\.)')
    VCPKG_INSTALLED = re.compile(r'Elapsed time to handle\s+(.+?):\s*')
    VCPKG_FAILED = re.compile(r'error:\s+building\s+(.+?)\s+failed', re.IGNORECASE)
    VCPKG_TOTAL = re.compile(r'The following packages will be built and installed:')

    # Linker patterns
    LINKER_ERROR = re.compile(r'(LNK\d+|undefined reference to|ld: error:)\s*(.+)')

    # Build time
    BUILD_TIME = re.compile(r'(?:Time Elapsed|Build completed in|Total time:)\s*(.+)', re.IGNORECASE)

    def __init__(self):
        self.result = BuildResult()
        self.context_buffer = []
        self.max_context = 3
        self.in_vcpkg_section = False
        self.vcpkg_package_list = []

    def parse_line(self, line: str):
        """Parse a single line of build output."""
        line = line.rstrip()
        self.result.raw_lines.append(line)

        # Track context for error messages
        self.context_buffer.append(line)
        if len(self.context_buffer) > self.max_context * 2 + 1:
            self.context_buffer.pop(0)

        # Detect vcpkg section
        if 'vcpkg' in line.lower() or self.in_vcpkg_section:
            self._parse_vcpkg(line)

        # Parse CMake output
        self._parse_cmake(line)

        # Parse compiler errors/warnings
        self._parse_compiler(line)

        # Parse linker errors
        self._parse_linker(line)

        # Parse build time
        if m := self.BUILD_TIME.search(line):
            self.result.build_time = m.group(1)

    def _parse_vcpkg(self, line: str):
        if 'The following packages will be built' in line:
            self.in_vcpkg_section = True
            return

        if self.in_vcpkg_section and line.strip().startswith('*'):
            # Package in list
            pkg = line.strip().lstrip('* ').split(':')[0].split('[')[0]
            if pkg:
                self.vcpkg_package_list.append(pkg)
            return

        if 'Restored' in line or 'Elapsed time' in line:
            self.in_vcpkg_section = False

        if m := self.VCPKG_INSTALLING.search(line):
            self.result.vcpkg.total_packages = int(m.group(1))

        if m := self.VCPKG_INSTALLED.search(line):
            pkg = m.group(1).split(':')[0]
            if pkg not in self.result.vcpkg.installed:
                self.result.vcpkg.installed.append(pkg)

        if m := self.VCPKG_FAILED.search(line):
            self.result.vcpkg.failed.append(m.group(1))

    def _parse_cmake(self, line: str):
        if m := self.CMAKE_ERROR.search(line):
            self.result.cmake.errors.append(m.group(1))

        if m := self.CMAKE_FOUND.search(line):
            pkg = m.group(1)
            if pkg not in self.result.cmake.found_packages:
                self.result.cmake.found_packages.append(pkg)

        if m := self.CMAKE_NOT_FOUND.search(line):
            pkg = m.group(1)
            if pkg not in self.result.cmake.missing_packages:
                self.result.cmake.missing_packages.append(pkg)

        if m := self.CMAKE_GENERATOR.search(line):
            self.result.cmake.generator = m.group(1)

        if m := self.CMAKE_BUILD_TYPE.search(line):
            self.result.cmake.build_type = m.group(1)

    def _parse_compiler(self, line: str):
        # Try MSVC patterns first
        if m := self.MSVC_ERROR.match(line):
            error = CompileError(
                file=m.group(1),
                line=int(m.group(2)),
                column=int(m.group(3)) if m.group(3) else 0,
                code=m.group(5),
                message=m.group(6),
                severity=m.group(4),
                context_before=self.context_buffer[:-1].copy()
            )
            self.result.errors.append(error)
            self._classify_error(error)
            return

        if m := self.MSVC_WARNING.match(line):
            self._add_warning(m.group(1), int(m.group(2)), m.group(4), m.group(5))
            return

        # Try GCC/Clang patterns
        if m := self.GCC_ERROR.match(line):
            error = CompileError(
                file=m.group(1),
                line=int(m.group(2)),
                column=int(m.group(3)),
                code="",
                message=m.group(5),
                severity=m.group(4),
                context_before=self.context_buffer[:-1].copy()
            )
            self.result.errors.append(error)
            self._classify_error(error)
            return

        if m := self.GCC_WARNING.match(line):
            self._add_warning(m.group(1), int(m.group(2)), "", m.group(4))
            return

    def _parse_linker(self, line: str):
        if m := self.LINKER_ERROR.search(line):
            error = CompileError(
                file="linker",
                line=0,
                column=0,
                code=m.group(1) if 'LNK' in m.group(1) else "LINK",
                message=m.group(2),
                severity="error"
            )
            self.result.errors.append(error)
            self.result.error_types["linker"].append(error)

    def _add_warning(self, file: str, line: int, code: str, message: str):
        key = f"{code}:{message}" if code else message
        if key in self.result.warnings:
            self.result.warnings[key].count += 1
        else:
            self.result.warnings[key] = Warning(file, line, code, message, 1)

    def _classify_error(self, error: CompileError):
        """Classify error for smart escalation decisions."""
        msg = error.message.lower()
        code = error.code

        # Syntax errors - usually self-explanatory
        if code in ['C2143', 'C2059', 'C2061'] or 'expected' in msg:
            self.result.error_types["syntax"].append(error)
        # Undefined identifier - may need more context
        elif code in ['C2065', 'C3861'] or 'undeclared' in msg or 'undefined' in msg:
            self.result.error_types["undefined"].append(error)
        # Type errors
        elif code in ['C2440', 'C2664'] or 'cannot convert' in msg:
            self.result.error_types["type"].append(error)
        # Include/header errors - often need to check paths
        elif code in ['C1083'] or 'cannot open' in msg or 'no such file' in msg:
            self.result.error_types["include"].append(error)
        # Template errors - complex, may need full context
        elif 'template' in msg or code in ['C2784', 'C2893']:
            self.result.error_types["template"].append(error)
        else:
            self.result.error_types["other"].append(error)

    def finalize(self):
        """Finalize parsing and determine success."""
        self.result.success = len(self.result.errors) == 0 and not self.result.cmake.errors
        if self.vcpkg_package_list:
            self.result.vcpkg.total_packages = len(self.vcpkg_package_list)
        return self.result


class OutputFormatter:
    """Format build results at different detail levels."""

    def __init__(self, result: BuildResult, level: Level):
        self.result = result
        self.level = level

    def format(self) -> str:
        if self.level == Level.MINIMAL:
            return self._format_minimal()
        elif self.level == Level.SUMMARY:
            return self._format_summary()
        elif self.level == Level.CONTEXT:
            return self._format_context()
        else:
            return self._format_full()

    def _format_minimal(self) -> str:
        lines = []
        status = "SUCCESS" if self.result.success else "FAILED"
        lines.append(f"Build: {status}")

        if self.result.errors:
            lines.append(f"Errors: {len(self.result.errors)}")
        if self.result.warnings:
            total_warnings = sum(w.count for w in self.result.warnings.values())
            lines.append(f"Warnings: {total_warnings} ({len(self.result.warnings)} unique)")
        if self.result.build_time:
            lines.append(f"Time: {self.result.build_time}")

        return "\n".join(lines)

    def _format_summary(self) -> str:
        lines = [self._format_minimal(), ""]

        # vcpkg summary
        if self.result.vcpkg.total_packages > 0:
            installed = len(self.result.vcpkg.installed)
            total = self.result.vcpkg.total_packages
            lines.append(f"vcpkg: Installed {installed}/{total} packages")
            if self.result.vcpkg.failed:
                lines.append(f"  Failed: {', '.join(self.result.vcpkg.failed)}")

        # CMake summary
        if self.result.cmake.missing_packages:
            lines.append(f"CMake: Missing packages: {', '.join(self.result.cmake.missing_packages)}")
        if self.result.cmake.errors:
            lines.append("CMake errors:")
            for err in self.result.cmake.errors[:3]:
                lines.append(f"  {err[:100]}")

        # Error summary
        if self.result.errors:
            lines.append("")
            lines.append("Errors:")
            for error in self.result.errors[:10]:
                lines.append(f"  {error.summary()}")
            if len(self.result.errors) > 10:
                lines.append(f"  ... and {len(self.result.errors) - 10} more errors")

        # Warning summary (deduplicated)
        if self.result.warnings:
            lines.append("")
            lines.append("Warnings (deduplicated):")
            sorted_warnings = sorted(
                self.result.warnings.values(),
                key=lambda w: w.count,
                reverse=True
            )
            for w in sorted_warnings[:5]:
                count_str = f" (x{w.count})" if w.count > 1 else ""
                code_str = f"[{w.code}] " if w.code else ""
                lines.append(f"  {w.file}:{w.line}: {code_str}{w.message[:80]}{count_str}")
            if len(sorted_warnings) > 5:
                lines.append(f"  ... and {len(sorted_warnings) - 5} more warning types")

        return "\n".join(lines)

    def _format_context(self) -> str:
        lines = [self._format_summary(), ""]

        if self.result.errors:
            lines.append("=" * 60)
            lines.append("ERROR DETAILS WITH CONTEXT")
            lines.append("=" * 60)

            for i, error in enumerate(self.result.errors[:5]):
                lines.append(f"\n--- Error {i+1}: {error.file}:{error.line} ---")
                if error.context_before:
                    for ctx in error.context_before[-3:]:
                        lines.append(f"  {ctx}")
                lines.append(f"> {error.summary()}")
                if error.context_after:
                    for ctx in error.context_after[:3]:
                        lines.append(f"  {ctx}")

        return "\n".join(lines)

    def _format_full(self) -> str:
        lines = [self._format_context(), ""]
        lines.append("=" * 60)
        lines.append("FULL BUILD OUTPUT")
        lines.append("=" * 60)
        lines.extend(self.result.raw_lines)
        return "\n".join(lines)

    def to_json(self) -> str:
        """Export result as JSON for programmatic use."""
        data = {
            "success": self.result.success,
            "error_count": len(self.result.errors),
            "warning_count": sum(w.count for w in self.result.warnings.values()),
            "build_time": self.result.build_time,
            "errors": [asdict(e) for e in self.result.errors],
            "warnings": [asdict(w) for w in self.result.warnings.values()],
            "error_types": {k: len(v) for k, v in self.result.error_types.items()},
            "vcpkg": asdict(self.result.vcpkg),
            "cmake": {
                "generator": self.result.cmake.generator,
                "build_type": self.result.cmake.build_type,
                "missing_packages": self.result.cmake.missing_packages,
                "errors": self.result.cmake.errors
            }
        }
        return json.dumps(data, indent=2)


def should_escalate(result: BuildResult, current_level: Level) -> tuple[bool, Level, str]:
    """Determine if we should auto-escalate to a higher detail level."""
    if current_level >= Level.FULL:
        return False, current_level, ""

    error_types = result.error_types

    # Template errors are complex - often need full context
    if error_types.get("template"):
        return True, Level.FULL, "Template errors detected - showing full context"

    # Include errors might need to see CMake/vcpkg output
    if error_types.get("include") and current_level < Level.CONTEXT:
        return True, Level.CONTEXT, "Include errors - showing path context"

    # Linker errors often need to see what was built
    if error_types.get("linker") and current_level < Level.CONTEXT:
        return True, Level.CONTEXT, "Linker errors - showing build context"

    # Multiple error types suggest complex issues
    error_type_count = sum(1 for v in error_types.values() if v)
    if error_type_count > 2 and current_level < Level.CONTEXT:
        return True, Level.CONTEXT, "Multiple error types - showing more context"

    return False, current_level, ""


def main():
    parser = argparse.ArgumentParser(description="Filter C++ build output for token efficiency")
    parser.add_argument("--level", type=int, choices=[1, 2, 3, 4], default=2,
                       help="Output detail level (1=minimal, 2=summary, 3=context, 4=full)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--full-on-error", action="store_true",
                       help="Auto-escalate to level 4 on complex errors")
    parser.add_argument("input", nargs="?", help="Input file (default: stdin)")
    args = parser.parse_args()

    # Read input
    if args.input:
        with open(args.input, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    else:
        lines = sys.stdin.readlines()

    # Parse
    build_parser = BuildOutputParser()
    for line in lines:
        build_parser.parse_line(line)
    result = build_parser.finalize()

    # Determine output level
    level = Level(args.level)
    if args.full_on_error and not result.success:
        should_esc, new_level, reason = should_escalate(result, level)
        if should_esc:
            print(f"[Auto-escalating: {reason}]", file=sys.stderr)
            level = new_level

    # Format output
    formatter = OutputFormatter(result, level)
    if args.json:
        print(formatter.to_json())
    else:
        print(formatter.format())

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
