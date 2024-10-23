import json
import snowflake.connector
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_secret() -> dict:
    secret_name = "dev/journal_events/SF_cred"
    region_name = "us-east-1"
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    return json.loads(get_secret_value_response['SecretString'])

    # Your code goes here.


def lambda_handler(event, context):
    reason = event.get('Reason for State Change')
    dimensions = event.get('Dimensions').split('=')

    event.update({
        'State Change': event.get('State Change', '').split('>')[1].strip(),
        'Aws region': event.get('Alarm Arn', '').split(':')[3],
        'Tool': event.get('MetricNamespace').split('/')[-1],
        'Threshold crossed': reason[reason.index('[') + 1:reason.index(' (')],
        'Threshold': reason[reason.rindex('(') + 1:reason.rindex(')')],
        'dimension_name': dimensions[0][1:].strip(),
        'dimension_value': dimensions[1][:-1].strip(),
    })

    try:
        logger.info('getting credentials')
        credentials = get_secret()

    except Exception as e:

        logger.error(f'An error getting credentials: {str(e)}')
        return {
            'statusCode': 400,
            'body': json.dumps(str(e))
        }

    status_return_code = 200
    reponse_message = 'Successful'

    try:
        logger.info("Attempting to connect to Snowflake")

        conn = snowflake.connector.connect(**credentials)

        logger.info("connection established")
        cur = conn.cursor()

        logger.info('inserting data')

        cur.execute_async("""
                INSERT INTO TEST
                SELECT
                    %(Name)s, %(Description)s, %(State Change)s, %(Threshold crossed)s, %(Threshold)s, %(Timestamp)s,
                    %(AWS Account)s, %(Alarm Arn)s, %(Aws region)s, %(MetricNamespace)s, %(MetricName)s, %(dimension_name)s,
                    %(dimension_value)s, %(Tool)s, PARSE_JSON(%(raw)s)
            """, {**event, 'raw': json.dumps(event)})
        logger.info("Data inserted successfully")


    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        conn.rollback()
        status_return_code = 400
        reponse_message = e

    finally:
        cur.close()
        conn.close()
        logger.info("connection closed")
        return {
            'statusCode': status_return_code,
            'body': reponse_message
        }
