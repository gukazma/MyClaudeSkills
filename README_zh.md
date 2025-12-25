# MyClaudeSkills

[English](README.md) | [中文](README_zh.md)

自定义 Claude Code 技能集合，用于优化开发工作流程。

## 技能列表

### cpp-build-optimizer

Token 高效的 C++ 编译输出过滤器，支持 CMake/vcpkg/MSVC/GCC/Clang。

**核心功能：**
- 将编译日志 token 消耗降低 80-95%
- 4 级渐进式输出详细程度
- 基于错误类型的智能升级策略
- 警告去重合并显示
- vcpkg/CMake 进度压缩
- JSON 输出支持

### cpp-build-discipline

强制增量式 C++ 开发，要求在完成逻辑代码单元后必须验证编译。

**核心功能：**
- 完成功能单元后强制编译验证
- 错误时硬性阻止 - 必须修复后才能继续
- 自动检测重构模式（延迟到重构完成后再验证）
- 新文件或包配置变更时触发 cmake configure
- **多智能体协调，序列化编译队列**
- 与 cpp-build-optimizer 协同工作，输出过滤

**触发条件：**

| 条件 | 动作 |
|-----|------|
| 逻辑功能单元完成 | 编译 |
| 头文件 + 对应 .cpp 都被修改 | 编译 |
| 重构完成 | 编译 |
| 新增源文件 | Configure + 编译 |
| vcpkg.json / conanfile / CMakeLists.txt 变更 | Configure + 编译 |

**核心规则：** `编译失败 → 停止 → 修复 → 重新编译 → 通过 → 继续`

**多智能体：** 当多个智能体并行工作时，编译通过 FIFO 队列序列化。每个智能体通过 `[BUILD QUEUE/START/DONE]` 通信，持有编译槽直到编译通过。

## 安装

### 方法 1：直接复制

```bash
# 克隆仓库
git clone https://github.com/gukazma/MyClaudeSkills.git

# 复制技能到 Claude 技能目录
cp -r MyClaudeSkills/cpp-build-optimizer ~/.claude/skills/
cp -r MyClaudeSkills/cpp-build-discipline ~/.claude/skills/
```

### 方法 2：符号链接

```bash
git clone https://github.com/gukazma/MyClaudeSkills.git
ln -s $(pwd)/MyClaudeSkills/cpp-build-optimizer ~/.claude/skills/cpp-build-optimizer
ln -s $(pwd)/MyClaudeSkills/cpp-build-discipline ~/.claude/skills/cpp-build-discipline
```

### Windows 用户

```powershell
git clone https://github.com/gukazma/MyClaudeSkills.git
Copy-Item -Recurse MyClaudeSkills\cpp-build-optimizer $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse MyClaudeSkills\cpp-build-discipline $env:USERPROFILE\.claude\skills\
```

## 使用方法

### 自动触发

- **cpp-build-optimizer**：当 Claude 检测到项目中存在 `CMakeLists.txt` 时自动激活
- **cpp-build-discipline**：编写 C++ 代码时自动激活，强制编译检查

### 手动使用 (cpp-build-optimizer)

```bash
# 默认 Level 2 摘要输出
cmake --build build 2>&1 | python ~/.claude/skills/cpp-build-optimizer/scripts/compile_filter.py

# 最简输出（仅成功/失败）
cmake --build build 2>&1 | python compile_filter.py --level 1

# 智能升级模式（复杂错误自动显示更多上下文）
cmake --build build 2>&1 | python compile_filter.py --full-on-error

# JSON 格式输出
cmake --build build 2>&1 | python compile_filter.py --json
```

### 输出级别

| Level | 内容 | Token 消耗 | 适用场景 |
|-------|------|-----------|---------|
| 1 | 成功/失败 + 计数 | 20-50 | 快速状态检查 |
| 2 | 错误摘要 + 去重警告 | 100-500 | 日常编译（默认） |
| 3 | 错误 + 代码上下文 | 500-2000 | 调试特定问题 |
| 4 | 完整输出 | 全部 | 最后手段 |

### 输出示例

**Level 2（默认）：**

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

### 智能升级规则

| 错误类型 | 自动操作 |
|---------|---------|
| 语法错误 | 保持当前级别 |
| 未定义标识符 | 保持当前级别 |
| 类型不匹配 | 保持当前级别 |
| 头文件/包含错误 | 升级到 Level 3 |
| 链接器错误 | 升级到 Level 3 |
| 模板错误 | 升级到 Level 4 |
| 多种错误类型 | 升级到 Level 3 |

## Token 节省效果

| 项目规模 | 原始日志 | 过滤后 (L2) | 节省 |
|---------|---------|------------|------|
| 小型 (10 文件) | 2,000 | 200 | 90% |
| 中型 (100 文件) | 15,000 | 400 | 97% |
| 大型 (500+ 文件) | 50,000+ | 600 | 99% |

## 支持的工具链

- **编译器**: MSVC, GCC, Clang
- **构建系统**: CMake, Ninja, Make
- **包管理**: vcpkg, Conan

## 许可证

MIT
