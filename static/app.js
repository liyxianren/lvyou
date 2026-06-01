let pendingProposal = null;

function pad2(value) {
  return String(value).padStart(2, "0");
}

function parseDayDate(label) {
  const match = String(label || "").match(/(\d{1,2})\s*月\s*(\d{1,2})\s*日/);
  if (!match) return null;
  const year = Number(document.body.dataset.tripYear || new Date().getFullYear());
  return new Date(year, Number(match[1]) - 1, Number(match[2]));
}

function parseTimeToMinutes(value) {
  const match = String(value || "").match(/(\d{1,2}):(\d{2})/);
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  return hour * 60 + minute;
}

function parseTimeRange(value, nextStart) {
  const text = String(value || "");
  const matches = [...text.matchAll(/(\d{1,2}):(\d{2})/g)];
  if (!matches.length) return null;
  const start = Number(matches[0][1]) * 60 + Number(matches[0][2]);
  let end = null;
  if (matches[1]) {
    end = Number(matches[1][1]) * 60 + Number(matches[1][2]);
  } else if (Number.isFinite(nextStart)) {
    end = nextStart;
  } else {
    end = start + 45;
  }
  if (end <= start) end += 24 * 60;
  return { start, end };
}

function getEffectiveNow() {
  const params = new URLSearchParams(window.location.search);
  const overrideDate = params.get("date");
  const overrideTime = params.get("time");
  if (overrideDate || overrideTime) {
    const base = overrideDate ? new Date(`${overrideDate}T00:00:00`) : new Date();
    const minutes = parseTimeToMinutes(overrideTime || `${pad2(base.getHours())}:${pad2(base.getMinutes())}`) || 0;
    base.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
    return base;
  }
  return new Date();
}

function sameLocalDay(a, b) {
  return a && b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function dayDiff(from, to) {
  const a = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  const b = new Date(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((b - a) / 86400000);
}

function updateTimelineState() {
  const now = getEffectiveNow();
  document.querySelectorAll("[data-live-clock]").forEach((node) => {
    node.textContent = `${pad2(now.getHours())}:${pad2(now.getMinutes())}`;
  });

  document.querySelectorAll("[data-smart-timeline]").forEach((timeline) => {
    const dayDate = parseDayDate(timeline.dataset.dayDate);
    const items = [...timeline.querySelectorAll("[data-time]")];
    const starts = items.map((item) => parseTimeToMinutes(item.dataset.time));
    const ranges = items.map((item, index) => parseTimeRange(item.dataset.time, starts[index + 1]));
    const panels = document.querySelectorAll(`[data-live-panel][data-day-date="${timeline.dataset.dayDate}"]`);
    let activeIndex = -1;
    let nextIndex = 0;
    let summary = "时间线已载入。";

    items.forEach((item) => {
      item.classList.remove("is-done", "is-active", "is-next", "is-locked");
      item.querySelector("[data-status]").textContent = "待开始";
    });

    if (!dayDate) return;

    if (!sameLocalDay(now, dayDate)) {
      const diff = dayDiff(now, dayDate);
      if (diff > 0) {
        summary = `距离 ${timeline.dataset.dayDate} 还有 ${diff} 天；当天会自动按当前时间高亮。`;
        nextIndex = 0;
        items[0]?.classList.add("is-next");
        items[0]?.querySelector("[data-status]") && (items[0].querySelector("[data-status]").textContent = "第一步");
      } else {
        summary = `${timeline.dataset.dayDate} 已结束，时间线仅作复盘。`;
        items.forEach((item) => {
          item.classList.add("is-done");
          item.querySelector("[data-status]").textContent = "已过";
        });
      }
    } else {
      const nowMinutes = now.getHours() * 60 + now.getMinutes();
      activeIndex = ranges.findIndex((range) => range && nowMinutes >= range.start && nowMinutes < range.end);
      nextIndex = starts.findIndex((start) => Number.isFinite(start) && start > nowMinutes);

      items.forEach((item, index) => {
        const status = item.querySelector("[data-status]");
        const range = ranges[index];
        if (!range) {
          item.classList.add("is-locked");
          status.textContent = "未排时";
          return;
        }
        if (index === activeIndex) {
          item.classList.add("is-active");
          status.textContent = "现在";
        } else if (index === nextIndex) {
          item.classList.add("is-next");
          status.textContent = "下一步";
        } else if (nowMinutes >= range.end) {
          item.classList.add("is-done");
          status.textContent = "已过";
        } else {
          status.textContent = "待开始";
        }
      });

      if (activeIndex >= 0) {
        summary = `现在应该在：${items[activeIndex].dataset.title}`;
      } else if (nextIndex >= 0) {
        summary = `下一步：${items[nextIndex].dataset.title}`;
      } else {
        summary = "今天时间线已经走完，后面只剩收尾和休息。";
      }
    }

    panels.forEach((panel) => {
      panel.querySelector("[data-live-summary]").textContent = summary;
    });
    const action = document.querySelector("[data-current-action]");
    if (action && sameLocalDay(now, dayDate)) {
      const picked = activeIndex >= 0 ? items[activeIndex] : items[nextIndex];
      if (picked) action.textContent = picked.dataset.title;
    }
  });
}

updateTimelineState();
window.setInterval(updateTimelineState, 30000);

function activateVisualGuidePoint(root, id) {
  root.querySelectorAll("[data-guide-point]").forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.guidePoint === id ? "true" : "false");
  });
  root.querySelectorAll("[data-guide-detail]").forEach((detail) => {
    detail.hidden = detail.dataset.guideDetail !== id;
  });
}

