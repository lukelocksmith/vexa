.PHONY: all setup submodules env force-env download-model build-bot-image build up down clean ps logs test migrate-check migrate-run migrate-status migrate-history migrate-copy migrate-force migrate-generate

# Default target: Sets up everything and starts the services
all: setup-env build-bot-image build up migrate-check

# Target to set up only the environment without Docker
# Ensure .env is created based on TARGET *before* other setup steps
setup-env: env submodules download-model
	@echo "Environment setup complete."
	@echo "The 'env' target (now called by setup-env) handles .env creation/preservation:"
	@echo "  - If .env exists, it is preserved."
	@echo "  - If .env does not exist, it is created based on the TARGET variable (e.g., 'make setup-env TARGET=gpu')."
	@echo "  - If .env is created and no TARGET is specified, it defaults to 'cpu'."
	@echo "To force an overwrite of an existing .env file, use 'make force-env TARGET=cpu/gpu'."

# Target to perform all initial setup steps
setup: setup-env build-bot-image
	@echo "Setup complete."

# Initialize and update Git submodules
submodules:
	@echo "---> Initializing and updating Git submodules..."
	@git submodule update --init --recursive

# Default bot image tag if not specified in .env
BOT_IMAGE_NAME ?= vexa-bot:dev

# Check if Docker daemon is running
check_docker:
	@echo "---> Checking if Docker is running..."
	@if ! docker info > /dev/null 2>&1; then \
		echo "ERROR: Docker is not running. Please start Docker Desktop or Docker daemon first."; \
		exit 1; \
	fi
	@echo "---> Docker is running."

# === DATABASE MIGRATION TARGETS ===

# Check if database needs migrations and run them if needed
migrate-check:
	@echo "---> Checking database migration status..."
	@if docker compose ps | grep -q "transcription-collector.*Up"; then \
		echo "---> Transcription collector is running, checking migrations..."; \
		if docker compose exec -T transcription-collector bash -c "cd /app && alembic current" 2>/dev/null | grep -q "(head)"; then \
			echo "✅ Database is up to date - no migrations needed."; \
		else \
			echo "🔄 Database needs migrations. Running them now..."; \
			$(MAKE) migrate-run; \
		fi; \
	else \
		echo "⚠️  Transcription collector not running. Start services first with 'make up'."; \
	fi

# Run pending database migrations
migrate-run:
	@echo "---> Applying database migrations..."
	@if docker compose ps | grep -q "transcription-collector.*Up"; then \
		echo "---> Copying alembic files to container..."; \
		docker cp libs/shared-models/alembic.ini $$(docker compose ps -q transcription-collector):/app/ 2>/dev/null || true; \
		docker cp libs/shared-models/alembic $$(docker compose ps -q transcription-collector):/app/ 2>/dev/null || true; \
		echo "---> Running alembic upgrade..."; \
		if docker compose exec -T transcription-collector bash -c "cd /app && alembic upgrade head"; then \
			echo "✅ Database migrations completed successfully!"; \
			$(MAKE) migrate-copy; \
		else \
			echo "❌ Migration failed. Please check the logs and database state."; \
			exit 1; \
		fi; \
	else \
		echo "❌ Transcription collector not running. Start services first with 'make up'."; \
		exit 1; \
	fi

# Force run migrations (useful for development)
migrate-force:
	@echo "---> Force running database migrations..."
	@if docker compose ps | grep -q "transcription-collector.*Up"; then \
		echo "---> Copying alembic files to container..."; \
		docker cp libs/shared-models/alembic.ini $$(docker compose ps -q transcription-collector):/app/; \
		docker cp libs/shared-models/alembic $$(docker compose ps -q transcription-collector):/app/; \
		echo "---> Running alembic upgrade..."; \
		docker compose exec -T transcription-collector bash -c "cd /app && alembic upgrade head"; \
		$(MAKE) migrate-copy; \
	else \
		echo "❌ Transcription collector not running. Start services first with 'make up'."; \
		exit 1; \
	fi

