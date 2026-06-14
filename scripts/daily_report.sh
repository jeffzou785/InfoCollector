#!/bin/bash
# 每日数据要素洞察报告生成与邮件发送

PROJECT_ROOT="/Users/quartet/data-elements"
cd "$PROJECT_ROOT"

REPORT_DATE=$(date +%Y-%m-%d)
REPORT_FILE="${PROJECT_ROOT}/reports/数据要素宏观洞察-${REPORT_DATE}.md"
LOG_FILE="${PROJECT_ROOT}/scripts/logs/${REPORT_DATE}.log"
TIMEOUT=1800 # 30分钟超时
WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=99b7a59c-100a-4b64-ab63-76aa5873a860"

mkdir -p scripts/logs

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

notify_wechat() {
  local content="$1"
  curl -s -X POST "$WEBHOOK_URL" \
    -H 'Content-Type: application/json' \
    -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"${content}\"}}" \
    > /dev/null 2>&1
}

log "开始执行每日报告任务"
log "工作目录: $(pwd)"
log "报告文件: $REPORT_FILE"
log "claude 版本: $(/opt/homebrew/bin/claude --version 2>&1 || echo '未知')"

# 使用 Claude Code 非交互模式执行 data-news skill，带超时
# --foreground: 确保能杀掉整个进程组
# --kill-after 10: SIGTERM 后 10 秒发 SIGKILL 强杀
log "启动 claude 执行 data-news skill（超时 ${TIMEOUT} 秒）"
START_TIME=$(date +%s)

/opt/homebrew/opt/coreutils/libexec/gnubin/timeout --foreground --kill-after 10 "$TIMEOUT" \
  /opt/homebrew/bin/claude -p "执行 /data-news skill，生成最近24小时的洞察报告。注意：不要自行发送邮件，邮件由外部脚本处理。" \
  --dangerously-skip-permissions \
  --output-format text \
  >> "$LOG_FILE" 2>&1
CLAUDE_EXIT=$?

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
log "claude 执行结束，退出码: $CLAUDE_EXIT，耗时: ${ELAPSED} 秒"

if [ $CLAUDE_EXIT -eq 124 ]; then
  log "错误：claude 执行超时（${TIMEOUT}秒），终止任务"
  exit 1
elif [ $CLAUDE_EXIT -eq 137 ]; then
  log "错误：claude 执行超时被强制终止（SIGKILL）"
  exit 1
elif [ $CLAUDE_EXIT -ne 0 ]; then
  log "错误：claude 执行失败，退出码 $CLAUDE_EXIT"
  exit 1
fi

# 列出工作目录中可能生成的文件
log "检查生成的文件: $(ls -1 "${PROJECT_ROOT}/reports/${REPORT_DATE}/" 2>/dev/null | head -20 || echo '目录不存在')"

# 检查报告文件是否生成并自动发送邮件
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
    notify_wechat "⚠️ 数据要素洞察报告邮件发送失败\n日期: ${REPORT_DATE}\n退出码: ${EMAIL_EXIT}"
  fi
else
  log "错误：报告文件未生成 $REPORT_FILE"
  notify_wechat "⚠️ 数据要素洞察报告文件未生成\n日期: ${REPORT_DATE}"
  log "当前目录文件列表: $(ls -1 "${PROJECT_ROOT}/reports/"*.md 2>/dev/null || echo '无 md 文件')"
fi

log "任务结束"
