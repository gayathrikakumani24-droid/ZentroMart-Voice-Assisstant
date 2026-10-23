/**
 * ZentroMart VoiceOps — Client-side PCM WAV Encoder.
 *
 * Encodes audio samples into a standard 16kHz 16-bit mono PCM WAV Blob.
 * Guaranteed compatibility with Gnani.ai STT across all modern browsers.
 */

export function encodeWAV(samples, sampleRate = 16000) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  /* RIFF identifier */
  writeString(view, 0, 'RIFF');
  /* RIFF chunk length */
  view.setUint32(4, 36 + samples.length * 2, true);
  /* RIFF type */
  writeString(view, 8, 'WAVE');
  /* format chunk identifier */
  writeString(view, 12, 'fmt ');
  /* format chunk length */
  view.setUint32(16, 16, true);
  /* sample format (raw PCM) */
  view.setUint16(20, 1, true);
  /* channel count (1 = mono) */
  view.setUint16(22, 1, true);
  /* sample rate */
  view.setUint32(24, sampleRate, true);
  /* byte rate (sampleRate * 1 channel * 2 bytes/sample) */
  view.setUint32(28, sampleRate * 2, true);
  /* block align (1 channel * 2 bytes/sample) */
  view.setUint16(32, 2, true);
  /* bits per sample */
  view.setUint16(34, 16, true);
  /* data chunk identifier */
  writeString(view, 36, 'data');
  /* data chunk length */
  view.setUint32(40, samples.length * 2, true);

  // Write 16-bit PCM samples with clipping
  floatTo16BitPCM(view, 44, samples);

  return new Blob([buffer], { type: 'audio/wav' });
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

function floatTo16BitPCM(view, offset, input) {
  for (let i = 0; i < input.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
}

/**
 * Resample an AudioBuffer to target sample rate (default: 16000 Hz) and downmix to mono.
 */
export function resampleToMono16kHz(audioBuffer, targetSampleRate = 16000) {
  const numChannels = audioBuffer.numberOfChannels;
  const length = audioBuffer.length;
  const originalSampleRate = audioBuffer.sampleRate;

  // Mix down channels to mono
  const mono = new Float32Array(length);
  for (let i = 0; i < length; i++) {
    let sum = 0;
    for (let c = 0; c < numChannels; c++) {
      sum += audioBuffer.getChannelData(c)[i];
    }
    mono[i] = sum / numChannels;
  }

  // If already at target sample rate, return mono samples
  if (originalSampleRate === targetSampleRate) {
    return mono;
  }

  // Linear interpolation resampling
  const ratio = originalSampleRate / targetSampleRate;
  const newLength = Math.round(length / ratio);
  const result = new Float32Array(newLength);

  for (let i = 0; i < newLength; i++) {
    const originIdx = i * ratio;
    const lower = Math.floor(originIdx);
    const upper = Math.min(lower + 1, length - 1);
    const weight = originIdx - lower;
    result[i] = mono[lower] * (1 - weight) + mono[upper] * weight;
  }

  return result;
}