# Show current migration status
migrate-status:
	@echo "---> Checking current migration status..."
	@if docker compose ps | grep -q "transcription-collector.*Up"; then \
		docker cp libs/shared-models/alembic.ini $$(docker compose ps -q transcription-collector):/app/ 2>/dev/null || true; \
		docker cp libs/shared-models/alembic $$(docker compose ps -q transcription-collector):/app/ 2>/dev/null || true; \
		echo "---> Current migration:"; \
		docker compose exec -T transcription-collector bash -c "cd /app && alembic current"; \
		echo "---> Available migrations:"; \
		docker compose exec -T transcription-collector bash -c "cd /app && alembic show head"; \
	else \
		echo "❌ Transcription collector not running. Start services first with 'make up'."; \
		exit 1; \
	fi

# Show migration history
migrate-history:
	@echo "---> Showing migration history..."
	@if docker compose ps | grep -q "transcription-collector.*Up"; then \
		docker cp libs/shared-models/alembic.ini $$(docker compose ps -q transcription-collector):/app/ 2>/dev/null || true; \
		docker cp libs/shared-models/alembic $$(docker compose ps -q transcription-collector):/app/ 2>/dev/null || true; \
		docker compose exec -T transcription-collector bash -c "cd /app && alembic history"; \
	else \
		echo "❌ Transcription collector not running. Start services first with 'make up'."; \
		exit 1; \
	fi

# Generate a new migration
migrate-generate:
	@echo "---> Generating new migration..."
	@if [ -z "$(MSG)" ]; then \
		echo "❌ Please provide a migration message. Usage: make migrate-generate MSG='Your migration description'"; \
		exit 1; \
	fi
	@if docker compose ps | grep -q "transcription-collector.*Up"; then \
		echo "---> Copying alembic files to container..."; \
		docker cp libs/shared-models/alembic.ini $$(docker compose ps -q transcription-collector):/app/; \
		docker cp libs/shared-models/alembic $$(docker compose ps -q transcription-collector):/app/; \
		echo "---> Generating migration: $(MSG)"; \
		docker compose exec -T transcription-collector bash -c "cd /app && alembic revision --autogenerate -m '$(MSG)'"; \
		$(MAKE) migrate-copy; \
		echo "✅ Migration generated! Remember to review the generated file."; \
	else \
		echo "❌ Transcription collector not running. Start services first with 'make up'."; \
		exit 1; \
	fi

# Copy migration files from container back to host
migrate-copy:
	@echo "---> Copying migration files from container to host..."
	@if docker compose ps | grep -q "transcription-collector.*Up"; then \
		CONTAINER_ID=$$(docker compose ps -q transcription-collector); \
		if [ -n "$$CONTAINER_ID" ]; then \
			echo "---> Copying alembic files from container..."; \
			docker cp $$CONTAINER_ID:/app/alembic/versions/. libs/shared-models/alembic/versions/ 2>/dev/null || echo "No new migration files to copy."; \
			echo "✅ Migration files synchronized."; \
		else \
			echo "❌ Could not find transcription collector container."; \
		fi; \
	else \
		echo "⚠️  Transcription collector not running. No files to copy."; \
	fi

# === END MIGRATION TARGETS ===

# Include .env file if it exists for environment variables 
-include .env

# Create .env file from example
env:
ifndef TARGET
	$(info TARGET not set. Defaulting to cpu. Use 'make env TARGET=cpu' or 'make env TARGET=gpu')
	$(eval TARGET := cpu)
