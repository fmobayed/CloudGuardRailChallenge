# SecretCode: fmobayed-2025-FAD

import json
import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SNS_ARN = os.getenv('SNS_TOPIC_ARN', '')

def lambda_handler(event, context):
    """
    Triggered when a CreateQueue event is detected (via CloudTrail -> EventBridge).
    Performs these checks on the newly created SQS queue:
        1. VPC Endpoint Check
        2. Encryption at Rest
        3. Customer-managed KMS Key usage
        4. Required tags: Name, Created By, Cost Center

    If any check fails, the function logs an error and (optionally) publishes
    an SNS alert if SNS_TOPIC_ARN is provided.
    """

    logger.info("Received event: %s", json.dumps(event))
    detail = event.get("detail", {})
    request_params = detail.get("requestParameters", {})
    _ = detail.get("responseElements", {})  # Not always needed, but kept for reference

    # 1. Get the queue name from requestParams
    queue_name = request_params.get("queueName")
    if not queue_name:
        msg = "Queue name not found in event detail."
        send_alert(msg)
        return {"statusCode": 400, "body": msg}

    # 2. Construct the queue URL
    account_id = event.get("account")
    region = event.get("region")
    queue_url = f"https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}"

    # 3. Check if SQS VPC Endpoint exists in this region
    ec2_client = boto3.client("ec2", region_name=region)
    sqs_vpc_endpoints = ec2_client.describe_vpc_endpoints(
        Filters=[
            {"Name": "service-name", "Values": [f"com.amazonaws.{region}.sqs"]}
        ]
    )["VpcEndpoints"]
    if not sqs_vpc_endpoints:
        msg = f"No SQS VPC Endpoint found in region {region}. Security best practice is to use a VPC endpoint."
        send_alert(msg)

    # 4. Check encryption & KMS
    sqs_client = boto3.client("sqs", region_name=region)
    try:
        attrs_resp = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["All"]
        )
        attrs = attrs_resp.get("Attributes", {})
    except Exception as e:
        msg = f"Failed to retrieve attributes for queue {queue_name}: {str(e)}"
        send_alert(msg)
        return {"statusCode": 500, "body": msg}

    kms_key_id = attrs.get("KmsMasterKeyId")
    if not kms_key_id:
        msg = f"Encryption is NOT enabled for queue {queue_name} (no KmsMasterKeyId)."
        send_alert(msg)
    else:
        # Check if it's a customer-managed key vs AWS-managed
        # AWS-managed key for SQS is typically 'alias/aws/sqs'
        if "alias/aws/sqs" in kms_key_id:
            msg = f"Queue {queue_name} uses AWS-managed KMS key instead of a customer-managed key."
            send_alert(msg)

    # 5. Check required tags
    try:
        tags_resp = sqs_client.list_queue_tags(QueueUrl=queue_url)
        tags = tags_resp.get("Tags", {})
    except Exception as e:
        msg = f"Failed to retrieve tags for queue {queue_name}: {str(e)}"
        send_alert(msg)
        return {"statusCode": 500, "body": msg}

    required_tags = ["Name", "Created By", "Cost Center"]
    for t in required_tags:
        if t not in tags:
            msg = f"Queue {queue_name} is missing required tag '{t}'."
            send_alert(msg)

    logger.info(f"All checks complete for queue '{queue_name}'.")
    return {"statusCode": 200, "body": f"Checked queue {queue_name} successfully."}


def send_alert(message):
    """
    Logs an error and optionally publishes to an SNS topic.
    """
    logger.error(message)
    if SNS_ARN:
        sns_client = boto3.client("sns")
        try:
            sns_client.publish(
                TopicArn=SNS_ARN,
                Subject="SQS Guardrail Alert",
                Message=message
            )
        except Exception as e:
            logger.error(f"Failed to publish to SNS: {str(e)}")
