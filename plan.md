Okay, let's summarize the current paradigm for scaling WhisperLive and the detailed plan we're implementing in Phase 2 (Local Docker Compose Setup).

**Current Paradigm & Strategy:**

1.  **Scaling Model:** We are implementing **horizontal scaling** by running multiple, independent instances of the WhisperLive server.
2.  **Load Balancing:** An external load balancer (Nginx within Docker Compose for now, transitioning to a Kubernetes Service/Ingress in production) sits in front of these instances. Its role is to distribute incoming client WebSocket connections across the available WhisperLive server replicas.
3.  **State Handling:**
    *   We acknowledge that each WhisperLive server instance might hold some temporary state related to an active connection (e.g., VAD state, last segments for context).
    *   However, we've determined that the *critical, long-term state* (meeting identity, user context, full collected transcript) resides *outside* the individual WhisperLive instance (handled by the connecting bot and the central Vexa `transcription-collector` service/API).
    *   Therefore, the standard requirement for "sticky sessions" (pinning a client to one specific backend instance for its entire lifetime) is relaxed.
    *   If a WhisperLive instance fails or restarts, the load balancer will direct a reconnecting client (assuming the client/bot handles reconnection) to a *different*, healthy instance. This is acceptable because the essential context travels with the bot's requests or is retrieved from the central collector. A brief interruption or potential loss of a few seconds of in-flight audio during reconnection is deemed an acceptable trade-off for simplified scaling.
4.  **Technology Stack:**
    *   **Local Development/Testing (Phase 2):** Docker Compose orchestrates all services, including multiple WhisperLive replicas, the Nginx load balancer, and a dedicated load testing client.
    *   **Production (Phase 3 Target):** Kubernetes will manage the deployment, scaling, and load balancing of the containerized WhisperLive service. The Docker image built now serves as the deployable unit.

**Detailed Plan Implementation (Phase 2 - Docker Compose):**

1.  **`docker-compose.yml` Configuration:**
    *   **`whisperlive` Service:**
        *   Uses your existing build configuration (`context: .`, `dockerfile: services/WhisperLive/Dockerfile.project`).
        *   Maintains existing `volumes` for model caching (`./hub`, `./services/WhisperLive/models`).
        *   Kept the original `command` to start the server (listening internally on port 9090).
        *   **Scaled:** Added a `deploy` section with `replicas: 3` to run three instances.
        *   **GPU Resources:** Configured under `deploy.resources` to allocate GPU access (`count: all`).
        *   **Networking:** Added to the new `whispernet` (for load balancer access) while keeping it on `vexa_default` (for potential internal communication like with `transcription-collector`, although the direct WebSocket URL in the environment suggests the *client* might be sending data there, not this service directly).
        *   **Ports:** Removed direct host port mapping (`ports: ["9090:9090"]`) as Nginx now handles external access.
    *   **`load-balancer` Service:**
        *   Runs the official `nginx:latest` image.
        *   Maps host port `9090` to its internal port `80`.
        *   Mounts the custom `./nginx.conf` file.
        *   Connects only to the `whispernet` network.
        *   Depends on the `whisperlive` service being started.
    *   **`load-tester` Service:**
        *   **Custom Image:** Built using `context: .` and `dockerfile: load-tester/Dockerfile`. This image includes Python 3.10, `ffmpeg`, `libsndfile1`, and Python dependencies (`websockets`, `numpy`, `soundfile`).
        *   **Volumes:** Mounts the host `./load_test_client.py` and `./test_audio` directory into `/app/` inside the container.
        *   **Command:** Runs `sleep infinity` as dependencies are installed in the image.
        *   **Networking:** Connects only to the `whispernet` network.
        *   Depends on the `load-balancer` service.
    *   **Existing Services:** Your other Vexa services (`api-gateway`, `admin-api`, `bot-manager`, `transcription-collector`, `redis`, `postgres`) remain defined as they were, using the `vexa_default` network.
    *   **Networks:** Defines both `vexa_default` (for original services) and `whispernet` (for the WhisperLive cluster + LB + tester).

2.  **`nginx.conf`:**
    *   Configures Nginx with an `upstream` block named `whisperlive_backend`.
    *   Uses Docker Compose's service discovery by referencing `server whisperlive:9090;` within the upstream block. Nginx will resolve `whisperlive` to the IPs of the running replicas.
    *   Listens on port 80 (internally).
    *   Proxies requests (`proxy_pass http://whisperlive_backend;`) and includes necessary headers (`Upgrade`, `Connection`) to correctly handle WebSocket traffic.

