/**
 * Slopsquatting Detector — VS Code Extension 진입점
 *
 * 실시간 타이핑 + 저장 시 + 파일 열기 + 수동 명령어로
 * import 문의 패키지를 파싱하고, FastAPI 백엔드로 위험도를 검증하여
 * 인라인 경고를 표시합니다.
 */

import * as vscode from 'vscode';
import { parseImports } from './parser';
import { analyzePackages, checkHealth, clearCache } from './apiClient';
import { initDiagnostics, updateDiagnostics, clearDiagnostics } from './diagnostics';
import { createHoverProvider, storeResults } from './hoverProvider';
import { initStatusBar, setScanning, setResult, setIdle, setOffline, setError } from './statusBar';

let debounceTimer: NodeJS.Timeout | undefined;

/** 문서 스캔 실행 */
async function scanDocument(document: vscode.TextDocument): Promise<void> {
  const config = vscode.workspace.getConfiguration('slopsquatting');
  const apiUrl = config.get<string>('apiUrl', 'http://localhost:8001');
  const minLevel = config.get<string>('minRiskLevel', 'MEDIUM');

  // 지원 언어 확인
  const supported = ['python', 'javascript', 'typescript', 'javascriptreact', 'typescriptreact', 'json'];
  if (!supported.includes(document.languageId)) {
    return;
  }

  // JSON은 package.json만
  if (document.languageId === 'json' && !document.fileName.endsWith('package.json')) {
    return;
  }

  // 1. Import 파싱
  const imports = parseImports(document.getText(), document.languageId);
  if (imports.length === 0) {
    clearDiagnostics(document.uri);
    setIdle();
    return;
  }

  // 2. API 호출
  setScanning();
  const packageNames = imports.map((imp) => imp.packageName);

  try {
    const results = await analyzePackages(packageNames, apiUrl);

    // 3. 결과 저장 (HoverProvider용)
    storeResults(document.uri.toString(), results);

    // 4. Diagnostics 업데이트
    const { total, risks } = updateDiagnostics(document, imports, results, minLevel);

    // 5. 상태바 업데이트
    setResult(total, risks);
  } catch (err: any) {
    const isConnectionError =
      err?.code === 'ECONNREFUSED' ||
      err?.message?.includes('ECONNREFUSED') ||
      err?.message?.includes('timeout');

    if (isConnectionError) {
      setOffline();
    } else {
      setError(err?.message || 'Unknown error');
    }
  }
}

/** 디바운스된 스캔 */
function debouncedScan(document: vscode.TextDocument): void {
  const config = vscode.workspace.getConfiguration('slopsquatting');
  const debounceMs = config.get<number>('debounceMs', 1500);

  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }

  debounceTimer = setTimeout(() => {
    scanDocument(document);
  }, debounceMs);
}

/** Extension 활성화 */
export function activate(context: vscode.ExtensionContext): void {
  console.log('[Slopsquatting] Extension activated');

  // Diagnostics 초기화
  initDiagnostics(context);

  // 상태바 초기화
  initStatusBar(context);

  // Hover Provider 등록
  const hoverProvider = createHoverProvider();
  const languages = ['python', 'javascript', 'typescript', 'javascriptreact', 'typescriptreact', 'json'];
  for (const lang of languages) {
    context.subscriptions.push(
      vscode.languages.registerHoverProvider({ language: lang }, hoverProvider)
    );
  }

  // ─── 이벤트 리스너 ──────────────────────────────

  // 실시간 타이핑
  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((event) => {
      const config = vscode.workspace.getConfiguration('slopsquatting');
      if (config.get<boolean>('enableRealtime', true)) {
        debouncedScan(event.document);
      }
    })
  );

  // 파일 저장 시
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((document) => {
      scanDocument(document);
    })
  );

  // 파일 열기
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((document) => {
      scanDocument(document);
    })
  );

  // 에디터 전환
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        scanDocument(editor.document);
      } else {
        setIdle();
      }
    })
  );

  // 파일 닫기 — diagnostics 정리
  context.subscriptions.push(
    vscode.workspace.onDidCloseTextDocument((document) => {
      clearDiagnostics(document.uri);
    })
  );

  // ─── 명령어 ──────────────────────────────────────

  // 수동 스캔
  context.subscriptions.push(
    vscode.commands.registerCommand('slopsquatting.scanFile', () => {
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        clearCache();
        scanDocument(editor.document);
        vscode.window.showInformationMessage('Slopsquatting: 스캔 시작');
      } else {
        vscode.window.showWarningMessage('열린 파일이 없습니다');
      }
    })
  );

  // API 상태 확인
  context.subscriptions.push(
    vscode.commands.registerCommand('slopsquatting.checkHealth', async () => {
      const config = vscode.workspace.getConfiguration('slopsquatting');
      const apiUrl = config.get<string>('apiUrl', 'http://localhost:8001');
      const ok = await checkHealth(apiUrl);
      if (ok) {
        vscode.window.showInformationMessage(`Slopsquatting API: ✅ 연결됨 (${apiUrl})`);
      } else {
        vscode.window.showErrorMessage(`Slopsquatting API: ❌ 연결 실패 (${apiUrl})`);
        setOffline();
      }
    })
  );

  // ─── 초기 스캔 ──────────────────────────────────
  if (vscode.window.activeTextEditor) {
    scanDocument(vscode.window.activeTextEditor.document);
  }
}

/** Extension 비활성화 */
export function deactivate(): void {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  clearCache();
  console.log('[Slopsquatting] Extension deactivated');
}
