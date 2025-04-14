# WhisperLive Scalability Documentation

This document describes the horizontally scalable WhisperLive architecture, explains how to run load tests against it, and provides guidance on interpreting test results.

## Scaling Architecture

The WhisperLive service is designed to scale horizontally, allowing the system to handle a higher number of simultaneous transcription requests. This is achieved through:

### Key Components:

1. **WhisperLive Instances**: Multiple identical instances of the WhisperLive transcription service, each capable of processing audio streams independently.

2. **Nginx Load Balancer**: A reverse proxy that distributes incoming WebSocket connections across all available WhisperLive instances.

3. **Transcription Collector**: A centralized service that collects and stores transcription segments from all WhisperLive instances, providing a unified storage layer.

### Architecture Diagram:

```
                     ┌───────────────────┐
                     │                   │
                     │  Nginx            │
  Clients ───────────►  Load Balancer    │
                     │  (port 8990)      │
                     │                   │
                     └─────────┬─────────┘
                               │
                 ┌─────────────┼─────────────────┐
                 │             │                 │
                 ▼             ▼                 ▼
   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
   │                 │ │                 │ │                 │
   │   WhisperLive   │ │   WhisperLive   │ │   WhisperLive   │
   │   Instance 1    │ │   Instance 2    │ │   Instance 3    │
   │                 │ │                 │ │                 │
   └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
            │                   │                   │
            └───────────┬───────┴───────────┬───────┘
                        │                   │
                        ▼                   ▼
           ┌─────────────────────┐ ┌─────────────────┐
           │                     │ │                 │
           │  Transcription      │ │                 │
           │  Collector          │ │    Database     │
           │                     │ │                 │
           └─────────────────────┘ └─────────────────┘
```

### State Management:

- Each WhisperLive instance manages its own temporary state (VAD context, audio buffer, etc.).
- The critical, long-term state (complete transcripts, meeting information) is stored externally in the Transcription Collector and database.
- This architecture allows clients to seamlessly reconnect to different instances if needed.

## Load Testing

The system includes a dedicated load testing tool designed to simulate multiple concurrent clients and measure performance metrics.

### Running Load Tests

#### Prerequisites:

1. Ensure the full system is running with `docker-compose -p vexa_dev up -d`
2. Verify that all WhisperLive instances are properly initialized (check logs)
3. Prepare test audio files in the `./test_audio` directory (16kHz mono WAV files recommended)

#### Basic Test Command:

```bash
docker-compose -p vexa_dev exec load-tester python load_test_client.py --num-clients <N>
```

Where `<N>` is the number of simultaneous client connections you want to simulate.

#### Additional Options:

- `--host` and `--port`: Target a specific host/port (default: load-balancer:80)
- `--audio-dir`: Specify a different audio directory (default: /app/test_audio)
- `--results-dir`: Change where result files are saved (default: /app/test_audio/results)
- `--output-file`: Specify a custom output file path (optional)

#### Test Results Storage:

The load test client automatically saves test results to the `--results-dir` directory, which defaults to `/app/test_audio/results`. This directory is mounted to your host machine's `./test_audio/results` directory, allowing easy access to test results.

If the `--output-file` parameter is not specified, the script automatically generates a timestamped filename in the results directory:

```
run_<N>_clients_<timestamp>.json
```

The results directory is created automatically if it doesn't exist, ensuring your test results are always properly saved.

#### Testing Methodology:

For a comprehensive assessment, we recommend:

1. **Baseline Test**: Start with a low number of clients (5-10) to establish baseline performance.
2. **Incremental Tests**: Gradually increase the number of clients (e.g., 10, 20, 30, 40, 50).
3. **Saturation Test**: Continue increasing until performance degrades significantly.

### Test Results

Test results are saved in JSON files in the `./test_audio/results` directory with names following the pattern:
`run_<N>_clients_<timestamp>.json`

Each result file contains:

1. **Test Configuration**: Number of clients, server URL, etc.
2. **Per-Client Results**: Details for each simulated client:
   - Success status
   - Message count
   - Audio duration
   - Processing time
   - Connection time
   - Transcript
   - Latency statistics
   - Errors (if any)
3. **Summary Statistics**:
   - Total test duration
   - Successful/failed clients
   - Average audio duration
   - Average processing time
   - Latency metrics (min, max, mean, median, p95)

## Interpreting Results

### Key Performance Indicators (KPIs):

1. **Maximum Concurrent Connections:** The highest number of simultaneous connections the system can handle while maintaining acceptable performance.

2. **End-to-End Latency:** The time between sending audio and receiving transcriptions:
   - **Average Latency**: General performance indicator
   - **95th Percentile Latency (p95)**: Important for consistent user experience
   - **Maximum Latency**: Worst-case scenario

3. **Word Error Rate (WER):** The accuracy of transcriptions under load (requires ground truth transcripts).

4. **Resource Utilization:** CPU, memory, and GPU usage across instances.

5. **Success Rate:** Percentage of clients completing without errors.

### Interpreting Performance Degradation:

Monitor these signs of system reaching capacity:

1. **Increased Latency**: Sharp rise in p95 or average latency
2. **Failed Connections**: Clients unable to connect/complete transcription
3. **Error Messages**: Look for specific error patterns in logs
4. **Uneven Load Distribution**: Check if some instances handle more connections than others

### Optimizing Performance:

Based on test results, consider:

1. **Scaling Horizontally**: Add more WhisperLive instances
2. **Resource Allocation**: Adjust CPU/GPU allocation per instance
3. **Load Balancer Configuration**: Fine-tune Nginx settings
4. **Model Size/Type**: Consider smaller/faster models for higher concurrency

## Technical Deep Dive

### WebSocket Connection Flow:

1. Client connects to the Nginx load balancer on port 8990
2. Nginx forwards the WebSocket connection to one of the WhisperLive instances
3. Client sends:
   - Initial configuration (JSON with client ID, language, etc.)
   - Audio data in chunks
4. WhisperLive processes audio in real-time
5. Transcription results are sent back to the client
6. Transcriptions are also sent to the Transcription Collector

### Load Balancing Strategy:

Nginx uses a round-robin algorithm by default, distributing new connections evenly across the available instances. This works well because:

1. Each connection represents a complete streaming session
2. Sessions are relatively long-lived (duration of audio)
3. Processing load is similar across sessions

If needed, more sophisticated strategies (least connections, IP hash) can be configured in nginx.conf.

### Resources and Limits:

Each WhisperLive instance requires:
- A minimum of 2-4GB RAM
- GPU memory varies by model:
  - Small model: ~1GB VRAM
  - Medium model: ~2.5GB VRAM
  - Large model: ~6GB VRAM

These resource requirements limit how many instances can run on a single machine, especially for GPU-constrained environments.

## Example Analysis

Here's an example analysis of test results:

```
Test Series: Incremental load testing (5, 10, 20, 30 clients)

Results:
- 5 clients: 100% success, avg latency 0.8s, p95 latency 1.2s
- 10 clients: 100% success, avg latency 1.3s, p95 latency 1.9s
- 20 clients: 95% success, avg latency a2.1s, p95 latency 3.2s
- 30 clients: 80% success, avg latency 4.5s, p95 latency 7.8s

Analysis:
- System handles up to 20 clients with acceptable performance
- At 30 clients, we see significant latency increase and connection failures
- Recommended max load: 20 concurrent connections
- Bottleneck identified: GPU memory utilization reached 95% at 20 clients
```

When writing your own analysis, focus on:
1. The inflection point where performance degrades
2. Resource utilization at each client count
3. The specific failure modes (timeouts, errors, etc.)
4. Recommendations for system improvements 