# Hot Dev Kit (local to vexa-bot)
IMAGE_NAME ?= vexa-bot:test
MEETING_URL ?=
DOCKER_NETWORK ?= vexa_dev_vexa_default
HOT_CHANNEL := bot_commands:meeting:999
ZOOM_WEBHOOK_FILE ?=
ZOOM_RTMS_DETAILS ?=

.PHONY: build rebuild test test-zoom capture-webhook publish publish-leave publish-rtms-config

# Build image + create local dist/ (one-time setup)
build:
	@echo "Building Docker image..."
	@docker build -t $(IMAGE_NAME) -f core/Dockerfile core
	@echo "Creating local dist/ for hot-reload..."
	@docker run --rm -v "$$(pwd)/core:/app" -w /app node:18 sh -c "npm install && npm run build"
	@echo "✅ Ready! Run: make test MEETING_URL=... or make test-zoom"

# Rebuild dist/ when you edit code (fast, uses Docker)
rebuild:
	@docker run --rm -v "$$(pwd)/core:/app" -w /app node:18 sh -c "npm install && npm run build"
	@echo "✅ dist/ rebuilt. Restart bot to pick up changes."

# Usage: make test MEETING_URL='https://teams.live.com/meet/...'
test:
	@[ -n "$(MEETING_URL)" ] || (echo "MEETING_URL is required" && exit 1)
	@cd core/src/platforms && ./hot-debug.sh $(MEETING_URL)

# Capture Zoom RTMS webhook event
# Usage: make capture-webhook [ZOOM_WEBHOOK_FILE=path/to/webhook.json]
capture-webhook:
	@cd core/src/platforms/zoom && ./capture-webhook.sh $(ZOOM_WEBHOOK_FILE)

# Test Zoom bot with RTMS details from captured webhook
# Usage: make test-zoom [ZOOM_RTMS_DETAILS=path/to/rtms-details.json]
test-zoom:
	@cd core/src/platforms && ./hot-debug.sh zoom $(ZOOM_RTMS_DETAILS)

# Usage: make publish DATA='{"action":"leave"}' (CHANNEL optional)
publish:
	@[ -n "$(DATA)" ] || (echo "DATA is required" && exit 1)
	docker run --rm --network $(DOCKER_NETWORK) redis:alpine \
	  redis-cli -h redis -p 6379 PUBLISH $${CHANNEL:-$(HOT_CHANNEL)} '$(DATA)'

# Usage: make publish-leave
publish-leave:
	@$(MAKE) publish DATA='{"action":"leave"}'

# Publish RTMS config update to bot (for testing webhook flow)
# Usage: make publish-rtms-config RTMS_STREAM_ID=... SERVER_URLS=... MEETING_UUID=...
publish-rtms-config:
	@[ -n "$(RTMS_STREAM_ID)" ] || (echo "RTMS_STREAM_ID is required" && exit 1)
	@[ -n "$(SERVER_URLS)" ] || (echo "SERVER_URLS is required" && exit 1)
	@[ -n "$(MEETING_UUID)" ] || (echo "MEETING_UUID is required" && exit 1)
	@$(MAKE) publish DATA='{"action":"update_rtms_config","meeting_id":999,"rtms_config":{"zoomRtmsStreamId":"$(RTMS_STREAM_ID)","zoomServerUrls":"$(SERVER_URLS)","nativeMeetingId":"$(MEETING_UUID)"}}'