document.querySelectorAll("[data-visual-guide]").forEach((root) => {
  const buttons = [...root.querySelectorAll("[data-guide-point]")];
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      activateVisualGuidePoint(root, button.dataset.guidePoint);
    });
  });
  const active = buttons.find((button) => button.getAttribute("aria-pressed") === "true") || buttons[0];
  if (active) activateVisualGuidePoint(root, active.dataset.guidePoint);
});

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || "请求失败");
  }
  return data;
}

async function postForm(url, formData) {
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || "请求失败");
  }
  return data;
}

function formToObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function formatCurrency(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? `¥${number}` : `¥${number.toFixed(2)}`;
}

function formatModelOperationPreview(operation, index) {
  const payload = operation.payload || {};
  const lines = [`${index + 1}. ${operation.label || "待保存记录"}`];

  if (operation.type === "add_expense") {
    lines.push(`日期：${payload.day_id || "未指定"}`);
    lines.push(`类别：${payload.category || "其他"}`);
    lines.push(`名称：${payload.title || "未命名支出"}`);
    lines.push(`金额：${formatCurrency(payload.amount)}`);
  } else if (operation.type === "add_booking") {
    lines.push(`日期：${payload.day_id || "未指定"}`);
    lines.push(`类型：${payload.type || "其他"}`);
    lines.push(`名称：${payload.name || "未命名预订"}`);
    lines.push(`状态：${payload.status || "待定"}`);
    lines.push(`价格：${formatCurrency(payload.price)}`);
  } else if (operation.type === "update_booking") {
    const changes = payload.changes || {};
    lines.push(`预订ID：${payload.booking_id || "未指定"}`);
    if (changes.status) lines.push(`状态：${changes.status}`);
    if (changes.price !== undefined) lines.push(`价格：${formatCurrency(changes.price)}`);
    if (changes.notes) lines.push(`备注：${changes.notes}`);
  } else if (operation.type === "update_supply") {
    const changes = payload.changes || {};
    lines.push(`物资ID：${payload.supply_id || "未指定"}`);
    if (changes.status) lines.push(`状态：${changes.status}`);
    if (changes.quantity !== undefined) lines.push(`数量：${changes.quantity}`);
    if (changes.notes) lines.push(`备注：${changes.notes}`);
  } else if (operation.type === "update_itinerary") {
    lines.push(`日期：${payload.day_id || "未指定"}`);
    lines.push(`项目：${payload.field || "未指定"}`);
    if (payload.value) lines.push(`内容：${payload.value}`);
    if (payload.title) lines.push(`标题：${payload.title}`);
    if (payload.time) lines.push(`时间：${payload.time}`);
    if (payload.detail) lines.push(`详情：${payload.detail}`);
  } else {
    lines.push(operation.label || "待保存调整");
  }

  if (payload.notes) lines.push(`备注：${payload.notes}`);
  return lines.join("\n");
}

function reloadSoon() {
  window.setTimeout(() => window.location.reload(), 250);
}

document.querySelector("[data-expense-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = formToObject(form);
  try {
    await postJson("/api/expenses", {
      action: "add",
      expense: {
        day_id: values.day_id,
        category: values.category,
        title: values.title,
        amount: Number(values.amount),
        notes: values.notes,
      },
    });
    reloadSoon();
  } catch (error) {
    alert(error.message);
  }
});

document.querySelector("[data-model-entry-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const box = document.querySelector("[data-model-proposal]");
  const actions = document.querySelector("[data-model-actions]");
  const formData = new FormData(form);
  formData.append("mode", form.dataset.mode);
  box.hidden = false;
  actions.hidden = true;
  box.textContent = "正在整理记录...";
  pendingProposal = null;

  try {
    const data = await postForm("/api/ai/parse-entry", formData);
    pendingProposal = data.proposal;
    const operations = pendingProposal.operations || [];
    const lines = [pendingProposal.summary || "解析结果"];
    operations.forEach((operation, index) => {
      lines.push(formatModelOperationPreview(operation, index));
    });
    box.textContent = lines.join("\n\n");
    actions.hidden = operations.length === 0;
  } catch (error) {
    box.textContent = error.message;
  }
});

