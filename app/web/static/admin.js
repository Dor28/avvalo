/* Progressive enhancement for the trilingual founder editor. */
(function () {
  "use strict";

  document.querySelectorAll("[data-translation-editor]").forEach(function (editor) {
    var tabs = Array.from(editor.querySelectorAll("[data-translation-tab]"));
    var panels = Array.from(editor.querySelectorAll("[data-translation-panel]"));
    if (!tabs.length || !panels.length) {
      return;
    }

    var activate = function (language, focusTab) {
      tabs.forEach(function (tab) {
        var selected = tab.dataset.translationTab === language;
        tab.setAttribute("aria-selected", selected ? "true" : "false");
        tab.tabIndex = selected ? 0 : -1;
        if (selected && focusTab) {
          tab.focus();
        }
      });
      panels.forEach(function (panel) {
        panel.classList.toggle("active", panel.dataset.translationPanel === language);
      });
    };

    editor.classList.add("is-enhanced");
    var initiallySelected = tabs.find(function (tab) {
      return tab.getAttribute("aria-selected") === "true";
    });
    activate(initiallySelected ? initiallySelected.dataset.translationTab : "ru", false);

    tabs.forEach(function (tab, index) {
      tab.addEventListener("click", function () {
        activate(tab.dataset.translationTab, false);
      });
      tab.addEventListener("keydown", function (event) {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
          return;
        }
        event.preventDefault();
        var offset = event.key === "ArrowRight" ? 1 : -1;
        var next = tabs[(index + offset + tabs.length) % tabs.length];
        activate(next.dataset.translationTab, true);
      });
    });

    var form = editor.closest("form");
    if (form) {
      form.addEventListener(
        "invalid",
        function (event) {
          var panel = event.target.closest("[data-translation-panel]");
          if (panel) {
            activate(panel.dataset.translationPanel, false);
          }
        },
        true
      );
    }
  });
})();
