# load_test_client.py
import asyncio
import websockets
import numpy as np
import soundfile as sf
import argparse
import os
import random
import time
import logging
import uuid
import json
import statistics
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
CHUNK_SIZE = 8192  # Bytes to send at a time (adjust as needed)
SAMPLE_RATE = 16000
CHANNELS = 1
AUDIO_DTYPE = 'float32'
SIMULATED_DELAY_SECONDS = (CHUNK_SIZE / (SAMPLE_RATE * np.dtype(AUDIO_DTYPE).itemsize * CHANNELS)) # Simulate real-time


async def receive_messages(websocket, client_id, message_data_list):
    """
    Listens for messages from the server, collecting timestamps and transcript data.
    
    Args:
        websocket: WebSocket connection
        client_id: ID of the client
        message_data_list: List to collect message data with timestamps
        
    Returns:
        message_count: Number of messages received
        full_transcript: Aggregated transcript from all messages
    """
    message_count = 0
    full_transcript = ""
    
    try:
        async for message in websocket:
            receive_time = time.time()
            message_count += 1
            
            # Try to parse JSON response
            try:
                message_data = json.loads(message)
                if isinstance(message_data, dict) and 'text' in message_data:
                    transcript_part = message_data['text']
                    full_transcript = transcript_part  # Usually the latest message contains the full transcript so far
                else:
                    transcript_part = str(message_data)  # Fallback if not in expected format
            except json.JSONDecodeError:
                transcript_part = "Non-JSON message"
            
            # Store the message data with timestamp
            message_data_list.append({
                'timestamp': receive_time,
                'message_num': message_count,
                'transcript_part': transcript_part,
                'raw_message': message[:500]  # Truncate if very long
            })
            
            logging.debug(f"Client {client_id}: Received message {message_count}")
            
    except websockets.exceptions.ConnectionClosedOK:
        logging.info(f"Client {client_id}: Connection closed normally.")
    except websockets.exceptions.ConnectionClosedError as e:
        logging.error(f"Client {client_id}: Connection closed with error: {e}")
    except Exception as e:
        logging.error(f"Client {client_id}: Error receiving messages: {e}")
    finally:
        logging.info(f"Client {client_id}: Received a total of {message_count} messages.")
    
    return message_count, full_transcript