endif
	@echo "---> Checking .env file for TARGET=$(TARGET)..."
	@if [ -f .env ]; then \
		echo "*** .env file already exists. Keeping existing file. ***"; \
		echo "*** To force recreation, delete .env first or use 'make force-env TARGET=$(TARGET)'. ***"; \
	elif [ "$(TARGET)" = "cpu" ]; then \
		if [ ! -f env-example.cpu ]; then \
			echo "env-example.cpu not found. Creating default one."; \
			echo "ADMIN_API_TOKEN=token" > env-example.cpu; \
			echo "LANGUAGE_DETECTION_SEGMENTS=10" >> env-example.cpu; \
			echo "VAD_FILTER_THRESHOLD=0.5" >> env-example.cpu; \
			echo "WHISPER_MODEL_SIZE=tiny" >> env-example.cpu; \
			echo "DEVICE_TYPE=cpu" >> env-example.cpu; \
			echo "BOT_IMAGE_NAME=vexa-bot:dev" >> env-example.cpu; \
			echo "# Exposed Host Ports" >> env-example.cpu; \
			echo "API_GATEWAY_HOST_PORT=8056" >> env-example.cpu; \
			echo "ADMIN_API_HOST_PORT=8057" >> env-example.cpu; \
			echo "TRAEFIK_WEB_HOST_PORT=9090" >> env-example.cpu; \
			echo "TRAEFIK_DASHBOARD_HOST_PORT=8085" >> env-example.cpu; \
			echo "TRANSCRIPTION_COLLECTOR_HOST_PORT=8123" >> env-example.cpu; \
			echo "POSTGRES_HOST_PORT=5438" >> env-example.cpu; \
		fi; \
		cp env-example.cpu .env; \
		echo "*** .env file created from env-example.cpu. Please review it. ***"; \
	elif [ "$(TARGET)" = "gpu" ]; then \
		if [ ! -f env-example.gpu ]; then \
			echo "env-example.gpu not found. Creating default one."; \
			echo "ADMIN_API_TOKEN=token" > env-example.gpu; \
			echo "LANGUAGE_DETECTION_SEGMENTS=10" >> env-example.gpu; \
			echo "VAD_FILTER_THRESHOLD=0.5" >> env-example.gpu; \
			echo "WHISPER_MODEL_SIZE=medium" >> env-example.gpu; \
			echo "DEVICE_TYPE=cuda" >> env-example.gpu; \
			echo "BOT_IMAGE_NAME=vexa-bot:dev" >> env-example.gpu; \
			echo "# Exposed Host Ports" >> env-example.gpu; \
			echo "API_GATEWAY_HOST_PORT=8056" >> env-example.gpu; \
			echo "ADMIN_API_HOST_PORT=8057" >> env-example.gpu; \
			echo "TRAEFIK_WEB_HOST_PORT=9090" >> env-example.gpu; \
			echo "TRAEFIK_DASHBOARD_HOST_PORT=8085" >> env-example.gpu; \
			echo "TRANSCRIPTION_COLLECTOR_HOST_PORT=8123" >> env-example.gpu; \
			echo "POSTGRES_HOST_PORT=5438" >> env-example.gpu; \
		fi; \
		cp env-example.gpu .env; \
		echo "*** .env file created from env-example.gpu. Please review it. ***"; \
	else \
		echo "Error: TARGET must be 'cpu' or 'gpu'. Usage: make env TARGET=<cpu|gpu>"; \
		exit 1; \
	fi

# Force create .env file from example (overwrite existing)
force-env:
ifndef TARGET
	$(info TARGET not set. Defaulting to cpu. Use 'make force-env TARGET=cpu' or 'make force-env TARGET=gpu')
	$(eval TARGET := cpu)
