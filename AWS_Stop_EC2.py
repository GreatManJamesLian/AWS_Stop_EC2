import boto3
import logging
import json
import urllib3
import os

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize HTTP client for Slack
http = urllib3.PoolManager()

def send_to_slack(message):
    """
    Send message to Slack channel using webhook URL
    """
    try:
        slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        
        if not slack_webhook_url:
            logger.error('SLACK_WEBHOOK_URL environment variable is not set')
            return False
        
        encoded_msg = json.dumps({
            'text': message
        }).encode('utf-8')
        
        response = http.request('POST',
                              slack_webhook_url,
                              body=encoded_msg,
                              headers={'Content-Type': 'application/json'})
        
        if response.status != 200:
            logger.error(f'Failed to send message to Slack. Status code: {response.status}')
            return False
            
        return True
        
    except Exception as e:
        logger.error(f'Error sending message to Slack: {str(e)}')
        return False

def lambda_handler(event, context):
    # Retrieve AWS account ID using STS
    try:
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity().get('Account')
        account_info = f'AWS 帳號 {account_id} 正在執行關機程序'
        logger.info(account_info)
    except Exception as e:
        account_info = '無法取得 AWS 帳號資訊'
        logger.error(f'取得 AWS 帳號 ID 時發生錯誤: {str(e)}')

    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
    errors = []
    success_count = 0
    slack_messages = [account_info]  # 開始加入帳號資訊到 Slack 訊息中

    # Loop through each region
    for region in regions:
        try:
            regional_ec2 = boto3.client('ec2', region_name=region)
            instances = regional_ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )
            
            # Loop through each running instance
            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    instance_id = instance['InstanceId']
                    tags = instance.get('Tags', [])
                    
                    # Check for the AutoStop tag
                    auto_stop = False
                    for tag in tags:
                        if tag['Key'] == 'AutoStop' and tag['Value'].lower() == 'no':
                            auto_stop = True
                            break
                    
                    if not auto_stop:
                        message = f'正在停止執行個體 {instance_id} (區域: {region})'
                        logger.info(message)
                        slack_messages.append(message)
                        
                        regional_ec2.stop_instances(InstanceIds=[instance_id])
                        
                        message = f'成功停止執行個體 {instance_id} (區域: {region})'
                        logger.info(message)
                        slack_messages.append(message)
                        success_count += 1
                    else:
                        message = f'因 AutoStop 標籤設定而跳過執行個體 {instance_id} (區域: {region})'
                        logger.info(message)
                        slack_messages.append(message)
                        
        except Exception as e:
            error_message = f'處理區域 {region} 時發生錯誤: {str(e)}'
            logger.error(error_message)
            errors.append(error_message)
            slack_messages.append(f':x: {error_message}')

    # Final result reporting
    if errors:
        message = f'執行完成，但發生 {len(errors)} 個錯誤。'
        logger.error(message)
        slack_messages.append(message)
        for error in errors:
            slack_messages.append(f':x: {error}')
    else:
        message = f'執行完成，共停止 {success_count} 個執行個體。'
        logger.info(message)
        slack_messages.append(f':white_check_mark: {message}')

    # Send collected messages to Slack
    full_message = '\n'.join(slack_messages)
    send_to_slack(full_message)

    return {
        'statusCode': 200,
        'body': 'EC2 instances checked and stopped where necessary, check Slack for details.'
    }

