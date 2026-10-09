import assert from "node:assert/strict";
import { it } from "node:test";

import { analyzeIntentCards, intentCardSystem, type IntentCardInput } from "../electron/intent-cards";
import { ModelConnectorError, type GenerationRequest, type ModelConfig } from "../electron/model-connectors";

const config: ModelConfig = {
  protocol: "chat_completions", baseUrl: "https://example.invalid/v1",
  model: "synthetic-model", apiKey: "synthetic-key",
};

const input: IntentCardInput = {
  style: "dating",
  messages: [
    { id: "a", sender: "SELF", text: "昨天说好周末吃饭。" },
    { id: "b", sender: "OTHER", text: "你今天是不是又忘了？" },
    { id: "c", sender: "SELF", text: "记得，我想说完整一点。" },
    { id: "d", sender: "OTHER", text: "所以呢？" },
  ],
  targetIds: ["b", "d"],
};

function choice(title: string, options: Array<[string, number]>) {
  return {
    kind: "choice", title,
    options: options.map(([label, percent]) => ({ label, percent })),
  };
}

function card(id: string, sections: unknown[]) {
  return { id, sections };
}

function fake(text: string, capture?: (request: GenerationRequest) => void) {
  return async (_config: ModelConfig, request: GenerationRequest) => {
    capture?.(request);
    return { text, usage: { inputTokens: 20, outputTokens: 30 } };
  };
}

const datingCards = {
  items: [
    card("t2", [
      choice("她在确认你是否在乎", [["是", 18], ["不是", 82]]),
      { kind: "meter", title: "危险等级", value: 7, max: 10 },
      { kind: "advice", text: "先回应她的原话，不要转开话题。" },
    ]),
    card("t4", [
      choice("她现在需要什么", [["道歉", 21], ["行动", 74], ["解释", 5]]),
      { kind: "advice", text: "给出一个具体安排，然后停住。" },
    ]),
  ],
};

it("returns dating cards in target order and asks for JSON", async () => {
  let request: GenerationRequest | undefined;
  const result = await analyzeIntentCards(config, input, fake(JSON.stringify(datingCards), (value) => {
    request = value;
  }));
  assert.deepEqual(result.cards.map((item) => item.id), ["b", "d"]);
  assert.equal(result.cards[0]!.sections[1]!.kind, "meter");
  assert.equal(result.cards[1]!.sections.length, 2);
  assert.equal(request!.jsonMode, true);
  assert.match(request!.system, /危险等级/u);
  assert.doesNotMatch(request!.system, /你今天是不是又忘了/u);
  assert.match(request!.prompt, /CHAT_BATCH_JSON/u);
  assert.match(request!.prompt, /你今天是不是又忘了/u);
  const payload = JSON.parse(request!.prompt.slice(request!.prompt.indexOf("\n") + 1));
  assert.deepEqual(payload.targetIds, ["t2", "t4"]);
  assert.equal(payload.messages[1].text, "你今天是不是又忘了？");
});

it("rejects percentages that do not add up to 100", async () => {
  const broken = {
    items: [card("t2", [choice("她在确认", [["是", 40], ["不是", 50]])])],
  };
  await assert.rejects(
    () => analyzeIntentCards(config, { ...input, targetIds: ["b"] }, fake(JSON.stringify(broken))),
    (error: unknown) => error instanceof ModelConnectorError && error.code === "invalid-output",
  );
});

it("rejects a danger meter outside dating mode", async () => {
  const metered = {
    items: [card("t2", [
      choice("这句在做什么", [["询问", 70], ["催促", 30]]),
      { kind: "meter", title: "危险等级", value: 9, max: 10 },
    ])],
  };
  await assert.rejects(
    () => analyzeIntentCards(config, { ...input, style: "general", targetIds: ["b"] }, fake(JSON.stringify(metered))),
    (error: unknown) => error instanceof ModelConnectorError && error.code === "invalid-output",
  );
  assert.match(intentCardSystem("general"), /不要输出 kind 为 meter/u);
  assert.doesNotMatch(intentCardSystem("general"), /可以有最多一个 meter/u);
});

it("rejects advice that is longer than one short sentence", async () => {
  const advice = "字".repeat(41);
  const verbose = {
    items: [card("t2", [
      choice("这句在做什么", [["询问", 60], ["分享", 40]]),
      { kind: "advice", text: advice },
    ])],
  };
  assert.equal([...advice].length, 41);
  await assert.rejects(
    () => analyzeIntentCards(config, { ...input, style: "general", targetIds: ["b"] }, fake(JSON.stringify(verbose))),
    (error: unknown) => error instanceof ModelConnectorError && error.code === "invalid-output",
  );
});

it("rejects an extra field on a card", async () => {
  const extra = {
    items: [{
      id: "t2",
      note: "多余",
      sections: [choice("这句在做什么", [["询问", 60], ["分享", 40]])],
    }],
  };
  await assert.rejects(
    () => analyzeIntentCards(config, { ...input, style: "general", targetIds: ["b"] }, fake(JSON.stringify(extra))),
    (error: unknown) => error instanceof ModelConnectorError && error.code === "invalid-output",
  );
});
