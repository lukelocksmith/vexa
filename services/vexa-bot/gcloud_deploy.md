# Deploying Vexa Bot to Google Cloud

This guide explains how to deploy Vexa Bot to Google Cloud to join a Google Meet meeting.

## Prerequisites

- Google Cloud account with billing enabled
- gcloud CLI installed and configured
- Docker installed
- Access to the vexa-bot source code

## Step 1: Build the Docker Image

1. Navigate to the core directory:
```bash
cd services/vexa-bot/core
```

2. Build the Docker image:
```bash
docker build -t vexa-bot .
```

## Step 2: Push the Image to Google Artifact Registry

1. Tag the image with your Google Cloud project and repository:
```bash
docker tag vexa-bot us-central1-docker.pkg.dev/YOUR_PROJECT_ID/REPOSITORY_NAME/vexa-bot:latest
```

2. Configure Docker to authenticate with Google Cloud:
```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

3. Push the image to Google Artifact Registry:
```bash
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/REPOSITORY_NAME/vexa-bot:latest
```

## Step 3: Create Bot Configuration File

Create a file named `bot_config.json` with your meeting configuration:

```json
{
  "platform": "google_meet",
  "meetingUrl": "https://meet.google.com/YOUR-MEETING-CODE",
  "botName": "Vexa",
  "token": "YOUR_TOKEN",
  "connectionId": "YOUR_CONNECTION_ID",
  "nativeMeetingId": "YOUR_MEETING_CODE",
  "automaticLeave": {
    "waitingRoomTimeout": 300000,
    "noOneJoinedTimeout": 300000,
    "everyoneLeftTimeout": 300000
  }
}
```

## Step 4: Deploy to Google Compute Engine

1. Create a container environment file:
```bash
echo 'BOT_CONFIG={"platform":"google_meet","meetingUrl":"https://meet.google.com/YOUR-MEETING-CODE","botName":"Vexa","token":"YOUR_TOKEN","connectionId":"YOUR_CONNECTION_ID","nativeMeetingId":"YOUR_MEETING_CODE","automaticLeave":{"waitingRoomTimeout":300000,"noOneJoinedTimeout":300000,"everyoneLeftTimeout":300000}}' > container_env.txt
```

2. Deploy a Compute Engine instance with the container:
```bash
gcloud compute instances create-with-container vexa-bot-instance \
  --container-image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/REPOSITORY_NAME/vexa-bot:latest \
  --machine-type=e2-small \
  --zone=us-central1-a \
  --project=YOUR_PROJECT_ID \
  --container-env-file=container_env.txt
```

## Step 5: Grant Permissions to Access Artifact Registry

Get the service account used by the VM:
```bash
gcloud compute instances describe vexa-bot-instance --zone=us-central1-a --format="value(serviceAccounts[0].email)"
```

Grant access to the Artifact Registry:
```bash
gcloud artifacts repositories add-iam-policy-binding REPOSITORY_NAME \
  --location=us-central1 \
  --member=serviceAccount:SERVICE_ACCOUNT_EMAIL \
  --role=roles/artifactregistry.reader
```

## Step 6: Restart the Instance

Reset the instance to apply permissions:
```bash
gcloud compute instances reset vexa-bot-instance --zone=us-central1-a
```

## Step 7: Verify Deployment

Check if the container is running:
```bash
gcloud compute ssh vexa-bot-instance --zone=us-central1-a --command="docker ps"
```

View container logs:
```bash
gcloud compute ssh vexa-bot-instance --zone=us-central1-a --command="docker logs $(docker ps -q)"
```

## Example Deployment Command

Here's a complete example with the Google Meet URL https://meet.google.com/hhs-bkmm-zqg:

```bash
# Create container environment file
echo 'BOT_CONFIG={"platform":"google_meet","meetingUrl":"https://meet.google.com/hhs-bkmm-zqg","botName":"Vexa","token":"test_token","connectionId":"test_connection","nativeMeetingId":"hhs-bkmm-zqg","automaticLeave":{"waitingRoomTimeout":300000,"noOneJoinedTimeout":300000,"everyoneLeftTimeout":300000}}' > container_env.txt

# Deploy VM with container
gcloud compute instances create-with-container vexa-bot-instance \
  --container-image=us-central1-docker.pkg.dev/spry-pipe-425611-c4/cloud-run-source-deploy/vexa-bot:latest \
  --machine-type=e2-small \
  --zone=us-central1-a \
  --project=spry-pipe-425611-c4 \
  --container-env-file=container_env.txt

# Grant permissions to the VM's service account
SERVICE_ACCOUNT=$(gcloud compute instances describe vexa-bot-instance --zone=us-central1-a --format="value(serviceAccounts[0].email)")
gcloud artifacts repositories add-iam-policy-binding cloud-run-source-deploy \
  --location=us-central1 \
  --member=serviceAccount:$SERVICE_ACCOUNT \
  --role=roles/artifactregistry.reader

# Reset the instance
gcloud compute instances reset vexa-bot-instance --zone=us-central1-a
```

## Troubleshooting

### Permission Denied Error
If you see "Permission denied" errors when pulling the container image, make sure you've granted the VM's service account access to the Artifact Registry repository.

### Container Not Starting
Check the container logs for details:
```bash
gcloud compute ssh vexa-bot-instance --zone=us-central1-a --command="docker logs $(docker ps -q)"
```

### Bot Unable to Join Meeting
Make sure your Google Meet URL is valid and accessible without authentication. The bot doesn't support joining meetings that require Google account sign-in. 