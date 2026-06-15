const state = {
  raw: {},
  currentView: "cards",
  busy: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const queryInput = $("#queryInput");
const categoryInput = $("#categoryInput");
const maxPriceInput = $("#maxPriceInput");
const topKInput = $("#topKInput");
const sessionInput = $("#sessionInput");
const statusPill = $("#statusPill");
const traceList = $("#traceList");
const answerBox = $("#answerBox");
const cardsView = $("#cardsView");
const jsonView = $("#jsonView");

function iconRefresh() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function setBusy(isBusy, label = "运行中") {
  state.busy = isBusy;
  statusPill.textContent = isBusy ? label : "已就绪";
  statusPill.className = `status-pill ${isBusy ? "running" : "done"}`;
  ["recommendBtn", "searchBtn", "chatBtn", "streamBtn"].forEach((id) => {
    $(`#${id}`).disabled = isBusy;
  });
}

function setError(message) {
  statusPill.textContent = "请求失败";
  statusPill.className = "status-pill error";
  answerBox.innerHTML = `<span class="muted">${escapeHtml(message)}</span>`;
}

function payloadBase() {
  const topK = Math.max(1, Math.min(10, Number(topKInput.value || 3)));
  const maxPrice = maxPriceInput.value ? Number(maxPriceInput.value) : null;
  const payload = {
    query: queryInput.value.trim(),
    top_k: topK,
  };
  if (categoryInput.value) payload.category = categoryInput.value;
  if (maxPrice) payload.max_price = maxPrice;
  return payload;
}

function chatPayload() {
  return {
    session_id: sessionInput.value.trim() || "interview-demo",
    message: queryInput.value.trim(),
    top_k: Math.max(1, Math.min(10, Number(topKInput.value || 3))),
  };
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function updateNodes(trace = []) {
  const doneNodes = new Set(trace.map((item) => item.node));
  $$(".flow-node").forEach((node) => {
    const name = node.dataset.node;
    node.classList.toggle("done", doneNodes.has(name));
    node.classList.remove("active");
  });
  const last = trace.at(-1)?.node;
  if (last) {
    const activeNode = $(`.flow-node[data-node="${last}"]`);
    if (activeNode) activeNode.classList.add("active");
  }
}

function renderTrace(trace = []) {
  if (!trace.length) {
    traceList.innerHTML = `<div class="trace-item"><h4>等待执行</h4><code>暂无 trace</code></div>`;
    updateNodes([]);
    return;
  }
  traceList.innerHTML = trace
    .map((item, index) => {
      const detail = { ...item };
      delete detail.node;
      return `
        <article class="trace-item">
          <h4>${index + 1}. ${escapeHtml(item.node)}</h4>
          <code>${escapeHtml(JSON.stringify(detail, null, 2))}</code>
        </article>
      `;
    })
    .join("");
  updateNodes(trace);
}

function normalizeRecommendations(raw) {
  if (Array.isArray(raw.recommendations)) return raw.recommendations;
  if (Array.isArray(raw.matches)) {
    return raw.matches.map((match) => ({
      product_id: match.product.id,
      title: match.product.title,
      price: match.product.price,
      score: match.score,
      reasons: match.reasons || [],
      caveats: [`召回来源：${match.source}`],
    }));
  }
  return [];
}

function renderCards(items) {
  if (!items.length) {
    cardsView.innerHTML = `
      <div class="empty-state">
        <i data-lucide="shopping-bag"></i>
        <p>暂无商品结果</p>
      </div>
    `;
    iconRefresh();
    return;
  }

  cardsView.innerHTML = items
    .map((item, index) => {
      const score = Math.max(0, Math.min(1, Number(item.score || 0)));
      const reasons = (item.reasons || []).map((reason) => `<span class="tag">${escapeHtml(reason)}</span>`).join("");
      const caveats = (item.caveats || []).map((text) => `<span class="tag warning">${escapeHtml(text)}</span>`).join("");
      return `
        <article class="product-card">
          <div class="product-top">
            <div>
              <h3>${index + 1}. ${escapeHtml(item.title)}</h3>
              <div class="product-id">${escapeHtml(item.product_id || "match")}</div>
            </div>
            <div class="price">￥${Number(item.price || 0).toLocaleString("zh-CN")}</div>
          </div>
          <div class="score-row">
            <div class="score-bar"><span style="width:${Math.round(score * 100)}%"></span></div>
            <div class="score-text">${Number(item.score || 0).toFixed(3)}</div>
          </div>
          <div class="tag-list">${reasons}${caveats}</div>
        </article>
      `;
    })
    .join("");
}

function render(raw, options = {}) {
  state.raw = raw || {};
  const recommendations = normalizeRecommendations(state.raw);
  const answer = options.answer || state.raw.answer || state.raw.clarification_question || state.raw.query || "";
  answerBox.innerHTML = answer
    ? escapeHtml(answer)
    : `<span class="muted">请求完成，但当前接口没有返回自然语言回复。</span>`;
  renderCards(recommendations);
  renderTrace(state.raw.trace || []);
  jsonView.textContent = JSON.stringify(state.raw, null, 2);
  iconRefresh();
}

async function runRecommend() {
  if (!queryInput.value.trim()) return setError("请先输入用户需求。");
  setBusy(true, "推荐中");
  try {
    const raw = await postJson("/recommend", payloadBase());
    render(raw, { answer: raw.needs_clarification ? raw.clarification_question : `已生成 ${raw.recommendations.length} 个推荐结果。` });
    setBusy(false);
  } catch (error) {
    setError(error.message);
  }
}

async function runSearch() {
  if (!queryInput.value.trim()) return setError("请先输入检索需求。");
  setBusy(true, "检索中");
  try {
    const raw = await postJson("/rag/search", payloadBase());
    render(raw, { answer: `混合检索返回 ${raw.matches.length} 个候选商品。` });
    setBusy(false);
  } catch (error) {
    setError(error.message);
  }
}

async function runChat() {
  if (!queryInput.value.trim()) return setError("请先输入对话内容。");
  setBusy(true, "对话中");
  try {
    const raw = await postJson("/chat", chatPayload());
    render(raw);
    setBusy(false);
  } catch (error) {
    setError(error.message);
  }
}

function parseSseBlock(block) {
  const event = block.match(/^event:\s*(.+)$/m)?.[1];
  const data = block.match(/^data:\s*(.*)$/m)?.[1];
  if (!event || data === undefined) return null;
  try {
    return { event, data: JSON.parse(data) };
  } catch {
    return { event, data };
  }
}

async function runStream() {
  if (!queryInput.value.trim()) return setError("请先输入对话内容。");
  setBusy(true, "流式输出");
  answerBox.textContent = "";
  cardsView.innerHTML = `
    <div class="empty-state">
      <i data-lucide="radio"></i>
      <p>正在接收 SSE 事件</p>
    </div>
  `;
  iconRefresh();

  const response = await fetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(chatPayload()),
  });

  if (!response.ok || !response.body) {
    setError(`${response.status} ${response.statusText}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  const raw = { session_id: sessionInput.value.trim(), trace: [], recommendations: [], stream: [] };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";
      for (const block of blocks) {
        const event = parseSseBlock(block);
        if (!event) continue;
        raw.stream.push(event);
        if (event.event === "trace") {
          raw.trace = event.data;
          renderTrace(raw.trace);
        }
        if (event.event === "recommendations") {
          raw.recommendations = event.data;
          renderCards(raw.recommendations);
        }
        if (event.event === "token") {
          answer += event.data.text;
          answerBox.textContent = answer;
        }
      }
    }
    raw.answer = answer;
    state.raw = raw;
    jsonView.textContent = JSON.stringify(raw, null, 2);
    setBusy(false);
  } catch (error) {
    setError(error.message);
  }
}

async function runHealth() {
  setBusy(true, "检查中");
  try {
    const response = await fetch("/health");
    const raw = await response.json();
    render({ ...raw, trace: [{ node: "health", status: raw.status, version: raw.version }] }, { answer: `服务状态：${raw.status}，版本：${raw.version}` });
    setBusy(false);
  } catch (error) {
    setError(error.message);
  }
}

function clearAll() {
  state.raw = {};
  answerBox.innerHTML = `<span class="muted">运行一次推荐或对话后展示结果。</span>`;
  jsonView.textContent = "{}";
  renderTrace([]);
  renderCards([]);
  statusPill.textContent = "待运行";
  statusPill.className = "status-pill";
}

async function copyJson() {
  await navigator.clipboard.writeText(JSON.stringify(state.raw, null, 2));
  statusPill.textContent = "已复制";
  statusPill.className = "status-pill done";
}

function setView(view) {
  state.currentView = view;
  $$(".segment").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  cardsView.classList.toggle("hidden", view !== "cards");
  jsonView.classList.toggle("hidden", view !== "json");
}

function bindEvents() {
  $("#recommendBtn").addEventListener("click", runRecommend);
  $("#searchBtn").addEventListener("click", runSearch);
  $("#chatBtn").addEventListener("click", runChat);
  $("#streamBtn").addEventListener("click", runStream);
  $("#healthBtn").addEventListener("click", runHealth);
  $("#clearBtn").addEventListener("click", clearAll);
  $("#copyBtn").addEventListener("click", copyJson);
  $("#toggleJsonBtn").addEventListener("click", () => setView(state.currentView === "json" ? "cards" : "json"));
  $$(".segment").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
  $$(".sample-chip").forEach((button) =>
    button.addEventListener("click", () => {
      queryInput.value = button.dataset.query;
      categoryInput.value = "";
      maxPriceInput.value = "";
    }),
  );
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  renderTrace([]);
  iconRefresh();
});
