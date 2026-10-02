function getCookie(name) {
  const prefix = `${name}=`;
  const item = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

async function sendJson(url, method, payload) {
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });
  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (!response.ok) {
    throw new Error(data.detail || "The request could not be completed.");
  }
  return data;
}

function setMessage(element, text, kind = "") {
  if (!element) return;
  element.textContent = text;
  element.classList.toggle("is-error", kind === "error");
  element.classList.toggle("is-success", kind === "success");
}

function formatDate(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return `${new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(parsed)} UTC`;
}

const explanationButton = document.querySelector("#generate-explanation");
if (explanationButton) {
  explanationButton.addEventListener("click", async () => {
    const message = document.querySelector("#explanation-message");
    const label = explanationButton.querySelector("span");
    const originalLabel = label.textContent;
    explanationButton.disabled = true;
    label.textContent = "Generating…";
    setMessage(message, "Requesting an explanation based on the recorded signals.");
    try {
      const data = await sendJson(explanationButton.dataset.endpoint, "POST", {
        regenerate: explanationButton.dataset.regenerate === "true",
      });
      const copy = document.querySelector("#explanation-copy");
      const placeholder = document.querySelector("#explanation-placeholder");
      const meta = document.querySelector("#explanation-meta");
      copy.textContent = data.explanation;
      copy.classList.remove("is-hidden");
      if (placeholder) placeholder.classList.add("is-hidden");
      meta.textContent = `Generated ${formatDate(data.generated_at)}. For reviewer context only.`;
      meta.classList.remove("is-hidden");
      explanationButton.dataset.regenerate = "true";
      label.textContent = "Regenerate explanation";
      const configNotice = document.querySelector("#ai-config-notice");
      if (configNotice) configNotice.remove();
      setMessage(
        message,
        data.cached
          ? "Showing the saved explanation. No new AI request was made."
          : "Explanation saved to this order.",
        "success",
      );
    } catch (error) {
      label.textContent = originalLabel;
      setMessage(message, error.message, "error");
    } finally {
      explanationButton.disabled = false;
    }
  });
}

const statusForm = document.querySelector("#status-form");
if (statusForm) {
  statusForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = statusForm.querySelector('button[type="submit"]');
    const message = document.querySelector("#status-message");
    button.disabled = true;
    try {
      const formData = new FormData(statusForm);
      const data = await sendJson(statusForm.dataset.endpoint, "PATCH", {
        status: formData.get("status"),
      });
      setMessage(message, `Status updated to ${data.status_label}.`, "success");
    } catch (error) {
      setMessage(message, error.message, "error");
    } finally {
      button.disabled = false;
    }
  });
}

const noteForm = document.querySelector("#note-form");
if (noteForm) {
  noteForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = noteForm.querySelector('button[type="submit"]');
    const message = document.querySelector("#note-message");
    const textarea = noteForm.querySelector("textarea");
    const note = textarea.value.trim();
    if (note.length < 3) {
      setMessage(message, "Add a little more detail to the note.", "error");
      return;
    }
    button.disabled = true;
    try {
      const data = await sendJson(noteForm.dataset.endpoint, "POST", { note });
      const empty = document.querySelector("#notes-empty");
      if (empty) empty.remove();

      const article = document.createElement("article");
      article.className = "note-item";
      const meta = document.createElement("div");
      meta.className = "note-meta";
      const author = document.createElement("strong");
      author.textContent = data.created_by;
      const time = document.createElement("time");
      time.textContent = `${formatDate(data.created_at)}`;
      meta.append(author, time);
      const content = document.createElement("p");
      content.textContent = data.note;
      article.append(meta, content);
      document.querySelector("#notes-list").prepend(article);

      const count = document.querySelector("#note-count");
      count.textContent = String(Number(count.textContent) + 1);
      textarea.value = "";
      setMessage(message, "Investigation note added.", "success");
    } catch (error) {
      setMessage(message, error.message, "error");
    } finally {
      button.disabled = false;
    }
  });
}