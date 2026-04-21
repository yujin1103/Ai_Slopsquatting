/**
 * Suggestion Provider — "혹시 ~~를 찾으셨나요?" 힌트 + 자동 교체
 *
 * 1. CodeLens: 경고 import 위에 "💡 혹시 'flask'를 찾으셨나요? 클릭하여 수정" 표시
 * 2. CodeAction: Ctrl+. 키로 Quick Fix 메뉴에서 교체 가능
 * 3. Command: 클릭/선택 시 에디터에서 텍스트 자동 교체
 */

import * as vscode from 'vscode';
import { ParsedImport, PackageResult, RISK_ORDER } from './types';

// 문서별 저장: <uri, { imports, results }>
interface SuggestData {
  imports: ParsedImport[];
  results: Map<string, PackageResult>;
}
const suggestionStore = new Map<string, SuggestData>();

/** 교체 가능한 케이스인지 판단 */
function canSuggestReplacement(result: PackageResult): boolean {
  // 등급이 위험 수준이고 + 가까운 패키지가 존재 + 편집거리 ≤ 4
  const order = RISK_ORDER[result.level] ?? 0;
  if (order < 1) return false; // LOW는 제안 안 함
  if (!result.closest || !result.closest.trim()) return false;
  if (result.closest === result.package) return false;
  if (result.min_dist > 4) return false;
  return true;
}

/** 문서의 제안 데이터 저장 (extension.ts에서 호출) */
export function storeSuggestions(
  uri: string,
  imports: ParsedImport[],
  results: PackageResult[]
): void {
  const map = new Map<string, PackageResult>();
  for (const r of results) {
    map.set(r.package, r);
  }
  suggestionStore.set(uri, { imports, results: map });
}

/** 문서 닫힘 시 정리 */
export function clearSuggestions(uri: string): void {
  suggestionStore.delete(uri);
}

// ─── CodeLens Provider ──────────────────────────────────────

export class SuggestCodeLensProvider implements vscode.CodeLensProvider {
  private _onDidChangeCodeLenses = new vscode.EventEmitter<void>();
  readonly onDidChangeCodeLenses: vscode.Event<void> = this._onDidChangeCodeLenses.event;

  /** 외부에서 데이터 갱신 시 CodeLens 다시 그리기 트리거 */
  refresh(): void {
    this._onDidChangeCodeLenses.fire();
  }

  provideCodeLenses(
    document: vscode.TextDocument,
    _token: vscode.CancellationToken
  ): vscode.CodeLens[] {
    const data = suggestionStore.get(document.uri.toString());
    if (!data) return [];

    const lenses: vscode.CodeLens[] = [];
    for (const imp of data.imports) {
      const result = data.results.get(imp.packageName);
      if (!result || !canSuggestReplacement(result)) continue;

      const range = new vscode.Range(
        new vscode.Position(imp.line, imp.startChar),
        new vscode.Position(imp.line, imp.endChar)
      );

      const lens = new vscode.CodeLens(range, {
        title: `💡 혹시 '${result.closest}'를 찾으셨나요? (편집거리 ${result.min_dist}) — 클릭하여 수정`,
        command: 'slopsquatting.replacePackage',
        arguments: [document.uri, imp, result.closest],
      });
      lenses.push(lens);
    }

    return lenses;
  }
}

// ─── CodeAction Provider (Quick Fix) ────────────────────────

export class SuggestCodeActionProvider implements vscode.CodeActionProvider {
  static readonly providedCodeActionKinds = [vscode.CodeActionKind.QuickFix];

  provideCodeActions(
    document: vscode.TextDocument,
    range: vscode.Range | vscode.Selection,
    context: vscode.CodeActionContext,
    _token: vscode.CancellationToken
  ): vscode.CodeAction[] {
    const data = suggestionStore.get(document.uri.toString());
    if (!data) return [];

    const actions: vscode.CodeAction[] = [];

    // 진단(diagnostic)이 있는 위치에서 트리거된 경우만
    for (const diag of context.diagnostics) {
      if (diag.source !== 'slopsquatting') continue;

      // 해당 라인의 import 찾기
      const imp = data.imports.find(
        (i) =>
          i.line === diag.range.start.line &&
          i.startChar <= diag.range.start.character &&
          diag.range.end.character <= i.endChar
      );
      if (!imp) continue;

      const result = data.results.get(imp.packageName);
      if (!result || !canSuggestReplacement(result)) continue;

      // Quick Fix: 교체
      const replaceAction = new vscode.CodeAction(
        `'${imp.packageName}' → '${result.closest}'로 교체`,
        vscode.CodeActionKind.QuickFix
      );
      replaceAction.diagnostics = [diag];
      replaceAction.command = {
        command: 'slopsquatting.replacePackage',
        title: 'Replace package',
        arguments: [document.uri, imp, result.closest],
      };
      replaceAction.isPreferred = true; // Ctrl+. 시 자동 선택
      actions.push(replaceAction);

      // 추가 정보: 상세 Hover로 이동
      const infoAction = new vscode.CodeAction(
        `'${imp.packageName}' 상세 정보 보기`,
        vscode.CodeActionKind.QuickFix
      );
      infoAction.diagnostics = [diag];
      infoAction.command = {
        command: 'editor.action.showHover',
        title: 'Show hover',
      };
      actions.push(infoAction);
    }

    return actions;
  }
}

// ─── Replace Command 구현 ───────────────────────────────────

export async function executeReplace(
  uri: vscode.Uri,
  imp: ParsedImport,
  newPackage: string
): Promise<void> {
  const doc = await vscode.workspace.openTextDocument(uri);
  const editor = await vscode.window.showTextDocument(doc);

  const range = new vscode.Range(
    new vscode.Position(imp.line, imp.startChar),
    new vscode.Position(imp.line, imp.endChar)
  );

  const oldText = doc.getText(range);
  const success = await editor.edit((edit) => {
    edit.replace(range, newPackage);
  });

  if (success) {
    vscode.window.showInformationMessage(
      `Slopsquatting: '${oldText}' → '${newPackage}' 교체 완료`
    );
  } else {
    vscode.window.showErrorMessage('교체 실패');
  }
}
