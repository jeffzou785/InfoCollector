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

# claude 调用封装为函数，便于 MD 缺失时自动重试
# --foreground: 确保能杀掉整个进程组
# --kill-after 10: SIGTERM 后 10 秒发 SIGKILL 强杀
run_claude() {
  /opt/homebrew/opt/coreutils/libexec/gnubin/timeout --foreground --kill-after 10 "$TIMEOUT" \
    /opt/homebrew/bin/claude -p "执行 /data-news skill，生成最近24小时的洞察报告。注意：不要自行发送邮件，邮件由外部脚本处理。" \
    --dangerously-skip-permissions \
    --output-format text \
    >> "$LOG_FILE" 2>&1
}

# 最多重试 2 次：report-synthesizer 偶发跳步不写 MD，重跑通常能成功
MAX_ATTEMPTS=2
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  ATTEMPT=$((ATTEMPT + 1))
  log "启动 claude 执行 data-news skill（第 $ATTEMPT/$MAX_ATTEMPTS 次，超时 ${TIMEOUT} 秒）"
  START_TIME=$(date +%s)
  run_claude
  CLAUDE_EXIT=$?
  END_TIME=$(date +%s)
  ELAPSED=$((END_TIME - START_TIME))
  log "claude 第 $ATTEMPT 次执行结束，退出码: $CLAUDE_EXIT，耗时: ${ELAPSED} 秒"

  # 进程级失败（超时/被强杀/非零退出）：直接终止，重试无意义
  if [ $CLAUDE_EXIT -eq 124 ] || [ $CLAUDE_EXIT -eq 137 ]; then
    log "错误：claude 执行超时被终止（退出码 $CLAUDE_EXIT）"
    notify_wechat "⚠️ 数据要素洞察报告执行超时\n日期: ${REPORT_DATE}\n退出码: ${CLAUDE_EXIT}"
    exit 1
  elif [ $CLAUDE_EXIT -ne 0 ]; then
    log "错误：claude 执行失败，退出码 $CLAUDE_EXIT"
    notify_wechat "⚠️ 数据要素洞察报告 claude 执行失败\n日期: ${REPORT_DATE}\n退出码: ${CLAUDE_EXIT}"
    exit 1
  fi

  log "检查生成的文件: $(ls -1 "${PROJECT_ROOT}/reports/${REPORT_DATE}/" 2>/dev/null | head -20 || echo '目录不存在')"

  # MD 报告存在且非空 → 成功跳出
  if [ -s "$REPORT_FILE" ]; then
    [ $ATTEMPT -gt 1 ] && log "info: MD 报告在第 $ATTEMPT 次执行后生成（经一次重试）"
    break
  fi

  # MD 缺失：report-synthesizer 偶发跳步，重试一次兜底
  if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
    log "警告：MD 报告文件未生成 $REPORT_FILE，将自动重试一次（report-synthesizer 偶发跳步兜底）"
  fi
done

# 检查报告文件是否生成并自动发送邮件
if [ -s "$REPORT_FILE" ]; then
  REPORT_SIZE=$(wc -c < "$REPORT_FILE")
  log "报告生成成功: $REPORT_FILE (${REPORT_SIZE} 字节)，开始发送邮件"

  /opt/homebrew/opt/coreutils/libexec/gnubin/timeout --foreground --kill-after 5 120 \
    "${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/scripts/send_report_email.py" "$REPORT_FILE" \
    >> "$LOG_FILE" 2>&1
  EMAIL_EXIT=$?

  if [ $EMAIL_EXIT -eq 0 ]; then
    log "邮件发送成功"
  else
    log "错误：邮件发送失败，退出码 $EMAIL_EXIT"
    notify_wechat "⚠️ 数据要素洞察报告邮件发送失败\n日期: ${REPORT_DATE}\n退出码: ${EMAIL_EXIT}"
  fi
else
  log "错误：重试 $MAX_ATTEMPTS 次后 MD 报告文件仍未生成 $REPORT_FILE"
  notify_wechat "⚠️ 数据要素洞察报告文件未生成（已重试 $MAX_ATTEMPTS 次）\n日期: ${REPORT_DATE}"
  log "当前目录文件列表: $(ls -1 "${PROJECT_ROOT}/reports/"*.md 2>/dev/null || echo '无 md 文件')"
fi

log "任务结束"
