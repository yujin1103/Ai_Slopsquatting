const dot  = document.getElementById("dot");
const text = document.getElementById("status-text");

chrome.runtime.sendMessage({ type: "HEALTH_CHECK" }, (res) => {
  if (res?.ok) {
    dot.classList.add("ok");
    text.textContent = "API 서버 연결됨 ✓";
  } else {
    dot.classList.add("error");
    text.textContent = "API 서버 오프라인 — Docker를 실행하세요";
  }
});
