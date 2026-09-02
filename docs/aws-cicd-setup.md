# AWS production CI/CD setup

The production workflow uses GitHub's OpenID Connect (OIDC) identity and AWS
Systems Manager (SSM). It does not require an AWS access key or EC2 private key
in GitHub.

## 1. Make the EC2 instance manageable with SSM

In IAM, create a role for the EC2 use case and attach the AWS-managed policy
`AmazonSSMManagedInstanceCore`. Attach that role to the production instance from
EC2 **Actions > Security > Modify IAM role**.

The instance must have the SSM Agent installed and running:

```bash
sudo systemctl status amazon-ssm-agent --no-pager
```

If the service is not installed, follow the AWS SSM Agent installation guide for
the instance's Ubuntu version. Confirm the instance appears as a managed node in
Systems Manager before continuing.

## 2. Add GitHub as an IAM identity provider

Create an IAM OpenID Connect provider with:

- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

Skip this step if the account already has that provider.

## 3. Create the GitHub deployment role

Create an IAM role with this trust policy. The subject restriction means only the
`production` environment in this repository can assume it.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::919651863327:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:nitashaf/TransferATS:environment:production"
        }
      }
    }
  ]
}
```

Attach this least-privilege permissions policy to the role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SendDeploymentCommand",
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ec2:us-east-2:919651863327:instance/i-0a03231cc61e2163d",
        "arn:aws:ssm:us-east-2::document/AWS-RunShellScript"
      ]
    },
    {
      "Sid": "ReadDeploymentResult",
      "Effect": "Allow",
      "Action": "ssm:GetCommandInvocation",
      "Resource": "*"
    }
  ]
}
```

## 4. Configure the GitHub production environment

In the GitHub repository, open **Settings > Environments**, create an environment
named `production`, and add this environment variable:

- `AWS_DEPLOY_ROLE_ARN`: the ARN of the GitHub deployment role

Adding a required reviewer is recommended so production releases require an
explicit approval.

## 5. Clean the production worktree

Deployment stops when tracked production files have uncommitted modifications.
Review and preserve those changes in Git before running the workflow:

```bash
cd /home/ubuntu/TransferATS
git status --short
git diff -- frontend/package-lock.json frontend/src/App.jsx requirements.txt
```

Do not discard these edits until they have been compared with the repository and
either committed or intentionally archived.

## 6. First deployment

Merge the workflow files to `main`. CI runs first; a successful CI run triggers
the production deployment. It can also be started manually from GitHub's Actions
page. The workflow builds the frontend, restarts `transferats.service`, reloads
Nginx, and checks both the local backend and public health endpoints.
