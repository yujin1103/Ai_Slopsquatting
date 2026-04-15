/**
 * VS Code Diagnostics — import 문 위치에 인라인 경고 표시
 */

import * as vscode from 'vscode';
import { ParsedImport, PackageResult, RISK_ORDER } from './types';

let diagnosticCollection: vscode.DiagnosticCollection;

/** DiagnosticCollection 초기화 */
export function initDiagnostics(context: vscode.ExtensionContext): vscode.DiagnosticCollection {
  diagnosticCollection = vscode.languages.createDiagnosticCollection('slopsquatting');
  context.subscriptions.push(diagnosticCollection);
  return diagnosticCollection;
}

/** 위험 등급 → DiagnosticSeverity 매핑 */
function toSeverity(level: string): vscode.DiagnosticSeverity {
  switch (level) {
    case 'CRITICAL':
    case 'HIGH':
      return vscode.DiagnosticSeverity.Error;
    case 'MEDIUM':
      return vscode.DiagnosticSeverity.Warning;
    default:
      return vscode.DiagnosticSeverity.Information;
  }
}

/** 시그널을 읽기 좋은 메시지로 변환 */
function formatSignals(result: PackageResult): string {
  const parts: string[] = [];

  if (!result.pypi_exists && !result.npm_exists) {
    parts.push('PyPI/npm 미등록');
  } else {
    if (result.pypi_exists) { parts.push('PyPI 등록'); }
    if (result.npm_exists) { parts.push('npm 등록'); }
  }

  if (result.closest && result.min_dist <= 4) {
    parts.push(`"${result.closest}"와 유사 (편집거리 ${result.min_dist})`);
  }

  if (result.reg_days !== null && result.reg_days <= 30) {
    parts.push(`등록 ${result.reg_days}일 전`);
  }

  if (result.version_count <= 1) {
    parts.push('버전 1개');
  }

  if (result.source_analyzed && result.source_score > 0) {
    parts.push(`소스 위험도: ${result.source_score}`);
  }

  return parts.join(' | ');
}

/** Diagnostic 항목 생성 */
function createDiagnostic(
  imp: ParsedImport,
  result: PackageResult
): vscode.Diagnostic {
  const range = new vscode.Range(
    new vscode.Position(imp.line, imp.startChar),
    new vscode.Position(imp.line, imp.endChar)
  );

  const message =
    `[Slopsquatting] "${result.package}" — ` +
    `score: ${result.score} (${result.level}) | ` +
    formatSignals(result);

  const diagnostic = new vscode.Diagnostic(range, message, toSeverity(result.level));
  diagnostic.source = 'slopsquatting';
  diagnostic.code = result.score;

  return diagnostic;
}

/** 문서에 대한 Diagnostics 업데이트 */
export function updateDiagnostics(
  document: vscode.TextDocument,
  imports: ParsedImport[],
  results: PackageResult[],
  minLevel: string
): { total: number; risks: number } {
  const resultMap = new Map<string, PackageResult>();
  for (const r of results) {
    resultMap.set(r.package, r);
  }

  const minOrder = RISK_ORDER[minLevel] ?? 1;
  const diagnostics: vscode.Diagnostic[] = [];
  let risks = 0;

  for (const imp of imports) {
    const result = resultMap.get(imp.packageName);
    if (!result) { continue; }

    const order = RISK_ORDER[result.level] ?? 0;
    if (order >= minOrder) {
      diagnostics.push(createDiagnostic(imp, result));
      risks++;
    }
  }

  diagnosticCollection.set(document.uri, diagnostics);

  return { total: imports.length, risks };
}

/** 특정 문서의 Diagnostics 삭제 */
export function clearDiagnostics(uri: vscode.Uri): void {
  diagnosticCollection.delete(uri);
}
