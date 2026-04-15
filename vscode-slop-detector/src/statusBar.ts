/**
 * 하단 상태바 — 스캔 상태 실시간 표시
 */

import * as vscode from 'vscode';

let statusBarItem: vscode.StatusBarItem;

/** 상태바 초기화 */
export function initStatusBar(context: vscode.ExtensionContext): vscode.StatusBarItem {
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusBarItem.command = 'slopsquatting.scanFile';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  setIdle();
  return statusBarItem;
}

/** 스캔 중 표시 */
export function setScanning(): void {
  statusBarItem.text = '$(loading~spin) Slop: Scanning...';
  statusBarItem.tooltip = 'Slopsquatting 검사 중...';
  statusBarItem.backgroundColor = undefined;
}

/** 결과 표시 */
export function setResult(total: number, risks: number): void {
  if (risks > 0) {
    statusBarItem.text = `$(warning) Slop: ${risks} risk${risks > 1 ? 's' : ''} / ${total} pkgs`;
    statusBarItem.tooltip = `${risks}개 위험 패키지 탐지됨 (총 ${total}개 검사)`;
    statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
  } else {
    statusBarItem.text = `$(check) Slop: ${total} pkgs checked`;
    statusBarItem.tooltip = `${total}개 패키지 검사 완료 — 위험 없음`;
    statusBarItem.backgroundColor = undefined;
  }
}

/** 유휴 상태 */
export function setIdle(): void {
  statusBarItem.text = '$(shield) Slop Detector';
  statusBarItem.tooltip = 'Slopsquatting Detector — 클릭하여 현재 파일 스캔';
  statusBarItem.backgroundColor = undefined;
}

/** API 오프라인 */
export function setOffline(): void {
  statusBarItem.text = '$(alert) Slop: API Offline';
  statusBarItem.tooltip = 'FastAPI 서버에 연결할 수 없습니다 (localhost:8001)';
  statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
}

/** 에러 표시 */
export function setError(msg: string): void {
  statusBarItem.text = `$(error) Slop: Error`;
  statusBarItem.tooltip = msg;
  statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
}