3.  **`load-tester/Dockerfile`:**
    *   Starts from `python:3.10-slim`.
    *   Installs `ffmpeg` and `libsndfile1` via `apt-get`.
    *   Copies `load-tester/requirements.txt` (relative to build context `.`) and installs Python packages via `pip`.
    *   Copies `load_test_client.py` and the `test_audio` directory (relative to build context `.`) into the image (though the volume mount will override the directory contents at runtime).
    *   Sets the default command to `sleep infinity`.

4.  **`load-tester/requirements.txt`:**
    *   Lists `websockets`, `numpy`, `soundfile`.

5.  **`load_test_client.py`:**
    *   An asyncio-based Python script.
    *   Takes arguments (`--num-clients`, `--host`, `--port`, `--audio-dir`).
    *   Connects (`args.num_clients`) concurrent WebSocket clients to the specified host/port (`load-balancer:80` by default).
    *   Randomly selects `.wav` files from the audio directory.
    *   Streams audio data in chunks, simulating real-time pacing.
    *   Includes basic error handling and summary reporting.
    *   Listens for incoming messages but primarily focuses on the sending/connection aspect for load generation.

6.  **`test_audio` Directory:**
    *   A directory (`/home/dima/vexa/test_audio`) intended to hold sample `.wav` files.
    *   **Crucially:** Currently contains invalid or unreadable audio files based on `ffmpeg` errors.

**Current Status & Immediate Next Steps:**

*   All necessary configuration files (`docker-compose.yml`, `nginx.conf`, `load-tester/Dockerfile`, `load-tester/requirements.txt`) and the client script (`load_test_client.py`) are in place.
*   The Docker services (including 3 `whisperlive` replicas) are running via `docker-compose up`.
*   The immediate **blocker** is the lack of valid `.wav` audio files in the `/home/dima/vexa/test_audio` directory that both `ffmpeg` (for potential conversion) and the `soundfile` library (within the client script) can read.
*   **Next actions required:**
    1.  Place at least one known-good, standard `.wav` file into `/home/dima/vexa/test_audio`.
    2.  (Optional but recommended) Use the `ffmpeg` command inside the `load-tester` container to convert this file to 16kHz mono 16-bit PCM (`*.converted.wav`) to ensure maximum compatibility.
    3.  Run the load test script using `docker-compose exec load-tester python load_test_client.py --num-clients <N>`.

**Phase 2: Load Testing Plan & KPIs**

**Objective:**

To rigorously evaluate the performance, scalability, and reliability of the horizontally scaled `whisperlive` service architecture under simulated load within the `vexa_dev` Docker Compose environment.

**Key Performance Indicators (KPIs):**

1.  **Maximum Concurrent Connections:** The highest number of simultaneous client connections the system (load balancer + 3 `whisperlive` replicas) can sustain while meeting acceptable performance thresholds for latency and error rates.
2.  **End-to-End Transcription Latency:** The time elapsed from sending an audio chunk from the client to receiving the corresponding transcription result back. We should measure average, 95th percentile (p95), and maximum latency.
3.  **Word Error Rate (WER):** The accuracy of the transcriptions produced compared to ground truth transcripts. This measures the core quality of the transcription service under load.
4.  **Resource Utilization:**
    *   CPU Utilization (%) per `whisperlive` replica and `load-balancer`.
    *   GPU Utilization (%) per `whisperlive` replica (if GPUs are used).
    *   GPU Memory Usage (MB/GB) per `whisperlive` replica (if GPUs are used).
    *   Container Memory Usage (MB/GB) per `whisperlive` replica and `load-balancer`.
5.  **System Stability & Reliability:**
    *   Connection Success Rate (%): Percentage of successful client connection attempts.
    *   Error Rate (%): Percentage of connections or transcription requests resulting in errors (logged by services or reported to the client).
    *   Load Balancer Distribution: Qualitative assessment of whether load appears to be distributed across the `whisperlive` replicas (e.g., via resource monitoring).

**Testing Plan & Evaluation Strategy:**

**Phase 1: Preparation**

