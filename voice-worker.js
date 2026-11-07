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
      asr = await pipeline('automatic-speech-recognition', `onnx-community/moonshine-${m.size}-ko-ONNX`, {
        device: 'wasm',
        dtype: m.dtype,
        progress_callback: (p) => {
          if (p.status === 'progress') self.postMessage({ type: 'progress', file: p.file, loaded: p.loaded, total: p.total });
        },
      });
      self.postMessage({ type: 'ready', ms: performance.now() - started });
    } else if (m.type === 'run') {
      const before = netCount();
      const started = performance.now();
      // 기본 출력 길이는 영어 기준이라 한국어 문장이 잘리므로 음성 길이에 맞춰 늘린다.
      const out = await asr(m.audio, { max_new_tokens: Math.ceil(m.audio.length / 16000 * 16) + 8 });
      // 무음 구간에서 나오는 영문 잡음은 버린다.
      const text = /[가-힣0-9]/.test(out.text) ? out.text.trim() : '';
      self.postMessage({ type: 'done', id: m.id, final: m.final, text, ms: performance.now() - started, net: netCount() - before });
    }
  } catch (e) {
    self.postMessage({ type: 'error', message: String(e && e.message || e) });
  }
};
