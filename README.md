# AWS_Stop_EC2
掃描 AWS EC2 數量，並關機的程式碼。
將此程式碼內容放上 Lambda，並配合 EventBridge，可達成自動關機排程的效果，並將結果訊息發佈於 Slack

須設定環境變數 SLACK_WEBHOOK_URL，指向 Slack Webhook
