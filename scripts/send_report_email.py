#!/usr/bin/env python3
"""数据要素洞察报告邮件发送脚本"""

import smtplib
import sys
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# SMTP 配置
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 587
SENDER = "441919123@qq.com"
AUTH_CODE = "uamyfvpbdjfxcadc"
RECIPIENTS = ["zoujunfeng1@huawei.com", "linana19@h-partners.com"]
SUBJECT = "数据要素洞察报告"


def markdown_to_html(md_text: str) -> str:
    import markdown
    body = markdown.markdown(md_text, extensions=["tables", "toc"])
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.7; font-size: 15px; color: #2c3e50; }}
h1 {{ border-bottom: 2px solid #c0392b; padding-bottom: 10px; color: #2c3e50; }}
h2 {{ border-bottom: 1px solid #2980b9; padding-bottom: 8px; color: #2c3e50; margin-top: 30px; }}
h3 {{ color: #2b6cb0; margin-top: 24px; }}
a {{ text-decoration: none; color: #3182ce; }}
hr {{ border: none; border-top: 1px solid #ecf0f1; margin: 20px 0; }}
strong {{ color: #c0392b; }}
code {{ background-color: #f1f5f9; color: #c0392b; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-family: ui-monospace, monospace; font-size: 0.9em; }}
ul {{ padding-left: 20px; }}
li {{ margin-bottom: 12px; }}
h2:last-of-type {{ font-size: 16px; margin-top: 40px; color: #718096; }}
h2:last-of-type + p {{ font-size: 13px; color: #4a5568; }}
h2:last-of-type + p + ol {{ font-size: 13px; color: #4a5568; padding-left: 15px; line-height: 1.4; }}
h2:last-of-type + p + ol li {{ margin-bottom: 4px; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def send_email(report_path: str):
    if not os.path.exists(report_path):
        print(f"Error: Report file not found: {report_path}")
        sys.exit(1)

    with open(report_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    date_str = datetime.now().strftime("%Y-%m-%d")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{SUBJECT} - {date_str}"
    msg["From"] = SENDER
    msg["To"] = ", ".join(RECIPIENTS)

    msg.attach(MIMEText(md_content, "plain", "utf-8"))
    msg.attach(MIMEText(markdown_to_html(md_content), "html", "utf-8"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER, AUTH_CODE)
        server.sendmail(SENDER, RECIPIENTS, msg.as_string())
        server.quit()
        print(f"Email sent successfully to {', '.join(RECIPIENTS)}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <report_path>")
        sys.exit(1)
    send_email(sys.argv[1])
