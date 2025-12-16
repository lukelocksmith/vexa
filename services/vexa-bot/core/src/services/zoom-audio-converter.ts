import { log } from '../utils';

export interface AudioFormat {
  sampleRate: number;
  channels: number;
  bitDepth: number;
  encoding: 'pcm' | 'float32';
}

export class ZoomAudioConverter {
  private sourceSampleRate: number = 48000; // Default RTMS sample rate (may vary)
  private targetSampleRate: number = 16000; // WhisperLive requirement
  private sourceChannels: number = 1; // Default mono
  private targetChannels: number = 1; // WhisperLive requires mono

  /**
   * Set source audio format from RTMS SDK
   */
  setSourceFormat(format: AudioFormat): void {
    this.sourceSampleRate = format.sampleRate;
    this.sourceChannels = format.channels;
    log(`[ZoomAudioConverter] Source format: ${format.sampleRate}Hz, ${format.channels}ch, ${format.bitDepth}bit, ${format.encoding}`);
  }

  /**
   * Convert RTMS audio buffer to Float32Array
   * Assumes input is PCM int16 (most common format)
   */
  convertToFloat32Array(audioBuffer: Buffer): Float32Array {
    try {
      // Assume PCM int16 format (most common)
      const int16Array = new Int16Array(audioBuffer.buffer, audioBuffer.byteOffset, audioBuffer.length / 2);
      const float32Array = new Float32Array(int16Array.length);

      // Convert int16 (-32768 to 32767) to float32 (-1.0 to 1.0)
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }

      return float32Array;
    } catch (error: any) {
      log(`[ZoomAudioConverter] Error converting to Float32Array: ${error.message}`);
      throw error;
    }
  }

  /**
   * Resample audio to target sample rate (16kHz for WhisperLive)
   * Uses linear interpolation (simple but effective for PoC)
   */
  resampleTo16kHz(audioData: Float32Array, sourceSampleRate?: number): Float32Array {
    const sourceRate = sourceSampleRate || this.sourceSampleRate;
    
    if (sourceRate === this.targetSampleRate) {
      return audioData; // No resampling needed
    }

    try {
      const ratio = sourceRate / this.targetSampleRate;
      const targetLength = Math.floor(audioData.length / ratio);
      const resampled = new Float32Array(targetLength);

      for (let i = 0; i < targetLength; i++) {
        const sourceIndex = i * ratio;
        const indexFloor = Math.floor(sourceIndex);
        const indexCeil = Math.min(indexFloor + 1, audioData.length - 1);
        const fraction = sourceIndex - indexFloor;

        // Linear interpolation
        resampled[i] = audioData[indexFloor] * (1 - fraction) + audioData[indexCeil] * fraction;
      }

      return resampled;
    } catch (error: any) {
      log(`[ZoomAudioConverter] Error resampling: ${error.message}`);
      throw error;
    }
  }

  /**
   * Convert stereo to mono (if needed)
   */
  convertToMono(audioData: Float32Array, channels: number = this.sourceChannels): Float32Array {
    if (channels === 1) {
      return audioData; // Already mono
    }

    try {
      const samplesPerChannel = audioData.length / channels;
      const mono = new Float32Array(samplesPerChannel);

      for (let i = 0; i < samplesPerChannel; i++) {
        let sum = 0;
        for (let ch = 0; ch < channels; ch++) {
          sum += audioData[i * channels + ch];
        }
        mono[i] = sum / channels; // Average channels
      }

      return mono;
    } catch (error: any) {
      log(`[ZoomAudioConverter] Error converting to mono: ${error.message}`);
      throw error;
    }
  }

  /**
   * Process audio chunk: convert format, resample, and ensure mono
   */
  processAudioChunk(chunk: Buffer, sourceFormat?: AudioFormat): Float32Array | null {
    try {
      if (sourceFormat) {
        this.setSourceFormat(sourceFormat);
      }

      // Convert to Float32Array
      let float32Audio = this.convertToFloat32Array(chunk);

      // Convert to mono if needed
      if (this.sourceChannels > 1) {
        float32Audio = this.convertToMono(float32Audio, this.sourceChannels);
      }

      // Resample to 16kHz
      const resampled = this.resampleTo16kHz(float32Audio);

      return resampled;
    } catch (error: any) {
      log(`[ZoomAudioConverter] Error processing audio chunk: ${error.message}`);
      return null;
    }
  }

  /**
   * Get target format for WhisperLive
   */
  getTargetFormat(): AudioFormat {
    return {
      sampleRate: this.targetSampleRate,
      channels: this.targetChannels,
      bitDepth: 32,
      encoding: 'float32',
    };
  }
}