1.  **Ground Truth Data:**
    *   Ensure the `test_audio` directory (`/home/dima/vexa_dev/test_audio`) contains not only the `.wav` files (ideally the 16kHz converted versions like `LJ001-0001_16kHz.wav`) but also their corresponding ground truth transcriptions. The LJSpeech dataset includes a `metadata.csv` file with IDs and text. We need to make this accessible to the `load-tester` or the analysis environment. A simple approach is to create text files named identically to the audio files (e.g., `LJ001-0001_16kHz.txt`) containing the exact transcription.
2.  **Enhance `load_test_client.py`:** Modify the Python script to:
    *   **Measure Latency:** Record timestamps before sending an audio chunk and upon receiving a transcription result. Calculate the delta for each chunk/result pair.
    *   **Collect Full Transcripts:** Aggregate all received transcription chunks for each simulated client session into a single final transcript per audio file processed.
    *   **Output Results:** Log latency measurements (e.g., average, p95 per connection) and the final collected transcripts (e.g., keyed by audio filename) to a structured format (like JSON or CSV) written to a file (e.g., `/app/test_results/run_<N>.json`).
    *   **Error Handling:** Log connection failures, unexpected disconnections, and any error messages received from the server.
3.  **Install WER Tool:** Ensure a WER calculation tool is available. The `jiwer` Python library is a good option. This can be installed *inside* the `load-tester` container or in your local environment where you'll perform the analysis.
    *   *Option A (Inside Container):* Add `jiwer` to `load-tester/requirements.txt` and rebuild the image (`docker-compose build load-tester`). Or, install it temporarily: `docker-compose exec load-tester pip install jiwer`
    *   *Option B (Local):* `pip install jiwer` locally.

**Phase 2: Test Execution**

1.  **Start Monitoring:** Open terminals to monitor resource usage and logs:
    *   `docker stats $(docker-compose -p vexa_dev ps -q whisperlive load-balancer)` (Live stats - Note: Added `-p vexa_dev`)
    *   `docker-compose -p vexa_dev logs -f whisperlive load-balancer` (Live logs - Note: Added `-p vexa_dev`)
2.  **Run Load Test:** Execute the test script from *outside* the container using `docker-compose exec`. Start with a low number of clients (e.g., N=5 or N=10) and gradually increase N in subsequent runs.
    *   `docker-compose -p vexa_dev exec load-tester mkdir -p /app/test_results` (Ensure output dir exists - Note: Added `-p vexa_dev`)
    *   `docker-compose -p vexa_dev exec load-tester python load_test_client.py --num-clients <N> --audio-dir /app/test_audio --output-file /app/test_results/run_<N>.json` (Adjust script args as needed based on modifications - Note: Added `-p vexa_dev`)
3.  **Observe:** Watch `docker stats` for resource consumption patterns across replicas. Check logs for errors during the run.

**Phase 3: Analysis & Evaluation**

1.  **Retrieve Results:** Copy the results file(s) from the container if needed, or access them via the mounted volume.
2.  **Latency Analysis:** Analyze the latency data from the output file(s). Calculate overall average, p95, and max latency for the run. Check if they meet your target (e.g., p95 < 500ms).
3.  **WER Calculation:**
    *   Write a small script (or manually use `jiwer`) to compare the collected transcripts from the output file against the ground truth text files.
    *   `wer_result = jiwer.compute_measures(ground_truth_list, hypothesis_list)`
    *   Calculate the overall WER for the test run.
4.  **Resource Analysis:** Review the peak and average CPU/GPU/Memory usage from `docker stats` (you might need to capture the output during the run, e.g., `docker stats ... --no-stream > stats_run_<N>.log`). Determine if resource usage is sustainable and balanced.
5.  **Stability Analysis:**
    *   Calculate the connection success rate based on client script logs/output.
    *   Tally errors from service logs and client output to determine the error rate.
    *   Check if resource usage was relatively even across `whisperlive` replicas, indicating good load balancing.

**Phase 4: Iteration**

1.  Repeat Phases 2 and 3, incrementing the number of clients (`N`).
2.  Identify the **Maximum Concurrent Connections** by finding the value of `N` beyond which:
    *   Latency (especially p95) exceeds acceptable thresholds.
    *   WER increases significantly.
    *   Error rates become non-negligible.
    *   Resource limits (CPU/Memory/GPU) are consistently hit on replicas.
