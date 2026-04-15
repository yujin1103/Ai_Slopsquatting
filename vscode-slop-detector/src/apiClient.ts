/**
 * FastAPI 백엔드 HTTP 클라이언트
 * localhost:8001 /analyze 엔드포인트 호출 + 로컬 캐시
 */

import * as http from 'http';
import * as https from 'https';
import { PackageResult, CacheEntry } from './types';

const CACHE_TTL_MS = 5 * 60 * 1000; // 5분 로컬 캐시 (서버 30분 캐시와 별개)
const REQUEST_TIMEOUT_MS = 30_000;

const cache = new Map<string, CacheEntry>();

/** 캐시에서 조회 */
function getCached(packageName: string): PackageResult | null {
  const entry = cache.get(packageName);
  if (!entry) { return null; }
  if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
    cache.delete(packageName);
    return null;
  }
  return entry.result;
}

/** 캐시에 저장 */
function setCache(result: PackageResult): void {
  cache.set(result.package, { result, timestamp: Date.now() });
}

/** HTTP POST 요청 (Node.js 기본 모듈 사용) */
function postJson(url: string, body: object): Promise<any> {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const parsed = new URL(url);
    const client = parsed.protocol === 'https:' ? https : http;

    const req = client.request(
      {
        hostname: parsed.hostname,
        port: parsed.port,
        path: parsed.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(data),
        },
        timeout: REQUEST_TIMEOUT_MS,
      },
      (res) => {
        let body = '';
        res.on('data', (chunk: Buffer) => { body += chunk.toString(); });
        res.on('end', () => {
          try {
            resolve(JSON.parse(body));
          } catch {
            reject(new Error(`Invalid JSON response: ${body.slice(0, 200)}`));
          }
        });
      }
    );

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });

    req.write(data);
    req.end();
  });
}

/** 패키지 목록 분석 요청 */
export async function analyzePackages(
  packageNames: string[],
  apiUrl: string
): Promise<PackageResult[]> {
  if (packageNames.length === 0) { return []; }

  // 캐시에 있는 것과 없는 것 분리
  const cached: PackageResult[] = [];
  const uncached: string[] = [];

  for (const name of packageNames) {
    const hit = getCached(name);
    if (hit) {
      cached.push(hit);
    } else {
      uncached.push(name);
    }
  }

  // 새로 조회할 게 없으면 캐시만 반환
  if (uncached.length === 0) { return cached; }

  // 최대 10개씩 (API 제한)
  const batches: string[][] = [];
  for (let i = 0; i < uncached.length; i += 10) {
    batches.push(uncached.slice(i, i + 10));
  }

  const freshResults: PackageResult[] = [];

  for (const batch of batches) {
    try {
      const response = await postJson(`${apiUrl}/analyze`, { packages: batch });
      const results: PackageResult[] = response.results || response;

      for (const r of results) {
        setCache(r);
        freshResults.push(r);
      }
    } catch (err) {
      // API 오류 시 해당 배치는 스킵
      console.error('[Slopsquatting] API error:', err);
    }
  }

  return [...cached, ...freshResults];
}

/** 서버 상태 확인 */
export async function checkHealth(apiUrl: string): Promise<boolean> {
  return new Promise((resolve) => {
    const parsed = new URL(`${apiUrl}/health`);
    const client = parsed.protocol === 'https:' ? https : http;

    const req = client.get(
      { hostname: parsed.hostname, port: parsed.port, path: parsed.pathname, timeout: 5000 },
      (res) => { resolve(res.statusCode === 200); }
    );

    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

/** 캐시 초기화 */
export function clearCache(): void {
  cache.clear();
}
