"use strict";
// Renders one validated intent card. It does not fetch, cache, or call a model.
(function () {
  function text(value) {
    return typeof value === "string" ? value.trim() : "";
  }
  function validChoice(section) {
    if (!section || section.kind !== "choice" || !text(section.title) || text(section.title).length > 24) return false;
    if (!Array.isArray(section.options) || section.options.length < 2 || section.options.length > 4) return false;
    let total = 0;
    for (const option of section.options) {
      const label = text(option && option.label);
      const percent = option && option.percent;
      if (!label || label.length > 16 || typeof percent !== "number" || !Number.isInteger(percent) ||
          percent < 0 || percent > 100) return false;
      total += percent;
    }
    return total === 100;
  }
  function validMeter(section) {
    return !!section && section.kind === "meter" && text(section.title).length > 0 &&
      text(section.title).length <= 12 && Number.isInteger(section.value) &&
      section.value >= 0 && section.value <= 10 && section.max === 10;
  }
  function validAdvice(section) {
    const advice = text(section && section.text);
    return !!section && section.kind === "advice" && advice.length > 0 && advice.length <= 40;
  }
  function valid(card, id, messageText) {
    if (!card || typeof card !== "object" || Array.isArray(card)) return false;
    if (card.id !== id || card.text !== messageText) return false;
    if (!Array.isArray(card.sections) || card.sections.length < 1 || card.sections.length > 4) return false;
    let meters = 0;
    let advice = 0;
    for (const section of card.sections) {
      if (validChoice(section)) continue;
      if (validMeter(section)) {
        meters += 1;
        continue;
      }
      if (validAdvice(section)) {
        advice += 1;
        continue;
      }
      return false;
    }
    return meters <= 1 && advice <= 1;
  }
  function create(dependencies) {
    const element = dependencies.element;
    function render(card) {
      const root = element("div", "intent-card");
      const head = element("div", "intent-card-head");
      head.appendChild(element("span", "intent-card-title", "[回复指南]"));
      head.appendChild(element("span", "intent-card-note", "模型推测"));
      root.appendChild(head);
      for (const section of card.sections) {
        if (section.kind === "choice") {
          const block = element("div", "intent-card-section");
          block.appendChild(element("div", "intent-card-question", section.title.trim()));
          for (const option of section.options) {
            const row = element("div", "intent-card-option");
            row.appendChild(element("span", "intent-card-option-label", option.label.trim()));
            row.appendChild(element("span", "intent-card-option-percent", option.percent + "%"));
            block.appendChild(row);
          }
          root.appendChild(block);
        } else if (section.kind === "meter") {
          root.appendChild(element("div", "intent-card-meter",
            section.title.trim() + " " + section.value + "/" + section.max));
        } else if (section.kind === "advice") {
          root.appendChild(element("div", "intent-card-advice", section.text.trim()));
        }
      }
      return root;
    }
    return { render };
  }
  window.IntentCards = Object.freeze({ create, valid });
})();
