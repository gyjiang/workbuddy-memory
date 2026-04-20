#!/bin/bash
#
# WorkBuddy Sync Script
# 用法:
#   ./wb-sync.sh              # 双向同步（pull + push）
#   ./wb-sync.sh pull         # 仅拉取远程最新
#   ./wb-sync.sh push         # 仅推送本地更改
#   ./wb-sync.sh setup        # 首次配置工作区路径
#
set -e

REPO_DIR="$HOME/.workbuddy"
WORKSPACE_MEMORY_DIR="$REPO_DIR/workspace-memory"
CONFIG_FILE="$REPO_DIR/.wb-sync-config"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[wb-sync]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[wb-sync]${NC} $1"; }
log_error() { echo -e "${RED}[wb-sync]${NC} $1"; }

# ---- 加载配置 ----
load_config() {
  if [[ -f "$CONFIG_FILE" ]]; then
    source "$CONFIG_FILE"
  fi

  # 默认：查找最近的 workspace（向上兼容多种目录结构）
  if [[ -z "$WORKSPACE_MEMORY_TARGET" ]]; then
    local wb_base
    wb_base=$(eval echo ~ 2>/dev/null || echo "$HOME")/WorkBuddy

    if [[ -d "$wb_base" ]]; then
      local latest_dir
      latest_dir=$(find "$wb_base" -maxdepth 2 -name ".workbuddy" -type d 2>/dev/null \
        | xargs -I{} dirname {} \
        | xargs -I{} ls -td "{}" \
        | head -1 2>/dev/null || echo "")

      if [[ -n "$latest_dir" ]]; then
        WORKSPACE_MEMORY_TARGET="$latest_dir/.workbuddy/memory"
        log_warn "未配置 WORKSPACE_MEMORY_TARGET，自动检测到: $WORKSPACE_MEMORY_TARGET"
      fi
    fi
  fi

  if [[ -z "$WORKSPACE_MEMORY_TARGET" ]]; then
    log_error "未找到 workspace memory 目录！请先运行 ./wb-sync.sh setup"
    exit 1
  fi
}

# ---- 配置工作区路径 ----
cmd_setup() {
  echo "当前已知的 workspace:"
  find "$HOME/WorkBuddy" -maxdepth 2 -name "memory" -type d 2>/dev/null \
    | xargs -I{} dirname {} \
    | while read dir; do
      echo "  $dir"
    done

  echo ""
  read -p "请输入你的 workspace memory 目录路径（按回车使用自动检测）: " user_input

  if [[ -n "$user_input" ]]; then
    if [[ ! -d "$user_input" ]]; then
      log_error "目录不存在: $user_input"
      exit 1
    fi
    WORKSPACE_MEMORY_TARGET="$user_input"
  fi

  echo "WORKSPACE_MEMORY_TARGET=\"$WORKSPACE_MEMORY_TARGET\"" > "$CONFIG_FILE"
  log_info "配置已保存到 $CONFIG_FILE"
  log_info "当前同步目标: $WORKSPACE_MEMORY_TARGET"
}

# ---- 双向同步 workspace-memory ↔ 实际 workspace ----
sync_workspace_memory() {
  log_info "同步 workspace-memory ↔ $WORKSPACE_MEMORY_TARGET"

  # 1. 确保目标目录存在
  mkdir -p "$WORKSPACE_MEMORY_TARGET"

  # 2. 把 Git 仓库中的 workspace-memory 同步到实际位置
  if [[ -d "$WORKSPACE_MEMORY_DIR" ]]; then
    for f in "$WORKSPACE_MEMORY_DIR"/*.md; do
      [[ -f "$f" ]] || continue
      local fname
      fname=$(basename "$f")
      cp "$f" "$WORKSPACE_MEMORY_TARGET/$fname"
      log_info "  ✓ 同步 $fname → workspace"
    done
  fi

  # 3. 把实际 workspace 的文件同步回 workspace-memory（如果有新文件）
  for f in "$WORKSPACE_MEMORY_TARGET"/*.md; do
    [[ -f "$f" ]] || continue
    local fname
    fname=$(basename "$f")
    local src_ts=0 dst_ts=0

    [[ -f "$WORKSPACE_MEMORY_DIR/$fname" ]] \
      && src_ts=$(stat -f "%m" "$WORKSPACE_MEMORY_DIR/$fname" 2>/dev/null || echo 0)
    [[ -f "$f" ]] \
      && dst_ts=$(stat -f "%m" "$f" 2>/dev/null || echo 0)

    if [[ "$dst_ts" -gt "$src_ts" ]]; then
      cp "$f" "$WORKSPACE_MEMORY_DIR/$fname"
      log_info "  ✓ 同步 $fname ← workspace（已更新）"
    fi
  done
}

# ---- Pull from remote ----
cmd_pull() {
  log_info "从 GitHub 拉取最新..."
  cd "$REPO_DIR"
  git pull origin main
}

# ---- Commit & Push local changes ----
cmd_push() {
  cd "$REPO_DIR"

  # 检查有没有变更
  if git diff --quiet && git diff --cached --quiet; then
    log_info "没有变更，无需推送。"
    return 0
  fi

  local timestamp
  timestamp=$(date "+%Y-%m-%d %H:%M")
  git add -A
  git commit -m "Sync $(date "+%Y-%m-%d %H:%M")"
  log_info "提交成功，正在推送..."
  git push origin main
}

# ---- 主流程 ----
main() {
  load_config

  local mode="${1:-both}"

  case "$mode" in
    pull)
      cmd_pull
      sync_workspace_memory
      ;;
    push)
      sync_workspace_memory
      cmd_push
      ;;
    both| "")
      cmd_pull
      sync_workspace_memory
      cmd_push
      ;;
    setup)
      cmd_setup
      ;;
    *)
      log_error "未知命令: $mode"
      echo "用法: $0 [pull|push|both|setup]"
      exit 1
      ;;
  esac

  log_info "同步完成 ✓"
}

main "$@"