endif
	@echo "---> Creating .env file for TARGET=$(TARGET) (forcing overwrite)..."
	@if [ "$(TARGET)" = "cpu" ]; then \
		if [ ! -f env-example.cpu ]; then \
			echo "env-example.cpu not found. Creating default one."; \
			echo "ADMIN_API_TOKEN=token" > env-example.cpu; \
			echo "LANGUAGE_DETECTION_SEGMENTS=10" >> env-example.cpu; \
			echo "VAD_FILTER_THRESHOLD=0.5" >> env-example.cpu; \
			echo "WHISPER_MODEL_SIZE=tiny" >> env-example.cpu; \
			echo "DEVICE_TYPE=cpu" >> env-example.cpu; \
			echo "BOT_IMAGE_NAME=vexa-bot:dev" >> env-example.cpu; \
			echo "# Exposed Host Ports" >> env-example.cpu; \
			echo "API_GATEWAY_HOST_PORT=8056" >> env-example.cpu; \
			echo "ADMIN_API_HOST_PORT=8057" >> env-example.cpu; \
			echo "TRAEFIK_WEB_HOST_PORT=9090" >> env-example.cpu; \
			echo "TRAEFIK_DASHBOARD_HOST_PORT=8085" >> env-example.cpu; \
			echo "TRANSCRIPTION_COLLECTOR_HOST_PORT=8123" >> env-example.cpu; \
			echo "POSTGRES_HOST_PORT=5438" >> env-example.cpu; \
		fi; \
		cp env-example.cpu .env; \
		echo "*** .env file created from env-example.cpu. Please review it. ***"; \
	elif [ "$(TARGET)" = "gpu" ]; then \
		if [ ! -f env-example.gpu ]; then \
			echo "env-example.gpu not found. Creating default one."; \
			echo "ADMIN_API_TOKEN=token" > env-example.gpu; \
			echo "LANGUAGE_DETECTION_SEGMENTS=10" >> env-example.gpu; \
			echo "VAD_FILTER_THRESHOLD=0.5" >> env-example.gpu; \
			echo "WHISPER_MODEL_SIZE=medium" >> env-example.gpu; \
			echo "DEVICE_TYPE=cuda" >> env-example.gpu; \
			echo "BOT_IMAGE_NAME=vexa-bot:dev" >> env-example.gpu; \
			echo "# Exposed Host Ports" >> env-example.gpu; \
			echo "API_GATEWAY_HOST_PORT=8056" >> env-example.gpu; \
			echo "ADMIN_API_HOST_PORT=8057" >> env-example.gpu; \
			echo "TRAEFIK_WEB_HOST_PORT=9090" >> env-example.gpu; \
			echo "TRAEFIK_DASHBOARD_HOST_PORT=8085" >> env-example.gpu; \
			echo "TRANSCRIPTION_COLLECTOR_HOST_PORT=8123" >> env-example.gpu; \
			echo "POSTGRES_HOST_PORT=5438" >> env-example.gpu; \
		fi; \
		cp env-example.gpu .env; \
		echo "*** .env file created from env-example.gpu. Please review it. ***"; \
	else \
		echo "Error: TARGET must be 'cpu' or 'gpu'. Usage: make force-env TARGET=<cpu|gpu>"; \
		exit 1; \
	fi

# Download the Whisper model
download-model:
	@echo "---> Creating ./hub directory if it doesn't exist..."
	@mkdir -p ./hub
	@echo "---> Ensuring ./hub directory is writable..."
	@chmod u+w ./hub
	@echo "---> Downloading Whisper model (this may take a while)..."
	@python download_model.py

# Build the standalone vexa-bot image
# Uses BOT_IMAGE_NAME from .env if available, otherwise falls back to default
build-bot-image: check_docker
	@if [ -f .env ]; then \
		ENV_BOT_IMAGE_NAME=$$(grep BOT_IMAGE_NAME .env | cut -d= -f2); \
		if [ -n "$$ENV_BOT_IMAGE_NAME" ]; then \
			echo "---> Building $$ENV_BOT_IMAGE_NAME image (from .env)..."; \
			docker build -t $$ENV_BOT_IMAGE_NAME -f services/vexa-bot/core/Dockerfile ./services/vexa-bot/core; \
		else \
			echo "---> Building $(BOT_IMAGE_NAME) image (BOT_IMAGE_NAME not found in .env)..."; \
			docker build -t $(BOT_IMAGE_NAME) -f services/vexa-bot/core/Dockerfile ./services/vexa-bot/core; \
		fi; \
	else \
		echo "---> Building $(BOT_IMAGE_NAME) image (.env file not found)..."; \
		docker build -t $(BOT_IMAGE_NAME) -f services/vexa-bot/core/Dockerfile ./services/vexa-bot/core; \
	fi

