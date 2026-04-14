/**
 * popup.js
 * 팝업 UI의 상태 업데이트 및 통계 표시를 담당합니다.
 */

document.addEventListener('DOMContentLoaded', () => {
  const dot = document.getElementById("dot");
  const text = document.getElementById("status-text");

  // 1. 서버(API) 연결 상태 확인
  chrome.runtime.sendMessage({ type: "HEALTH_CHECK" }, (res) => {
    if (res?.ok) {
      dot.className = "dot ok";
      text.textContent = "로컬 분석 엔진 연결됨 ✓";
    } else {
      dot.className = "dot error";
      text.textContent = "분석 엔진 오프라인 (Docker 확인)";
    }
  });

  // 2. background.js로부터 누적된 위협 통계 데이터 가져오기
  chrome.runtime.sendMessage({ type: "GET_STATS" }, (stats) => {
    if (stats) {
      document.getElementById("stat-safe").textContent = stats.safe || 0;
      document.getElementById("stat-sus").textContent = stats.suspicious || 0;
      document.getElementById("stat-mal").textContent = stats.malicious || 0;
    }
  });
});