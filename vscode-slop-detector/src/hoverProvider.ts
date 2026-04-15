/**
 * Hover Provider — import 문 위에 마우스 올리면 패키지 상세 정보 표시
 */

import * as vscode from 'vscode';
import { PackageResult } from './types';

// 최근 분석 결과 저장 (diagnostics와 공유)
const resultStore = new Map<string, Map<string, PackageResult>>();

/** 분석 결과 저장 (extension.ts에서 호출) */
export function storeResults(uri: string, results: PackageResult[]): void {
  const map = new Map<string, PackageResult>();
  for (const r of results) {
    map.set(r.package, r);
  }
  resultStore.set(uri, map);
}

/** 결과 조회 */
function getResult(uri: string, packageName: string): PackageResult | undefined {
  return resultStore.get(uri)?.get(packageName);
}

/** 위험 등급 이모지 */
function levelEmoji(level: string): string {
  switch (level) {
    case 'CRITICAL': return '🔴';
    case 'HIGH': return '🟠';
    case 'MEDIUM': return '🟡';
    case 'LOW': return '🟢';
    default: return '⚪';
  }
}

/** Markdown 상세 정보 생성 */
function buildHoverContent(result: PackageResult): vscode.MarkdownString {
  const md = new vscode.MarkdownString();
  md.isTrusted = true;

  md.appendMarkdown(`### ${levelEmoji(result.level)} Slopsquatting: \`${result.package}\`\n\n`);
  md.appendMarkdown(`| 항목 | 값 |\n|---|---|\n`);
  md.appendMarkdown(`| **위험 점수** | ${result.score} / 100 |\n`);
  md.appendMarkdown(`| **등급** | ${result.level} |\n`);
  md.appendMarkdown(`| **PyPI** | ${result.pypi_exists ? '✅ 등록' : '❌ 미등록'} |\n`);
  md.appendMarkdown(`| **npm** | ${result.npm_exists ? '✅ 등록' : '❌ 미등록'} |\n`);
  md.appendMarkdown(`| **에코시스템** | ${result.ecosystem} |\n`);

  if (result.reg_days !== null) {
    md.appendMarkdown(`| **등록일** | ${result.reg_days}일 전 |\n`);
  }

  md.appendMarkdown(`| **버전 수** | ${result.version_count} |\n`);

  if (result.closest && result.min_dist <= 4) {
    md.appendMarkdown(`| **유사 패키지** | \`${result.closest}\` (편집거리 ${result.min_dist}) |\n`);
  }

  if (result.source_analyzed) {
    md.appendMarkdown(`| **소스 분석** | 점수: ${result.source_score} |\n`);
  }

  // 시그널 목록
  if (result.signals.length > 0) {
    md.appendMarkdown(`\n**시그널:**\n`);
    for (const sig of result.signals) {
      md.appendMarkdown(`- ${sig}\n`);
    }
  }

  // 소스 시그널
  if (result.source_signals && result.source_signals.length > 0) {
    md.appendMarkdown(`\n**소스 분석 결과:**\n`);
    for (const sig of result.source_signals) {
      md.appendMarkdown(`- ⚠️ ${sig}\n`);
    }
  }

  return md;
}

/** HoverProvider 생성 */
export function createHoverProvider(): vscode.HoverProvider {
  return {
    provideHover(
      document: vscode.TextDocument,
      position: vscode.Position
    ): vscode.Hover | null {
      const line = document.lineAt(position.line).text;

      // import 문에서 패키지명 추출 시도
      const patterns = [
        // Python: import X, from X import
        /(?:import|from)\s+([\w][\w\-\.]*)/,
        // JS/TS: from 'X', require('X')
        /(?:from\s+|require\(\s*)['"]([^'"]+)['"]/,
      ];

      for (const pat of patterns) {
        const match = pat.exec(line);
        if (!match) { continue; }

        const pkg = match[1].split('/')[0].split('.')[0];
        const result = getResult(document.uri.toString(), pkg);
        if (!result) { continue; }

        // 패키지명 위치가 커서와 겹치는지 확인
        const idx = line.indexOf(match[1]);
        if (idx < 0) { continue; }
        if (position.character >= idx && position.character <= idx + match[1].length) {
          const range = new vscode.Range(
            position.line, idx,
            position.line, idx + match[1].length
          );
          return new vscode.Hover(buildHoverContent(result), range);
        }
      }

      return null;
    },
  };
}