# Build Docker Compose service images
build: check_docker
	@echo "---> Building Docker Compose services..."
	@if [ "$(TARGET)" = "cpu" ]; then \
		echo "---> Building with 'cpu' profile (includes whisperlive-cpu)..."; \
		docker compose --profile cpu build; \
	elif [ "$(TARGET)" = "gpu" ]; then \
		echo "---> Building with 'gpu' profile (includes whisperlive GPU)..."; \
		docker compose --profile gpu build; \
	else \
		echo "---> TARGET not explicitly set, defaulting to CPU mode. 'whisperlive' (GPU) will not be built."; \
		docker compose --profile cpu build; \
	fi

# Start services in detached mode
up: check_docker
	@echo "---> Starting Docker Compose services..."
	@if [ "$(TARGET)" = "cpu" ]; then \
		echo "---> Activating 'cpu' profile to start whisperlive-cpu along with other services..."; \
		docker compose --profile cpu up -d; \
	elif [ "$(TARGET)" = "gpu" ]; then \
		echo "---> Starting services for GPU. This will start 'whisperlive' (for GPU) and other default services. 'whisperlive-cpu' (profile=cpu) will not be started."; \
		docker compose --profile gpu up -d; \
	else \
		echo "---> TARGET not explicitly set, defaulting to CPU mode. 'whisperlive' (GPU) will not be started."; \
		docker compose --profile cpu up -d; \
	fi
	@echo "---> Waiting for services to start..."
	@sleep 5
	@echo "---> Services started. Run 'make migrate-check' to verify database migrations."

# Stop services
down: check_docker
	@echo "---> Stopping Docker Compose services..."
	@if [ "$(TARGET)" = "cpu" ]; then \
		echo "---> Stopping services with 'cpu' profile (including whisperlive-cpu)..."; \
		docker compose --profile cpu down; \
	elif [ "$(TARGET)" = "gpu" ]; then \
		echo "---> Stopping services with 'gpu' profile (including whisperlive GPU)..."; \
		docker compose --profile gpu down; \
	else \
		echo "---> TARGET not specified, stopping all services regardless of profile..."; \
		docker compose down; \
	fi

# Stop services and remove volumes
clean: check_docker
	@echo "---> WARNING: This will stop services AND REMOVE ALL VOLUMES (including database data)!"
	@echo "---> This action is IRREVERSIBLE and will delete all persistent data."
	@read -p "Are you sure you want to continue? (y/N): " confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		echo "Operation cancelled."; \
		exit 0; \
	fi
	@echo "---> Stopping Docker Compose services and removing volumes..."
	@if [ "$(TARGET)" = "cpu" ]; then \
		echo "---> Stopping services with 'cpu' profile (including whisperlive-cpu) and removing volumes..."; \
		docker compose --profile cpu down -v; \
	elif [ "$(TARGET)" = "gpu" ]; then \
		echo "---> Stopping services with 'gpu' profile (including whisperlive GPU) and removing volumes..."; \
		docker compose --profile gpu down -v; \
	else \
		echo "---> TARGET not specified, stopping all services regardless of profile and removing volumes..."; \
		docker compose down -v; \
	fi

# Show container status
ps: check_docker
	@docker compose ps

# Tail logs for all services
logs:
	@docker compose logs -f

# Run the interaction test script
test: check_docker
	@echo "---> Running test script..."
	@echo "---> API Documentation URLs:"
	@if [ -f .env ]; then \
		API_PORT=$$(grep -E '^[[:space:]]*API_GATEWAY_HOST_PORT=' .env | cut -d= -f2- | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$$//'); \
		ADMIN_PORT=$$(grep -E '^[[:space:]]*ADMIN_API_HOST_PORT=' .env | cut -d= -f2- | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$$//'); \
		[ -z "$$API_PORT" ] && API_PORT=8056; \
		[ -z "$$ADMIN_PORT" ] && ADMIN_PORT=8057; \
		echo "    Main API:  http://localhost:$$API_PORT/docs"; \
		echo "    Admin API: http://localhost:$$ADMIN_PORT/docs"; \
	else \
		echo "    Main API:  http://localhost:8056/docs"; \
		echo "    Admin API: http://localhost:8057/docs"; \
	fi
	@chmod +x run_vexa_interaction.sh
	@./run_vexa_interaction.sh
