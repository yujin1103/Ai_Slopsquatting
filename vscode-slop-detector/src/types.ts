/** 파서가 추출한 개별 import 정보 */
export interface ParsedImport {
  packageName: string;
  line: number; // 0-based
  startChar: number;
  endChar: number;
}

/** FastAPI /analyze 응답의 개별 패키지 결과 */
export interface PackageResult {
  package: string;
  pypi_exists: boolean;
  npm_exists: boolean;
  ecosystem: 'python' | 'npm' | 'both' | 'unknown';
  is_dynamic: boolean;
  score: number;
  level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  signals: string[];
  closest: string;
  min_dist: number;
  reg_days: number | null;
  version_count: number;
  metadata_score: number;
  source_analyzed: boolean;
  source_score: number;
  source_signals: string[];
}

/** 로컬 캐시 항목 */
export interface CacheEntry {
  result: PackageResult;
  timestamp: number;
}

/** 위험 등급 순서 (필터링용) */
export const RISK_ORDER: Record<string, number> = {
  LOW: 0,
  MEDIUM: 1,
  HIGH: 2,
  CRITICAL: 3,
};
