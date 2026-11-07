// 음성 인식 시험판의 작업 스레드. 모델 파일만 내려받고, 음성은 이 기기 안에서만 처리한다.
import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.2';

env.allowLocalModels = false;
let asr = null;

const netCount = () => performance.getEntriesByType('resource').length;

self.onmessage = async ({ data: m }) => {
  try {
    if (m.type === 'load') {
      asr = null;
      const started = performance.now();
      asr = await pipeline('automatic-speech-recognition', `onnx-community/whisper-${m.size}`, {
        device: m.device,
        dtype: m.device === 'webgpu' ? { encoder_model: 'fp32', decoder_model_merged: 'q4' } : 'q8',
        progress_callback: (p) => {
          if (p.status === 'progress') self.postMessage({ type: 'progress', file: p.file, loaded: p.loaded, total: p.total });
        },
      });
      self.postMessage({ type: 'ready', ms: performance.now() - started });
    } else if (m.type === 'run') {
      const before = netCount();
      const started = performance.now();
      const out = await asr(m.audio, { language: 'korean', task: 'transcribe', chunk_length_s: 30, stride_length_s: 5 });
      self.postMessage({ type: 'done', text: out.text.trim(), ms: performance.now() - started, net: netCount() - before });
    }
  } catch (e) {
    self.postMessage({ type: 'error', message: String(e && e.message || e) });
  }
};
