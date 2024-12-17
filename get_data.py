import json
import boto3
from datetime import datetime


def find_index(phrases, keywords):
    indices = [i for i, phrase in enumerate(phrases) if any(keyword in phrase for keyword in keywords)]
    return indices


def lambda_handler(event, context):
    try:
        for record in event.get('Records', []):
            # Each record contains the message body and other metadata
            message_body = record.get('body', None)
            message_id = record.get('messageId', None)
            #receipt_handle = record.get('receiptHandle', '')
            if message_body is None or message_id  is None:
                continue

            body_rows = message_body.split('\n')

            # Find indices of key phrases
            keywords = ['Alarm Details:', 'Threshold:', 'Monitored Metric:', 'State Change Actions:']
            index = find_index(body_rows, keywords)

            # Extract relevant details
            alarm_details = body_rows[index[0] + 1 : index[1] - 1]
            monitored_metric = body_rows[index[2] + 1 : index[3] - 1]

            alert_detail = alarm_details + monitored_metric

            # Create a dictionary with the details
            res = {
                _dict[0].replace("-", "").strip(): _dict[1].strip()
                for alarm in alert_detail
                if (len(_dict := alarm.split(':', 1))) > 1
            }

            dt = datetime.strptime(res.get('Timestamp'), '%A %d %B, %Y %H:%M:%S %Z')

            res.update({
                'Timestamp': dt.isoformat(),
            })

            client = boto3.client('lambda')
            client.invoke(FunctionName='TestSnowflakeInsert', InvocationType='Event', Payload=json.dumps(res, indent=2))

        return {
            'statusCode': 200,
            'body': json.dumps(res, indent=2)
        }

    except Exception as e:
        print(str(e))
        return {
            'statusCode': 400,
            'body': json.dumps(str(e))
        }