async def run_client(client_id, server_url, audio_file):
    """
    Simulates a single client connecting and streaming an audio file.
    
    Returns a dictionary with detailed metrics and results.
    """
    websocket = None
    message_count = 0
    connection_start_time = time.time()
    stream_start_time = None
    audio_duration = 0
    client_uid = str(uuid.uuid4())
    message_data_list = []
    full_transcript = ""
    
    # Results dictionary to collect metrics
    result_data = {
        'client_id': client_id,
        'client_uid': client_uid,
        'audio_file': os.path.basename(audio_file),
        'success': False,
        'message_count': 0,
        'audio_duration': 0,
        'processing_time': 0,
        'connection_time': 0,
        'message_data': [],
        'transcript': "",
        'latency_stats': {},
        'error': None
    }
    
    logging.info(f"Client {client_id}: Starting - UID {client_uid} - File {os.path.basename(audio_file)}")

    try:
        # --- Read Audio File ---
        try:
            with sf.SoundFile(audio_file, 'r') as f:
                if f.samplerate != SAMPLE_RATE:
                    logging.warning(f"Client {client_id}: Audio file {audio_file} has sample rate {f.samplerate}, expected {SAMPLE_RATE}.")
                if f.channels != CHANNELS:
                     logging.warning(f"Client {client_id}: Audio file {audio_file} has {f.channels} channels, expected {CHANNELS}.")
                # Read entire file - adjust if files are very large
                audio_data = f.read(dtype=AUDIO_DTYPE)
                audio_duration = len(audio_data) / SAMPLE_RATE
                result_data['audio_duration'] = audio_duration
        except Exception as e:
            error_msg = f"Failed to read audio file {audio_file}: {e}"
            logging.error(f"Client {client_id}: {error_msg}")
            result_data['error'] = error_msg
            return result_data

        # --- Connect to Server ---
        connection_start_time = time.time()
        websocket = await websockets.connect(server_url, open_timeout=10, close_timeout=10)
        connection_time = time.time() - connection_start_time
        result_data['connection_time'] = connection_time
        logging.info(f"Client {client_id}: Connected to {server_url} in {connection_time:.2f} seconds")

        # --- Start Receiving Task ---
        receiver_task = asyncio.create_task(receive_messages(websocket, client_id, message_data_list))

        # --- Send Initial Config ---
        config_message = {
            "uid": client_uid,
            "language": "en",  # Specify English language
            "task": "transcribe",
            "model": "large-v3", # Should match server if relevant
            "use_vad": True,
            # Add required fields
            "platform": "test",
            "meeting_url": "https://test-meeting.example.com",
            "token": "test-token",
            "meeting_id": f"test-meeting-{client_id}"
        }
        await websocket.send(json.dumps(config_message)) # Use proper JSON serialization
        logging.info(f"Client {client_id}: Sent initial config.")

        # --- Stream Audio Chunks ---
        stream_start_time = time.time()
        bytes_sent = 0
        num_chunks = (len(audio_data) * audio_data.itemsize + CHUNK_SIZE - 1) // CHUNK_SIZE

        for i in range(num_chunks):
            start_byte = i * CHUNK_SIZE
            end_byte = start_byte + CHUNK_SIZE
            chunk = audio_data.flat[start_byte:end_byte].tobytes() # Get bytes slice

            if not chunk:
                break

            await websocket.send(chunk)
            bytes_sent += len(chunk)
            logging.debug(f"Client {client_id}: Sent chunk {i+1}/{num_chunks} ({len(chunk)} bytes)")

            # Simulate real-time pacing
            await asyncio.sleep(SIMULATED_DELAY_SECONDS)

        logging.info(f"Client {client_id}: Finished streaming {bytes_sent} bytes ({num_chunks} chunks) for {os.path.basename(audio_file)}")

        # --- Wait for processing / server disconnect ---
        await asyncio.sleep(5) # Wait a bit for final messages
        await websocket.close(reason='Client finished streaming')
        logging.info(f"Client {client_id}: WebSocket closed.")

        message_count, full_transcript = await receiver_task
        processing_time = time.time() - stream_start_time if stream_start_time else 0
        
        # Calculate latencies for each message relative to stream start
        latencies = []
        for msg_data in message_data_list:
            latency = msg_data['timestamp'] - stream_start_time
            msg_data['latency'] = latency
            latencies.append(latency)
            
        # Calculate latency statistics
        if latencies:
            result_data['latency_stats'] = {
                'min': min(latencies),
                'max': max(latencies),
                'mean': statistics.mean(latencies),
                'median': statistics.median(latencies),
                'p95': statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
            }
            
        # Populate result data
        result_data['success'] = True
        result_data['message_count'] = message_count
        result_data['processing_time'] = processing_time
        result_data['message_data'] = message_data_list
        result_data['transcript'] = full_transcript
        
        return result_data

    except websockets.exceptions.ConnectionClosedOK:
        logging.info(f"Client {client_id}: Connection closed before finishing.")
        if websocket and not receiver_task.done():
             await websocket.close()
             message_count, full_transcript = await receiver_task # Get messages received before close
             
        result_data['message_count'] = message_count
        result_data['transcript'] = full_transcript
        result_data['message_data'] = message_data_list
        result_data['processing_time'] = time.time() - stream_start_time if stream_start_time else 0
        result_data['error'] = "Connection closed before finishing"
        return result_data
        
    except Exception as e:
        error_msg = f"FAILED with error: {e}"
        logging.error(f"Client {client_id}: {error_msg}", exc_info=True)
        if websocket and not websocket.closed:
             await websocket.close(code=1011, reason=f'Client error: {e}')
        if 'receiver_task' in locals() and not receiver_task.done():
             receiver_task.cancel() # Attempt to cancel receiver task
             try:
                 await receiver_task
             except asyncio.CancelledError:
                 pass
             except Exception as rex:
                 logging.error(f"Client {client_id}: Error during receiver task cancellation: {rex}")

        result_data['error'] = error_msg
        result_data['processing_time'] = time.time() - stream_start_time if stream_start_time else 0
        return result_data


