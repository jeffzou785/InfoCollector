#!/bin/bash
# 测试：5个数据源的定时任务全流程（含邮件）

PROJECT_ROOT="/Users/quartet/data-elements"
cd "$PROJECT_ROOT"

REPORT_DATE=$(date +%Y-%m-%d)
REPORT_FILE="${PROJECT_ROOT}/reports/数据要素宏观洞察-${REPORT_DATE}.md"
LOG_FILE="${PROJECT_ROOT}/scripts/logs/test-${REPORT_DATE}.log"
TIMEOUT=1800

mkdir -p scripts/logs

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== 测试开始（5个数据源）==="
log "报告文件: $REPORT_FILE"

START_TIME=$(date +%s)

/opt/homebrew/opt/coreutils/libexec/gnubin/timeout --foreground --kill-after 10 "$TIMEOUT" \
  /opt/homebrew/bin/claude -p "执行 /data-news skill，只处理以下5个信息源：国家数据局、数据要素社、数据资产从0到1、北京数据、数据要素市场。忽略 SITE.md 中的其他信息源。生成洞察报告并发送邮件。" \
  --dangerously-skip-permissions \
  --output-format text \
  >> "$LOG_FILE" 2>&1
CLAUDE_EXIT=$?

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
log "claude 执行结束，退出码: $CLAUDE_EXIT，耗时: ${ELAPSED} 秒"

if [ $CLAUDE_EXIT -ne 0 ]; then
  log "错误：claude 执行失败，退出码 $CLAUDE_EXIT"
  exit 1
fi

# 检查报告
if [ -f "$REPORT_FILE" ]; then
  REPORT_SIZE=$(wc -c < "$REPORT_FILE")
  log "报告生成成功: $REPORT_FILE (${REPORT_SIZE} 字节)，开始发送邮件"

  /opt/homebrew/opt/coreutils/libexec/gnubin/timeout --foreground --kill-after 5 120 \
    python3 "${PROJECT_ROOT}/scripts/send_report_email.py" "$REPORT_FILE" \
    >> "$LOG_FILE" 2>&1
  EMAIL_EXIT=$?

  if [ $EMAIL_EXIT -eq 0 ]; then
    log "邮件发送成功"
  else
    log "错误：邮件发送失败，退出码 $EMAIL_EXIT"
  fi
else
  log "错误：报告文件未生成 $REPORT_FILE"
fi

log "=== 测试结束 ==="
