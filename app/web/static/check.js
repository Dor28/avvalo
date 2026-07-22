/* Progressive enhancement for the shared check form.
 *
 * Everything here is optional polish on top of a form that already works
 * without JavaScript: the counter, the file readout and the pre-flight empty
 * check only save the user a round trip. All user-facing strings arrive as
 * data-* attributes so this file stays language-agnostic.
 */
(function () {
  "use strict";

  var REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function resultBlock(title, message) {
    var block = document.createElement("div");
    block.className = "result-block error";
    block.setAttribute("role", "alert");
    var icon = document.createElement("span");
    icon.className = "result-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "!";
    block.appendChild(icon);
    var copy = document.createElement("div");
    var strong = document.createElement("strong");
    strong.textContent = title;
    copy.appendChild(strong);
    if (message) {
      var paragraph = document.createElement("p");
      paragraph.textContent = message;
      copy.appendChild(paragraph);
    }
    block.appendChild(copy);
    return block;
  }

  function setupCounter(form) {
    var textarea = form.querySelector("textarea[name='text']");
    var counter = form.querySelector(".char-counter");
    if (!textarea || !counter) {
      return;
    }
    var value = counter.querySelector(".char-counter-value");
    var max = parseInt(counter.dataset.max, 10) || 0;
    var update = function () {
      var length = textarea.value.length;
      value.textContent = String(length);
      // Stay out of the way until the limit is actually in sight.
      counter.hidden = length === 0;
      counter.classList.toggle("is-near-limit", max > 0 && length > max * 0.9);
    };
    textarea.addEventListener("input", update);
    update();
  }

  function setupFileField(form) {
    var input = form.querySelector(".file-input");
    var chosen = form.querySelector(".file-chosen");
    if (!input || !chosen) {
      return;
    }
    var name = chosen.querySelector(".file-chosen-name");
    var clear = chosen.querySelector(".file-clear");
    var render = function () {
      var file = input.files && input.files[0];
      chosen.hidden = !file;
      name.textContent = file ? file.name : "";
    };
    input.addEventListener("change", render);
    clear.addEventListener("click", function () {
      input.value = "";
      render();
      input.focus();
    });
    render();
  }

  function showBlock(result, block) {
    result.innerHTML = "";
    result.appendChild(block);
  }

  function setupSubmit(form) {
    var result = document.getElementById("result");
    if (!result) {
      return;
    }
    var button = form.querySelector("button[type='submit']");
    var label = button.querySelector(".submit-label");
    var textarea = form.querySelector("textarea[name='text']");
    var fileInput = form.querySelector("input[type='file']");
    var consent = form.querySelector("input[name='consent']");

    if (textarea) {
      textarea.addEventListener("input", function () {
        textarea.removeAttribute("aria-invalid");
      });
    }
    if (consent) {
      consent.addEventListener("change", function () {
        consent.removeAttribute("aria-invalid");
      });
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();

      var hasText = textarea && textarea.value.trim().length > 0;
      var hasImage = fileInput && fileInput.files && fileInput.files.length > 0;
      if (!hasText && !hasImage) {
        showBlock(result, resultBlock(form.dataset.emptyError, ""));
        if (textarea) {
          textarea.setAttribute("aria-invalid", "true");
          textarea.focus();
        }
        return;
      }

      if (consent && !consent.checked) {
        showBlock(result, resultBlock(form.dataset.consentError, ""));
        consent.setAttribute("aria-invalid", "true");
        consent.focus();
        return;
      }

      var idleLabel = label.textContent;
      button.disabled = true;
      button.classList.add("is-busy");
      label.textContent = form.dataset.busyLabel;
      result.setAttribute("aria-busy", "true");
      result.innerHTML = "";
      result.classList.add("is-loading");

      fetch(form.action, { method: "POST", body: new FormData(form) })
        .then(function (response) {
          return response.text();
        })
        .then(function (html) {
          result.innerHTML = html;
          if (result.innerHTML.trim()) {
            result.scrollIntoView({
              behavior: REDUCED_MOTION ? "auto" : "smooth",
              block: "start",
            });
          }
        })
        .catch(function () {
          showBlock(result, resultBlock(form.dataset.errorTitle, ""));
        })
        .finally(function () {
          button.disabled = false;
          button.classList.remove("is-busy");
          label.textContent = idleLabel;
          result.setAttribute("aria-busy", "false");
          result.classList.remove("is-loading");
        });
    });
  }

  document.querySelectorAll(".check-form").forEach(function (form) {
    setupCounter(form);
    setupFileField(form);
    setupSubmit(form);
  });
})();