async def main(args):
    """Runs multiple clients concurrently and saves results to a JSON file if specified."""
    server_url = f"ws://{args.host}:{args.port}"
    logging.info(f"Starting load test with {args.num_clients} clients targeting {server_url}")
    logging.info(f"Using audio files from: {args.audio_dir}")
    
    # Results collection
    all_results = {
        'test_id': str(uuid.uuid4()),
        'timestamp': datetime.now().isoformat(),
        'test_config': {
            'num_clients': args.num_clients,
            'server_url': server_url,
            'audio_dir': args.audio_dir,
        },
        'client_results': [],
        'summary': {}
    }

    try:
        audio_files = [os.path.join(args.audio_dir, f) for f in os.listdir(args.audio_dir) if f.lower().endswith('.wav')]
        if not audio_files:
            logging.error(f"No .wav files found in {args.audio_dir}")
            return
        logging.info(f"Found {len(audio_files)} audio files.")
    except FileNotFoundError:
        logging.error(f"Audio directory not found: {args.audio_dir}")
        return
    except Exception as e:
        logging.error(f"Error listing audio files: {e}")
        return

    start_time = time.time()
    tasks = []
    for i in range(args.num_clients):
        audio_file = random.choice(audio_files)
        tasks.append(run_client(i + 1, server_url, audio_file))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    end_time = time.time()

    # --- Process Results ---
    successful_clients = 0
    total_messages = 0
    total_audio_duration = 0
    total_processing_time = 0
    failed_clients = 0
    all_latencies = []

    for i, result in enumerate(results):
        client_id = i + 1
        if isinstance(result, Exception):
            logging.error(f"Client {client_id}: Task raised an exception: {result}")
            failed_clients += 1
            all_results['client_results'].append({
                'client_id': client_id,
                'success': False,
                'error': str(result)
            })
        else:
            # Store the complete client result data
            all_results['client_results'].append(result)
            
            if result['success']:
                successful_clients += 1
                total_messages += result['message_count']
                total_audio_duration += result['audio_duration']
                total_processing_time += result['processing_time']
                
                # Collect latencies for aggregate statistics
                if 'latency_stats' in result and 'mean' in result['latency_stats']:
                    all_latencies.append(result['latency_stats']['mean'])
            else:
                failed_clients += 1
                logging.warning(f"Client {client_id}: Task reported failure: {result['error']}")
                total_messages += result.get('message_count', 0)  # Count messages even on failure

    # Calculate summary statistics
    summary = {
        'total_duration': end_time - start_time,
        'target_clients': args.num_clients,
        'successful_clients': successful_clients,
        'failed_clients': failed_clients,
        'total_messages': total_messages,
    }
    
    if successful_clients > 0:
        summary['avg_audio_duration'] = total_audio_duration / successful_clients
        summary['avg_processing_time'] = total_processing_time / successful_clients
        
    if all_latencies:
        summary['latency'] = {
            'min': min(all_latencies),
            'max': max(all_latencies),
            'mean': statistics.mean(all_latencies),
            'median': statistics.median(all_latencies)
        }
        if len(all_latencies) >= 20:
            summary['latency']['p95'] = statistics.quantiles(all_latencies, n=20)[18]
    
    all_results['summary'] = summary

    # Output to JSON file if specified
    if args.output_file:
        try:
            os.makedirs(os.path.dirname(args.output_file), exist_ok=True)
            with open(args.output_file, 'w') as f:
                json.dump(all_results, f, indent=2)
            logging.info(f"Results saved to {args.output_file}")
        except Exception as e:
            logging.error(f"Failed to write results to {args.output_file}: {e}")

    # Log summary
    logging.info("----- Load Test Summary -----")
    logging.info(f"Total duration: {summary['total_duration']:.2f} seconds")
    logging.info(f"Target clients: {summary['target_clients']}")
    logging.info(f"Successful clients: {summary['successful_clients']}")
    logging.info(f"Failed clients: {summary['failed_clients']}")
    logging.info(f"Total messages received: {summary['total_messages']}")
    
    if successful_clients > 0:
        logging.info(f"Average audio duration per successful client: {summary['avg_audio_duration']:.2f} seconds")
        logging.info(f"Average processing time per successful client: {summary['avg_processing_time']:.2f} seconds")
        
    if 'latency' in summary:
        logging.info(f"Average latency: {summary['latency']['mean']:.3f} seconds")
        if 'p95' in summary['latency']:
            logging.info(f"95th percentile latency: {summary['latency']['p95']:.3f} seconds")
            
    logging.info("---------------------------")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhisperLive Load Test Client")
    parser.add_argument("--num-clients", type=int, default=5, help="Number of concurrent clients")
    parser.add_argument("--host", type=str, default="load-balancer", help="Server hostname (service name in Docker Compose)")
    parser.add_argument("--port", type=int, default=80, help="Server port (Nginx internal port)")
    parser.add_argument("--audio-dir", type=str, default="/app/test_audio", help="Directory containing .wav audio files")
    parser.add_argument("--output-file", type=str, help="JSON file to save detailed test results")
    parser.add_argument("--results-dir", type=str, default="/app/test_audio/results", help="Directory to save test results (mounted to host)")
    # Add more arguments if needed (e.g., test duration, language)

    args = parser.parse_args()
    
    # If no output file is specified, generate a default one in the results directory
    if not args.output_file:
        # Make sure results directory exists
        os.makedirs(args.results_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_file = f"{args.results_dir}/run_{args.num_clients}_clients_{timestamp}.json"
    
    asyncio.run(main(args)) 