document.querySelector("[data-confirm-model-proposal]")?.addEventListener("click", async () => {
  if (!pendingProposal || !pendingProposal.operations?.length) {
    alert("还没有可保存的记录。");
    return;
  }
  try {
    await postJson("/api/confirm-change", { proposal: pendingProposal });
    reloadSoon();
  } catch (error) {
    alert(error.message);
  }
});

document.querySelector("[data-clear-model-proposal]")?.addEventListener("click", () => {
  pendingProposal = null;
  document.querySelector("[data-model-proposal]").hidden = true;
  document.querySelector("[data-model-actions]").hidden = true;
});

document.querySelectorAll("[data-expense-tags] button").forEach((button) => {
  button.addEventListener("click", () => {
    const category = document.querySelector("[data-expense-category]");
    const title = document.querySelector("[data-expense-title]");
    if (category) category.value = button.dataset.category || "";
    if (title) title.value = button.dataset.title || "";
    title?.focus();
  });
});

document.querySelectorAll("[data-delete-expense]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!confirm("删除这笔支出？")) return;
    try {
      await postJson("/api/expenses", {
        action: "delete",
        id: button.dataset.deleteExpense,
      });
      reloadSoon();
    } catch (error) {
      alert(error.message);
    }
  });
});

document.querySelector("[data-booking-add-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = formToObject(form);
  try {
    await postJson("/api/bookings", {
      day_id: values.day_id,
      type: values.type,
      name: values.name,
      status: values.status,
      price: values.price || 0,
      notes: values.notes,
    });
    reloadSoon();
  } catch (error) {
    alert(error.message);
  }
});

document.querySelectorAll("[data-booking-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = formToObject(form);
    try {
      await postJson(`/api/bookings/${form.dataset.bookingForm}`, {
        status: values.status,
        price: values.price,
      });
      reloadSoon();
    } catch (error) {
      alert(error.message);
    }
  });
});

document.querySelectorAll("[data-delete-booking]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!confirm("删除这个预订项？")) return;
    try {
      await postJson(`/api/bookings/${button.dataset.deleteBooking}/delete`, {});
      reloadSoon();
    } catch (error) {
      alert(error.message);
    }
  });
});

document.querySelectorAll("[data-supply-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = formToObject(form);
    try {
      await postJson(`/api/supplies/${form.dataset.supplyForm}`, {
        status: values.status,
        quantity: values.quantity,
      });
      reloadSoon();
    } catch (error) {
      alert(error.message);
    }
  });
});

document.querySelectorAll("[data-supply-toggle]").forEach((input) => {
  input.addEventListener("change", async () => {
    const status = input.checked ? "已购买" : "待购买";
    input.disabled = true;
    try {
      await postJson(`/api/supplies/${input.dataset.supplyToggle}`, { status });
      const card = input.closest(".prep-check");
      const supplyCard = input.closest(".supply-card");
      card?.classList.toggle("is-checked", input.checked);
      supplyCard?.classList.toggle("is-checked", input.checked);
      const form = document.querySelector(`[data-supply-form="${input.dataset.supplyToggle}"]`);
      const select = form?.querySelector('select[name="status"]');
      if (select) select.value = status;
    } catch (error) {
      input.checked = !input.checked;
      alert(error.message);
    } finally {
      input.disabled = false;
    }
  });
});

document.querySelectorAll("[data-delete-supply]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!confirm("删除这个物资？")) return;
    try {
      await postJson(`/api/supplies/${button.dataset.deleteSupply}/delete`, {});
      reloadSoon();
    } catch (error) {
      alert(error.message);
    }
  });
});

document.querySelector("[data-ai-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = formToObject(form);
  const result = document.querySelector("#ai-result");
  const box = document.querySelector("[data-proposal-box]");
  box.textContent = "正在生成变更预览...";
  result.hidden = false;
  pendingProposal = null;

  try {
    const data = await postJson("/api/ai/propose", { message: values.message });
    pendingProposal = data.proposal;
    const operations = pendingProposal.operations || [];
    const lines = [pendingProposal.summary || "变更预览"];
    if (operations.length) {
      operations.forEach((operation, index) => {
        lines.push(formatModelOperationPreview(operation, index));
      });
    } else {
      lines.push("没有可写入的结构化修改。");
    }
    box.textContent = lines.join("\n\n");
  } catch (error) {
    box.textContent = error.message;
  }
});

document.querySelector("[data-confirm-proposal]")?.addEventListener("click", async () => {
  if (!pendingProposal || !pendingProposal.operations?.length) {
    alert("还没有可保存的调整。");
    return;
  }
  try {
    await postJson("/api/confirm-change", { proposal: pendingProposal });
    reloadSoon();
  } catch (error) {
    alert(error.message);
  }
});

document.querySelector("[data-clear-proposal]")?.addEventListener("click", () => {
  pendingProposal = null;
  document.querySelector("#ai-result").hidden = true;
});
