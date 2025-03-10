CloudGuardRailChallenge

This repository provides an enterprise-grade guardrail solution for newly created Amazon SQS queues. It enforces security best practices, checks encryption, tagging, and usage of a VPC endpoint, and optionally alerts via SNS. It also  enables a Control Tower guardrail requiring SQS dead-letter queues. 

Overview

    AWS SAM (Serverless Application Model) Template
        Uses the Transform: AWS::Serverless-2016-10-31 directive.
        Declares a AWS::Serverless::Function for the Lambda, an IAM Role, and an EventBridge Rule to invoke the Lambda upon CreateQueue calls.
    Python Lambda:
        Verifies new SQS queues have encryption with a customer-managed KMS key, have required tags, and logs/publishes SNS alerts if checks fail.
    IAM Role with a Permission Boundary:
        Restricts the Lambda’s maximum privileges, ensuring tight security in multi-account environments.
    Optionally add a Control Tower guardrail requiring SQS to have a dead-letter queue in your chosen region. (Commented out in the template, but can be uncommented.)

Architecture

    CreateQueue calls are detected by CloudTrail.
    EventBridge (with a rule filtering CreateQueue events) invokes the Lambda.
    The Lambda checks:
        VPC endpoint presence for SQS.
        Queue encryption (KMS).
        Customer-managed key usage (not alias/aws/sqs).
        Required tags: Name, Created By, Cost Center.
        Logs errors or optionally sends an alert to SNS if any check fails.

Prerequisites

Before setting up the workflow, ensure you have:

1. AWS Account with permissions to create IAM roles, Lambda functions, and a Control Tower enrollment to enable the guardrail on the account level. 
2. S3 Bucket for packaging code and uploading to it through the pipeline process. E.g., my-lambda-artifacts.
3. Permission Boundary Policy (optional if your org requires it) – an IAM managed policy that you’ll reference via the PermissionBoundaryArn parameter.
4. (Optional) SNS Topic ARN if you want to receive alerts.
5. Create AWS Secrets & Variables in GitHub.

File Structure

    CloudGuardRailChallenge/
    ├── README.md                  # This file
    ├── template.yaml              # AWS SAM template (with "Transform: AWS::Serverless-2016-10-31")
    └── .github/
        └── workflows/deploy.yml
    └── lambda_function/
        └── lambda_function.py     # Python code for the guardrail checks    

Set Up AWS Credentials in GitHub
1. Using IAM Role with OpenID Connect (OIDC)
    Create an IAM Role for GitHub Actions:
     IAM Trust Policy should allow GitHub OIDC:

        {
        "Version": "2012-10-17",
        "Statement": [
            {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringLike": {
                "token.actions.githubusercontent.com:sub": "repo:<GitHub_Org>/<Repo_Name>:ref:refs/heads/main"
                }
            }
            }
        ]
        }

Attach a Policy allowing CloudFormation, Lambda, S3, IAM, and EventBridge actions.

Save the IAM Role ARN and add it to GitHub as a secret:

    ROLE_TO_ASSUME → IAM Role ARN (e.g., arn:aws:iam::123456789012:role/GitHubDeployRole).

Set Up Repository Variables and secrets

In GitHub Actions → Variables, and secrets for sensitive values

    CFN_S3_BUCKET - S3 bucket for storing Lambda package
    CFN_S3_KEY - Path to store Lambda zip in S3	
    CFN_STACK_NAME - Name of CloudFormation stack
    CFN_RUNTIME - Lambda runtime python3.9
    CFN_MEMORY - Memory allocated to Lambda (MB) 256
    PERMISSION_BOUNDARY_ARN - ARN of IAM permission boundary (if applicable)
    CONTROL_TOWER_OU_ARN - ARN of Organizational Unit (if using Control Tower)
    OPTIONAL_SNS_TOPIC_ARN - ARN of the SNS TOPIC for Alerting
    ROLE_TO_ASSUME - IAM ROLE ARN for OIDC

Deployment Instructions

Using GitHub Actions (CI/CD)

1. Make updates to the files and Push your code (including template.yaml and lambda_function/).
2. The github actions wokflorw will be triggered (.github/workflows/deploy.yml)
3. Once your workflow completes, the function is deployed.

Verify the Deployment
A) Check CloudFormation Stack

    Go to AWS Console → CloudFormation → Check the SQSGuardrailStack stack.
    Ensure all resources are successfully created.

B) Check Lambda Logs

    AWS Console → CloudWatch Logs → /aws/lambda/SQSGuardrailFunction-<stackname>.
    Look for logs confirming the function was invoked on SQS CreateQueue events.

C) Manually Trigger a Test Event

Run this command in AWS CLI to create an SQS queue:

    aws sqs create-queue --queue-name TestQueue

If successful, EventBridge should trigger the Lambda function.
Check CloudWatch Logs to confirm the function ran.
Alternatively, You can create a test SQS Queue through AWS Console.        

Design Decisions

    AWS SAM: Simplifies packaging the Lambda code. CodeUri property ensures your local code is zipped and uploaded automatically if you use sam package.
    Permission Boundary: Constrains the Lambda role’s maximum privileges. You can pass the boundary ARN as a parameter for multi-environment support.
    EventBridge / CloudTrail: Catches CreateQueue calls across your accounts.
    SNS Alerts (Optional): If an ARN is provided, the Lambda will publish a message if checks fail. Otherwise it just logs the errors. 
    Control Tower: Native approach to require SQS DLQs, more robust than just a code check.

Troubleshooting

    Credentials Error: If you see Could not load credentials, ensure you either configured an OIDC with a role-to-assume.
    OU Not Registered: If you enable the Control Tower guardrail but your OU isn’t fully enrolled in that region, you’ll get an error. Register the OU in that region first.

Extending the Solution

    Tag Enforcement: Add more required tags or logic if needed.
    Encryption Enhancements: Check key rotation, enforce KMS alias naming conventions, etc.
    Multi-Region: Deploy across multiple regions or replicate the guardrail in each desired region.
    CI/CD: Add advanced GitHub Action steps to validate, test, and deploy multiple stacks (dev, stage, prod).
    Use Vaults in AWS such as secrets manager for storing sensitive data instead of github. 