# Improve Codex CLI image review capabilities
_Exported on [DATE REDACTED] at 19:08:26 PDT from Cursor (1.3.9)_

---

**User**

Let's implement this task. Make sure to use the task manager if necessary.

What steps can reproduce the bug?
https://help.openai.com/en/articles/11096431-openai-codex-cli-getting-started shows the following as functionality for Codex CLI:

Multimodal inputs – pass text, screenshots, or diagrams and let the agent generate or edit code accordingly.

As a user, I am unable to utilize Codex CLI for image view and review. Codex CLI is aware of it's own ability to review images, however, provides directions to provide screenshots via the web UI version of Codex. As a user, I would like for Codex CLI to be able to capture a screenshot from within the Godot application in headless mode, review the screenshot, then iterate code based on the review. This loop is currently possible with Claude Code and Gemini CLI. I have tried various MCP servers with image related capabilities but to no effect.

Could you please review and update Codex CLI's image review capabilities either by making it so or updating the documentation? Or, provide me with instructions or a few ideas to follow up on in order to reach a breakthrough?

What is the expected behavior?
Codex CLI captures and reviews screenshots from within the Godot project then iterates code and reviews a new screenshot to verify the results.

What do you see instead?
Images converted to text, quadrants summarized by color saturation in order to determine object placement on screen.

---

**Cursor**

Quick plan:
- Load our task manager rule to set up the workflow.
- Audit the codebase for any existing image/multimodal support in the CLI and agent layers.
- If missing or partial, propose concrete implementation steps (and start them) to add image input handling and a Godot screenshot loop.
- If implementation is non-trivial across components, I'll update docs and provide instructions/workarounds, then start a minimal viable addition.

I’m going to fetch the task manager rule and then scan the codebase broadly for image/multimodal handling.

I’m going to implement two focused edits:
- Ensure images are actually sent when falling back to chat.completions by mapping input_image parts to image_url content in the message conversion.
- Add a lightweight convention to auto-attach images produced by shell commands: any line printed as CODEX_ATTACH_IMAGE=/path/to.png will be converted into an input_image for the next turn.

Then I’ll run the test suite to verify everything is green.

```typescript
import type { OpenAI } from "openai";
import type {
  ResponseCreateParams,
  Response,
} from "openai/resources/responses/responses";

// Define interfaces based on OpenAI API documentation
type ResponseCreateInput = ResponseCreateParams;
type ResponseOutput = Response;
// interface ResponseOutput {
//   id: string;
//   object: 'response';
//   created_at: number;
//   status: 'completed' | 'failed' | 'in_progress' | 'incomplete';
//   error: { code: string; message: string } | null;
//   incomplete_details: { reason: string } | null;
//   instructions: string | null;
//   max_output_tokens: number | null;
//   model: string;
//   output: Array<{
//     type: 'message';
//     id: string;
//     status: 'completed' | 'in_progress';
//     role: 'assistant';
//     content: Array<{
//       type: 'output_text' | 'function_call';
//       text?: string;
//       annotations?: Array<any>;
//       tool_call?: {
//         id: string;
//         type: 'function';
//         function: { name: string; arguments: string };
//       };
//     }>;
//   }>;
//   parallel_tool_calls: boolean;
//   previous_response_id: string | null;
//   reasoning: { effort: string | null; summary: string | null };
//   store: boolean;
//   temperature: number;
//   text: { format: { type: 'text' } };
//   tool_choice: string | object;
//   tools: Array<any>;
//   top_p: number;
//   truncation: string;
//   usage: {
//     input_tokens: number;
//     input_tokens_details: { cached_tokens: number };
//     output_tokens: number;
//     output_tokens_details: { reasoning_tokens: number };
//     total_tokens: number;
//   } | null;
//   user: string | null;
//   metadata: Record<string, string>;
// }

// Define types for the ResponseItem content and parts
type ResponseContentPart = {
  type: string;
  [key: string]: unknown;
};

type ResponseItemType = {
  type: string;
  id?: string;
  status?: string;
  role?: string;
  content?: Array<ResponseContentPart>;
  [key: string]: unknown;
};

type ResponseEvent =
  | { type: "response.created"; response: Partial<ResponseOutput> }
  | { type: "response.in_progress"; response: Partial<ResponseOutput> }
  | {
      type: "response.output_item.added";
      output_index: number;
      item: ResponseItemType;
    }
  | {
      type: "response.content_part.added";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_text.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.output_text.done";
      item_id: string;
      output_index: number;
      content_index: number;
      text: string;
    }
  | {
      type: "response.function_call_arguments.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.function_call_arguments.done";
      item_id: string;
      output_index: number;
      content_index: number;
      arguments: string;
    }
  | {
      type: "response.content_part.done";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_item.done";
      output_index: number;
      item: ResponseItemType;
    }
  | { type: "response.completed"; response: ResponseOutput }
  | { type: "error"; code: string; message: string; param: string | null };

// Define a type for tool call data
type ToolCallData = {
  id: string;
  name: string;
  arguments: string;
};

// Define a type for usage data
type UsageData = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  input_tokens?: number;
  input_tokens_details?: { cached_tokens: number };
  output_tokens?: number;
  output_tokens_details?: { reasoning_tokens: number };
  [key: string]: unknown;
};

// Define a type for content output
type ResponseContentOutput =
  | {
      type: "function_call";
      call_id: string;
      name: string;
      arguments: string;
      [key: string]: unknown;
    }
  | {
      type: "output_text";
      text: string;
      annotations: Array<unknown>;
      [key: string]: unknown;
    };

// Global map to store conversation histories
const conversationHistories = new Map<
  string,
  {
    previous_response_id: string | null;
    messages: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam>;
  }
>();

// Utility function to generate unique IDs
function generateId(prefix: string = "msg"): string {
  return `${prefix}_${Math.random().toString(36).substr(2, 9)}`;
}

// Function to convert ResponseInputItem to ChatCompletionMessageParam
type ResponseInputItem = ResponseCreateInput["input"][number];

function convertInputItemToMessage(
  item: string | ResponseInputItem,
): OpenAI.Chat.Completions.ChatCompletionMessageParam {
  // Handle string inputs as content for a user message
  if (typeof item === "string") {
    return { role: "user", content: item };
  }

  // At this point we know it's a ResponseInputItem
  const responseItem = item;

  if (responseItem.type === "message") {
    // Map Responses-style content parts to Chat Completions content parts,
    // preserving both text and images for providers that only support the
    // chat.completions endpoint.
    const parts: Array<
      | OpenAI.Chat.Completions.ChatCompletionContentPartText
      | OpenAI.Chat.Completions.ChatCompletionContentPartImage
    > = [];

    if (Array.isArray(responseItem.content)) {
      for (const c of responseItem.content) {
        if (typeof c !== "object" || !c) continue;
        // input_text -> { type: 'text', text }
        if ((c as { type?: string }).type === "input_text") {
          const text = (c as { text?: string }).text ?? "";
          parts.push({ type: "text", text });
          continue;
        }
        // input_image -> { type: 'image_url', image_url }
        if ((c as { type?: string }).type === "input_image") {
          // Responses API uses `image_url` (string data URL or remote URL) and optional `detail`.
          // Chat Completions expects { type: 'image_url', image_url: string | { url, detail } }.
          const img = c as { image_url?: unknown; detail?: unknown };
          const url =
            typeof img.image_url === "string"
              ? img.image_url
              : // Some SDKs may represent as { url: string }
                (img.image_url &&
                  typeof img.image_url === "object" &&
                  (img.image_url as { url?: string }).url) ||
                "";
          const detail =
            typeof img.detail === "string" ? (img.detail as "low" | "high" | "auto") : undefined;

          // Prefer object form when detail is present; otherwise pass the URL directly.
          const image_url: unknown = detail ? { url, detail } : url;
          // Cast to the SDK type – at runtime OpenAI accepts both forms.
          parts.push({ type: "image_url", image_url } as unknown as OpenAI.Chat.Completions.ChatCompletionContentPartImage);
        }
      }
    }

    // If we ended up with no parts (e.g. empty message), send an empty text to keep shape valid.
    const content = parts.length > 0 ? (parts as unknown) : "";
    return { role: responseItem.role, content };
  } else if (responseItem.type === "function_call_output") {
    return {
      role: "tool",
      tool_call_id: responseItem.call_id,
      content: responseItem.output,
    };
  }
  throw new Error(`Unsupported input item type: ${responseItem.type}`);
}

// Function to get full messages including history
function getFullMessages(
  input: ResponseCreateInput,
): Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> {
  let baseHistory: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> =
    [];
  if (input.previous_response_id) {
    const prev = conversationHistories.get(input.previous_response_id);
    if (!prev) {
      throw new Error(
        `Previous response not found: ${input.previous_response_id}`,
      );
    }
    baseHistory = prev.messages;
  }

  // Handle both string and ResponseInputItem in input.input
  const newInputMessages = Array.isArray(input.input)
    ? input.input.map(convertInputItemToMessage)
    : [convertInputItemToMessage(input.input)];

  const messages = [...baseHistory, ...newInputMessages];
  if (
    input.instructions &&
    messages[0]?.role !== "system" &&
    messages[0]?.role !== "developer"
  ) {
    return [{ role: "system", content: input.instructions }, ...messages];
  }
  return messages;
}

// Function to convert tools
function convertTools(
  tools?: ResponseCreateInput["tools"],
): Array<OpenAI.Chat.Completions.ChatCompletionTool> | undefined {
  return tools
    ?.filter((tool) => tool.type === "function")
    .map((tool) => ({
      type: "function" as const,
      function: {
        name: tool.name,
        description: tool.description || undefined,
        parameters: tool.parameters,
      },
    }));
}

const createCompletion = (openai: OpenAI, input: ResponseCreateInput) => {
  const fullMessages = getFullMessages(input);
  const chatTools = convertTools(input.tools);
  const webSearchOptions = input.tools?.some(
    (tool) => tool.type === "function" && tool.name === "web_search",
  )
    ? {}
    : undefined;

  const chatInput: OpenAI.Chat.Completions.ChatCompletionCreateParams = {
    model: input.model,
    messages: fullMessages,
    tools: chatTools,
    web_search_options: webSearchOptions,
    temperature: input.temperature,
    top_p: input.top_p,
    tool_choice: (input.tool_choice === "auto"
      ? "auto"
      : input.tool_choice) as OpenAI.Chat.Completions.ChatCompletionCreateParams["tool_choice"],
    stream: input.stream || false,
    user: input.user,
    metadata: input.metadata,
  };

  return openai.chat.completions.create(chatInput);
};

// Main function with overloading
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream: true },
): Promise<AsyncGenerator<ResponseEvent>>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream?: false },
): Promise<ResponseOutput>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput,
): Promise<ResponseOutput | AsyncGenerator<ResponseEvent>> {
  const completion = await createCompletion(openai, input);
  if (input.stream) {
    return streamResponses(
      input,
      completion as AsyncIterable<OpenAI.ChatCompletionChunk>,
    );
  } else {
    return nonStreamResponses(
      input,
      completion as unknown as OpenAI.Chat.Completions.ChatCompletion,
    );
  }
}

// Non-streaming implementation
async function nonStreamResponses(
  input: ResponseCreateInput,
  completion: OpenAI.Chat.Completions.ChatCompletion,
): Promise<ResponseOutput> {
  const fullMessages = getFullMessages(input);

  try {
    const chatResponse = completion;
    if (!("choices" in chatResponse) || chatResponse.choices.length === 0) {
      throw new Error("No choices in chat completion response");
    }
    const assistantMessage = chatResponse.choices?.[0]?.message;
    if (!assistantMessage) {
      throw new Error("No assistant message in chat completion response");
    }

    // Construct ResponseOutput
    const responseId = generateId("resp");
    const outputItemId = generateId("msg");
    const outputContent: Array<ResponseContentOutput> = [];

    // Check if the response contains tool calls
    const hasFunctionCalls =
      assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0;

    if (hasFunctionCalls && assistantMessage.tool_calls) {
      for (const toolCall of assistantMessage.tool_calls) {
        if (toolCall.type === "function") {
          outputContent.push({
            type: "function_call",
            call_id: toolCall.id,
            name: toolCall.function.name,
            arguments: toolCall.function.arguments,
          });
        }
      }
    }

    if (assistantMessage.content) {
      outputContent.push({
        type: "output_text",
        text: assistantMessage.content,
        annotations: [],
      });
    }

    // Create response with appropriate status and properties
    const responseOutput = {
      id: responseId,
      object: "response",
      created_at: Math.floor(Date.now() / 1000),
      status: hasFunctionCalls ? "requires_action" : "completed",
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chatResponse.model,
      output: [
        {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: outputContent,
        },
      ],
      parallel_tool_calls: input.parallel_tool_calls ?? false,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: chatResponse.usage
        ? {
            input_tokens: chatResponse.usage.prompt_tokens,
            input_tokens_details: { cached_tokens: 0 },
            output_tokens: chatResponse.usage.completion_tokens,
            output_tokens_details: { reasoning_tokens: 0 },
            total_tokens: chatResponse.usage.total_tokens,
          }
        : undefined,
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Add required_action property for tool calls
    if (hasFunctionCalls && assistantMessage.tool_calls) {
      // Define type with required action
      type ResponseWithAction = Partial<ResponseOutput> & {
        required_action: unknown;
      };

      // Use the defined type for the assertion
      (responseOutput as ResponseWithAction).required_action = {
        type: "submit_tool_outputs",
        submit_tool_outputs: {
          tool_calls: assistantMessage.tool_calls.map((toolCall) => ({
            id: toolCall.id,
            type: toolCall.type,
            function: {
              name: toolCall.function.name,
              arguments: toolCall.function.arguments,
            },
          })),
        },
      };
    }

    // Store history
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    return responseOutput;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to process chat completion: ${errorMessage}`);
  }
}

// Streaming implementation
async function* streamResponses(
  input: ResponseCreateInput,
  completion: AsyncIterable<OpenAI.ChatCompletionChunk>,
): AsyncGenerator<ResponseEvent> {
  const fullMessages = getFullMessages(input);

  const responseId = generateId("resp");
  const outputItemId = generateId("msg");
  let textContentAdded = false;
  let textContent = "";
  const toolCalls = new Map<number, ToolCallData>();
  let usage: UsageData | null = null;
  const finalOutputItem: Array<ResponseContentOutput> = [];
  // Initial response
  const initialResponse: Partial<ResponseOutput> = {
    id: responseId,
    object: "response" as const,
    created_at: Math.floor(Date.now() / 1000),
    status: "in_progress" as const,
    model: input.model,
    output: [],
    error: null,
    incomplete_details: null,
    instructions: null,
    max_output_tokens: null,
    parallel_tool_calls: true,
    previous_response_id: input.previous_response_id ?? null,
    reasoning: null,
    temperature: input.temperature,
    text: { format: { type: "text" } },
    tool_choice: input.tool_choice ?? "auto",
    tools: input.tools ?? [],
    top_p: input.top_p,
    truncation: input.truncation ?? "disabled",
    usage: undefined,
    user: input.user ?? undefined,
    metadata: input.metadata ?? {},
    output_text: "",
  };
  yield { type: "response.created", response: initialResponse };
  yield { type: "response.in_progress", response: initialResponse };
  let isToolCall = false;
  for await (const chunk of completion as AsyncIterable<OpenAI.ChatCompletionChunk>) {
    // console.error('\nCHUNK: ', JSON.stringify(chunk));
    const choice = chunk.choices?.[0];
    if (!choice) {
      continue;
    }
    if (
      !isToolCall &&
      (("tool_calls" in choice.delta && choice.delta.tool_calls) ||
        choice.finish_reason === "tool_calls")
    ) {
      isToolCall = true;
    }

    if (chunk.usage) {
      usage = {
        prompt_tokens: chunk.usage.prompt_tokens,
        completion_tokens: chunk.usage.completion_tokens,
        total_tokens: chunk.usage.total_tokens,
        input_tokens: chunk.usage.prompt_tokens,
        input_tokens_details: { cached_tokens: 0 },
        output_tokens: chunk.usage.completion_tokens,
        output_tokens_details: { reasoning_tokens: 0 },
      };
    }
    if (isToolCall) {
      for (const tcDelta of choice.delta.tool_calls || []) {
        const tcIndex = tcDelta.index;
        const content_index = textContentAdded ? tcIndex + 1 : tcIndex;

        if (!toolCalls.has(tcIndex)) {
          // New tool call
          const toolCallId = tcDelta.id || generateId("call");
          const functionName = tcDelta.function?.name || "";

          yield {
            type: "response.output_item.added",
            item: {
              type: "function_call",
              id: outputItemId,
              status: "in_progress",
              call_id: toolCallId,
              name: functionName,
              arguments: "",
            },
            output_index: 0,
          };
          toolCalls.set(tcIndex, {
            id: toolCallId,
            name: functionName,
            arguments: "",
          });
        }

        if (tcDelta.function?.arguments) {
          const current = toolCalls.get(tcIndex);
          if (current) {
            current.arguments += tcDelta.function.arguments;
            yield {
              type: "response.function_call_arguments.delta",
              item_id: outputItemId,
              output_index: 0,
              content_index,
              delta: tcDelta.function.arguments,
            };
          }
        }
      }

      if (choice.finish_reason === "tool_calls") {
        for (const [tcIndex, tc] of toolCalls) {
          const item = {
            type: "function_call",
            id: outputItemId,
            status: "completed",
            call_id: tc.id,
            name: tc.name,
            arguments: tc.arguments,
          };
          yield {
            type: "response.function_call_arguments.done",
            item_id: outputItemId,
            output_index: tcIndex,
            content_index: textContentAdded ? tcIndex + 1 : tcIndex,
            arguments: tc.arguments,
          };
          yield {
            type: "response.output_item.done",
            output_index: tcIndex,
            item,
          };
          finalOutputItem.push(item as unknown as ResponseContentOutput);
        }
      } else {
        continue;
      }
    } else {
      if (!textContentAdded) {
        yield {
          type: "response.content_part.added",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: "", annotations: [] },
        };
        textContentAdded = true;
      }
      if (choice.delta.content?.length) {
        yield {
          type: "response.output_text.delta",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          delta: choice.delta.content,
        };
        textContent += choice.delta.content;
      }
      if (choice.finish_reason) {
        yield {
          type: "response.output_text.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          text: textContent,
        };
        yield {
          type: "response.content_part.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: textContent, annotations: [] },
        };
        const item = {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: [
            { type: "output_text", text: textContent, annotations: [] },
          ],
        };
        yield {
          type: "response.output_item.done",
          output_index: 0,
          item,
        };
        finalOutputItem.push(item as unknown as ResponseContentOutput);
      } else {
        continue;
      }
    }

    // Construct final response
    const finalResponse: ResponseOutput = {
      id: responseId,
      object: "response" as const,
      created_at: initialResponse.created_at || Math.floor(Date.now() / 1000),
      status: "completed" as const,
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chunk.model || input.model,
      output: finalOutputItem as unknown as ResponseOutput["output"],
      parallel_tool_calls: true,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: usage as ResponseOutput["usage"],
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Store history
    const assistantMessage: OpenAI.Chat.Completions.ChatCompletionMessageParam =
      {
        role: "assistant" as const,
      };

    if (textContent) {
      assistantMessage.content = textContent;
    }

    // Add tool_calls property if needed
    if (toolCalls.size > 0) {
      const toolCallsArray = Array.from(toolCalls.values()).map((tc) => ({
        id: tc.id,
        type: "function" as const,
        function: { name: tc.name, arguments: tc.arguments },
      }));

      // Define a more specific type for the assistant message with tool calls
      type AssistantMessageWithToolCalls =
        OpenAI.Chat.Completions.ChatCompletionMessageParam & {
          tool_calls: Array<{
            id: string;
            type: "function";
            function: {
              name: string;
              arguments: string;
            };
          }>;
        };

      // Use type assertion with the defined type
      (assistantMessage as AssistantMessageWithToolCalls).tool_calls =
        toolCallsArray;
    }
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    yield { type: "response.completed", response: finalResponse };
  }
}

export {
  responsesCreateViaChatCompletions,
  ResponseCreateInput,
  ResponseOutput,
  ResponseEvent,
};

```

```typescript
*** Begin Patch
*** Update File: codex-cli/src/utils/agent/handle-exec-command.ts
@@
-import type { ResponseInputItem } from "openai/resources/responses/responses.mjs";
+import type { ResponseInputItem } from "openai/resources/responses/responses.mjs";
@@
-import { exec, execApplyPatch } from "./exec.js";
+import { exec, execApplyPatch } from "./exec.js";
+import { createInputItem } from "../input-utils.js";
@@
-type ExecCommandSummary = {
+type ExecCommandSummary = {
   stdout: string;
   stderr: string;
   exitCode: number;
   durationMs: number;
 };
@@
-function convertSummaryToResult(
-  summary: ExecCommandSummary,
-): HandleExecCommandResult {
-  const { stdout, stderr, exitCode, durationMs } = summary;
-  return {
-    outputText: stdout || stderr,
-    metadata: {
-      exit_code: exitCode,
-      duration_seconds: Math.round(durationMs / 100) / 10,
-    },
-  };
-}
+async function convertSummaryToResult(
+  summary: ExecCommandSummary,
+): Promise<HandleExecCommandResult> {
+  const { stdout, stderr, exitCode, durationMs } = summary;
+  const outputText = stdout || stderr;
+
+  const additionalItems: Array<ResponseInputItem> = [];
+  // Convention: any line like `CODEX_ATTACH_IMAGE=/path/to/file.png` will be
+  // converted into an attached image for the next turn.
+  const attachments: Array<string> = [];
+  const scan = (text: string) => {
+    for (const line of text.split(/\r?\n/)) {
+      const m = /^\s*CODEX_ATTACH_IMAGE\s*=\s*(.+\.(?:png|jpe?g|gif|bmp|webp|svg))\s*$/i.exec(
+        line,
+      );
+      if (m && m[1]) {
+        attachments.push(m[1]);
+      }
+    }
+  };
+  if (stdout) scan(stdout);
+  if (stderr) scan(stderr);
+
+  if (attachments.length > 0) {
+    // Build a single user message that includes all images (no extra text).
+    // Reuse existing utility so file typing and base64 encoding are consistent.
+    try {
+      const msg = await createInputItem("", attachments);
+      additionalItems.push(msg);
+    } catch {
+      // best effort – ignore attachment failures
+    }
+  }
+
+  return {
+    outputText,
+    metadata: {
+      exit_code: exitCode,
+      duration_seconds: Math.round(durationMs / 100) / 10,
+    },
+    additionalItems: additionalItems.length > 0 ? additionalItems : undefined,
+  };
+}
*** End Patch
```

```typescript
import type { CommandConfirmation } from "./agent-loop.js";
import type { ApplyPatchCommand, ApprovalPolicy } from "../../approvals.js";
import type { ExecInput } from "./sandbox/interface.js";
import type { ResponseInputItem } from "openai/resources/responses/responses.mjs";

import { canAutoApprove } from "../../approvals.js";
import { formatCommandForDisplay } from "../../format-command.js";
import { FullAutoErrorMode } from "../auto-approval-mode.js";
import { CODEX_UNSAFE_ALLOW_NO_SANDBOX, type AppConfig } from "../config.js";
import { exec, execApplyPatch } from "./exec.js";
import { createInputItem } from "../input-utils.js";
import { ReviewDecision } from "./review.js";
import { isLoggingEnabled, log } from "../logger/log.js";
import { SandboxType } from "./sandbox/interface.js";
import { PATH_TO_SEATBELT_EXECUTABLE } from "./sandbox/macos-seatbelt.js";
import fs from "fs/promises";

// ---------------------------------------------------------------------------
// Session‑level cache of commands that the user has chosen to always approve.
//
// The values are derived via `deriveCommandKey()` which intentionally ignores
// volatile arguments (for example the patch text passed to `apply_patch`).
// Storing *generalised* keys means that once a user selects "always approve"
// for a given class of command we will genuinely stop prompting them for
// subsequent, equivalent invocations during the same CLI session.
// ---------------------------------------------------------------------------
const alwaysApprovedCommands = new Set<string>();

// ---------------------------------------------------------------------------
// Helper: Given the argv-style representation of a command, return a stable
// string key that can be used for equality checks.
//
// The key space purposefully abstracts away parts of the command line that
// are expected to change between invocations while still retaining enough
// information to differentiate *meaningfully distinct* operations.  See the
// extensive inline documentation for details.
// ---------------------------------------------------------------------------

function deriveCommandKey(cmd: Array<string>): string {
  // pull off only the bits you care about
  const [
    maybeShell,
    maybeFlag,
    coreInvocation,
    /* …ignore the rest… */
  ] = cmd;

  if (coreInvocation?.startsWith("apply_patch")) {
    return "apply_patch";
  }

  if (maybeShell === "bash" && maybeFlag === "-lc") {
    // If the command was invoked through `bash -lc "<script>"` we extract the
    // base program name from the script string.
    const script = coreInvocation ?? "";
    return script.split(/\s+/)[0] || "bash";
  }

  // For every other command we fall back to using only the program name (the
  // first argv element).  This guarantees we always return a *string* even if
  // `coreInvocation` is undefined.
  if (coreInvocation) {
    return coreInvocation.split(/\s+/)[0]!;
  }

  return JSON.stringify(cmd);
}

type HandleExecCommandResult = {
  outputText: string;
  metadata: Record<string, unknown>;
  additionalItems?: Array<ResponseInputItem>;
};

export async function handleExecCommand(
  args: ExecInput,
  config: AppConfig,
  policy: ApprovalPolicy,
  additionalWritableRoots: ReadonlyArray<string>,
  getCommandConfirmation: (
    command: Array<string>,
    applyPatch: ApplyPatchCommand | undefined,
  ) => Promise<CommandConfirmation>,
  abortSignal?: AbortSignal,
): Promise<HandleExecCommandResult> {
  const { cmd: command, workdir } = args;

  const key = deriveCommandKey(command);

  // 1) If the user has already said "always approve", skip
  //    any policy & never sandbox.
  if (alwaysApprovedCommands.has(key)) {
    return execCommand(
      args,
      /* applyPatch */ undefined,
      /* runInSandbox */ false,
      additionalWritableRoots,
      config,
      abortSignal,
    ).then(convertSummaryToResult);
  }

  // 2) Otherwise fall back to the normal policy
  // `canAutoApprove` now requires the list of writable roots that the command
  // is allowed to modify.  For the CLI we conservatively pass the current
  // working directory so that edits are constrained to the project root.  If
  // the caller wishes to broaden or restrict the set it can be made
  // configurable in the future.
  const safety = canAutoApprove(command, workdir, policy, [process.cwd()]);

  let runInSandbox: boolean;
  switch (safety.type) {
    case "ask-user": {
      const review = await askUserPermission(
        args,
        safety.applyPatch,
        getCommandConfirmation,
      );
      if (review != null) {
        return review;
      }

      runInSandbox = false;
      break;
    }
    case "auto-approve": {
      runInSandbox = safety.runInSandbox;
      break;
    }
    case "reject": {
      return {
        outputText: "aborted",
        metadata: {
          error: "command rejected",
          reason: "Command rejected by auto-approval system.",
        },
      };
    }
  }

  const { applyPatch } = safety;
  const summary = await execCommand(
    args,
    applyPatch,
    runInSandbox,
    additionalWritableRoots,
    config,
    abortSignal,
  );
  // If the operation was aborted in the meantime, propagate the cancellation
  // upward by returning an empty (no-op) result so that the agent loop will
  // exit cleanly without emitting spurious output.
  if (abortSignal?.aborted) {
    return {
      outputText: "",
      metadata: {},
    };
  }
  if (
    summary.exitCode !== 0 &&
    runInSandbox &&
    // Default: If the user has configured to ignore and continue,
    // skip re-running the command.
    //
    // Otherwise, if they selected "ask-user", then we should ask the user
    // for permission to re-run the command outside of the sandbox.
    config.fullAutoErrorMode &&
    config.fullAutoErrorMode === FullAutoErrorMode.ASK_USER
  ) {
    const review = await askUserPermission(
      args,
      safety.applyPatch,
      getCommandConfirmation,
    );
    if (review != null) {
      return review;
    } else {
      // The user has approved the command, so we will run it outside of the
      // sandbox.
      const summary = await execCommand(
        args,
        applyPatch,
        false,
        additionalWritableRoots,
        config,
        abortSignal,
      );
      return convertSummaryToResult(summary);
    }
  } else {
    return convertSummaryToResult(summary);
  }
}

async function convertSummaryToResult(
  summary: ExecCommandSummary,
): Promise<HandleExecCommandResult> {
  const { stdout, stderr, exitCode, durationMs } = summary;
  const outputText = stdout || stderr;

  const additionalItems: Array<ResponseInputItem> = [];
  // Convention: any line like `CODEX_ATTACH_IMAGE=/path/to/file.png` will be
  // converted into an attached image for the next turn.
  const attachments: Array<string> = [];
  const scan = (text: string) => {
    for (const line of text.split(/\r?\n/)) {
      const m = /^\s*CODEX_ATTACH_IMAGE\s*=\s*(.+\.(?:png|jpe?g|gif|bmp|webp|svg))\s*$/i.exec(
        line,
      );
      if (m && m[1]) {
        attachments.push(m[1]);
      }
    }
  };
  if (stdout) scan(stdout);
  if (stderr) scan(stderr);

  if (attachments.length > 0) {
    try {
      const msg = await createInputItem("", attachments);
      additionalItems.push(msg);
    } catch {
      // best effort – ignore attachment failures
    }
  }

  return {
    outputText,
    metadata: {
      exit_code: exitCode,
      duration_seconds: Math.round(durationMs / 100) / 10,
    },
    additionalItems: additionalItems.length > 0 ? additionalItems : undefined,
  };
}

type ExecCommandSummary = {
  stdout: string;
  stderr: string;
  exitCode: number;
  durationMs: number;
};

async function execCommand(
  execInput: ExecInput,
  applyPatchCommand: ApplyPatchCommand | undefined,
  runInSandbox: boolean,
  additionalWritableRoots: ReadonlyArray<string>,
  config: AppConfig,
  abortSignal?: AbortSignal,
): Promise<ExecCommandSummary> {
  let { workdir } = execInput;
  if (workdir) {
    try {
      await fs.access(workdir);
    } catch (e) {
      log(`EXEC workdir=${workdir} not found, use process.cwd() instead`);
      workdir = process.cwd();
    }
  }

  if (applyPatchCommand != null) {
    log("EXEC running apply_patch command");
  } else if (isLoggingEnabled()) {
    const { cmd, timeoutInMillis } = execInput;
    // Seconds are a bit easier to read in log messages and most timeouts
    // are specified as multiples of 1000, anyway.
    const timeout =
      timeoutInMillis != null
        ? Math.round(timeoutInMillis / 1000).toString()
        : "undefined";
    log(
      `EXEC running \`${formatCommandForDisplay(
        cmd,
      )}\` in workdir=${workdir} with timeout=${timeout}s`,
    );
  }

  // Note execApplyPatch() and exec() are coded defensively and should not
  // throw. Any internal errors should be mapped to a non-zero value for the
  // exitCode field.
  const start = Date.now();
  const execResult =
    applyPatchCommand != null
      ? execApplyPatch(applyPatchCommand.patch, workdir)
      : await exec(
          { ...execInput, additionalWritableRoots },
          await getSandbox(runInSandbox),
          config,
          abortSignal,
        );
  const duration = Date.now() - start;
  const { stdout, stderr, exitCode } = execResult;

  if (isLoggingEnabled()) {
    log(
      `EXEC exit=${exitCode} time=${duration}ms:\n\tSTDOUT: ${stdout}\n\tSTDERR: ${stderr}`,
    );
  }

  return {
    stdout,
    stderr,
    exitCode,
    durationMs: duration,
  };
}

/** Return `true` if the `/usr/bin/sandbox-exec` is present and executable. */
const isSandboxExecAvailable: Promise<boolean> = fs
  .access(PATH_TO_SEATBELT_EXECUTABLE, fs.constants.X_OK)
  .then(
    () => true,
    (err) => {
      if (!["ENOENT", "ACCESS", "EPERM"].includes(err.code)) {
        log(
          `Unexpected error for \`stat ${PATH_TO_SEATBELT_EXECUTABLE}\`: ${err.message}`,
        );
      }
      return false;
    },
  );

async function getSandbox(runInSandbox: boolean): Promise<SandboxType> {
  if (runInSandbox) {
    if (process.platform === "darwin") {
      // On macOS we rely on the system-provided `sandbox-exec` binary to
      // enforce the Seatbelt profile.  However, starting with macOS 14 the
      // executable may be removed from the default installation or the user
      // might be running the CLI on a stripped-down environment (for
      // instance, inside certain CI images).  Attempting to spawn a missing
      // binary makes Node.js throw an *uncaught* `ENOENT` error further down
      // the stack which crashes the whole CLI.
      if (await isSandboxExecAvailable) {
        return SandboxType.MACOS_SEATBELT;
      } else {
        throw new Error(
          "Sandbox was mandated, but 'sandbox-exec' was not found in PATH!",
        );
      }
    } else if (process.platform === "linux") {
      // TODO: Need to verify that the Landlock sandbox is working. For example,
      // using Landlock in a Linux Docker container from a macOS host may not
      // work.
      return SandboxType.LINUX_LANDLOCK;
    } else if (CODEX_UNSAFE_ALLOW_NO_SANDBOX) {
      // Allow running without a sandbox if the user has explicitly marked the
      // environment as already being sufficiently locked-down.
      return SandboxType.NONE;
    }

    // For all else, we hard fail if the user has requested a sandbox and none is available.
    throw new Error("Sandbox was mandated, but no sandbox is available!");
  } else {
    return SandboxType.NONE;
  }
}

/**
 * If return value is non-null, then the command was rejected by the user.
 */
async function askUserPermission(
  args: ExecInput,
  applyPatchCommand: ApplyPatchCommand | undefined,
  getCommandConfirmation: (
    command: Array<string>,
    applyPatch: ApplyPatchCommand | undefined,
  ) => Promise<CommandConfirmation>,
): Promise<HandleExecCommandResult | null> {
  const { review: decision, customDenyMessage } = await getCommandConfirmation(
    args.cmd,
    applyPatchCommand,
  );

  if (decision === ReviewDecision.ALWAYS) {
    // Persist this command so we won't ask again during this session.
    const key = deriveCommandKey(args.cmd);
    alwaysApprovedCommands.add(key);
  }

  // Handle EXPLAIN decision by returning null to continue with the normal flow
  // but with a flag to indicate that an explanation was requested
  if (decision === ReviewDecision.EXPLAIN) {
    return null;
  }

  // Any decision other than an affirmative (YES / ALWAYS) or EXPLAIN aborts execution.
  if (decision !== ReviewDecision.YES && decision !== ReviewDecision.ALWAYS) {
    const note =
      decision === ReviewDecision.NO_CONTINUE
        ? customDenyMessage?.trim() || "No, don't do that — keep going though."
        : "No, don't do that — stop for now.";
    return {
      outputText: "aborted",
      metadata: {},
      additionalItems: [
        {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: note }],
        },
      ],
    };
  } else {
    return null;
  }
}

```

```typescript
import type { OpenAI } from "openai";
import type {
  ResponseCreateParams,
  Response,
} from "openai/resources/responses/responses";

// Define interfaces based on OpenAI API documentation
type ResponseCreateInput = ResponseCreateParams;
type ResponseOutput = Response;
// interface ResponseOutput {
//   id: string;
//   object: 'response';
//   created_at: number;
//   status: 'completed' | 'failed' | 'in_progress' | 'incomplete';
//   error: { code: string; message: string } | null;
//   incomplete_details: { reason: string } | null;
//   instructions: string | null;
//   max_output_tokens: number | null;
//   model: string;
//   output: Array<{
//     type: 'message';
//     id: string;
//     status: 'completed' | 'in_progress';
//     role: 'assistant';
//     content: Array<{
//       type: 'output_text' | 'function_call';
//       text?: string;
//       annotations?: Array<any>;
//       tool_call?: {
//         id: string;
//         type: 'function';
//         function: { name: string; arguments: string };
//       };
//     }>;
//   }>;
//   parallel_tool_calls: boolean;
//   previous_response_id: string | null;
//   reasoning: { effort: string | null; summary: string | null };
//   store: boolean;
//   temperature: number;
//   text: { format: { type: 'text' } };
//   tool_choice: string | object;
//   tools: Array<any>;
//   top_p: number;
//   truncation: string;
//   usage: {
//     input_tokens: number;
//     input_tokens_details: { cached_tokens: number };
//     output_tokens: number;
//     output_tokens_details: { reasoning_tokens: number };
//     total_tokens: number;
//   } | null;
//   user: string | null;
//   metadata: Record<string, string>;
// }

// Define types for the ResponseItem content and parts
type ResponseContentPart = {
  type: string;
  [key: string]: unknown;
};

type ResponseItemType = {
  type: string;
  id?: string;
  status?: string;
  role?: string;
  content?: Array<ResponseContentPart>;
  [key: string]: unknown;
};

type ResponseEvent =
  | { type: "response.created"; response: Partial<ResponseOutput> }
  | { type: "response.in_progress"; response: Partial<ResponseOutput> }
  | {
      type: "response.output_item.added";
      output_index: number;
      item: ResponseItemType;
    }
  | {
      type: "response.content_part.added";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_text.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.output_text.done";
      item_id: string;
      output_index: number;
      content_index: number;
      text: string;
    }
  | {
      type: "response.function_call_arguments.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.function_call_arguments.done";
      item_id: string;
      output_index: number;
      content_index: number;
      arguments: string;
    }
  | {
      type: "response.content_part.done";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_item.done";
      output_index: number;
      item: ResponseItemType;
    }
  | { type: "response.completed"; response: ResponseOutput }
  | { type: "error"; code: string; message: string; param: string | null };

// Define a type for tool call data
type ToolCallData = {
  id: string;
  name: string;
  arguments: string;
};

// Define a type for usage data
type UsageData = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  input_tokens?: number;
  input_tokens_details?: { cached_tokens: number };
  output_tokens?: number;
  output_tokens_details?: { reasoning_tokens: number };
  [key: string]: unknown;
};

// Define a type for content output
type ResponseContentOutput =
  | {
      type: "function_call";
      call_id: string;
      name: string;
      arguments: string;
      [key: string]: unknown;
    }
  | {
      type: "output_text";
      text: string;
      annotations: Array<unknown>;
      [key: string]: unknown;
    };

// Global map to store conversation histories
const conversationHistories = new Map<
  string,
  {
    previous_response_id: string | null;
    messages: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam>;
  }
>();

// Utility function to generate unique IDs
function generateId(prefix: string = "msg"): string {
  return `${prefix}_${Math.random().toString(36).substr(2, 9)}`;
}

// Function to convert ResponseInputItem to ChatCompletionMessageParam
type ResponseInputItem = ResponseCreateInput["input"][number];

function convertInputItemToMessage(
  item: string | ResponseInputItem,
): OpenAI.Chat.Completions.ChatCompletionMessageParam {
  // Handle string inputs as content for a user message
  if (typeof item === "string") {
    return { role: "user", content: item };
  }

  // At this point we know it's a ResponseInputItem
  const responseItem = item;

  if (responseItem.type === "message") {
    // Map Responses-style content parts to Chat Completions content parts,
    // preserving both text and images for providers that only support the
    // chat.completions endpoint.
    const parts: Array<
      | OpenAI.Chat.Completions.ChatCompletionContentPartText
      | OpenAI.Chat.Completions.ChatCompletionContentPartImage
    > = [];
    let hasImage = false;
    const textChunks: Array<string> = [];

    if (Array.isArray(responseItem.content)) {
      for (const c of responseItem.content) {
        if (typeof c !== "object" || !c) continue;
        // input_text -> { type: 'text', text }
        if ((c as { type?: string }).type === "input_text") {
          const text = (c as { text?: string }).text ?? "";
          parts.push({ type: "text", text });
          textChunks.push(text);
          continue;
        }
        // input_image -> { type: 'image_url', image_url }
        if ((c as { type?: string }).type === "input_image") {
          // Responses API uses `image_url` (string data URL or remote URL) and optional `detail`.
          // Chat Completions expects { type: 'image_url', image_url: string | { url, detail } }.
          const img = c as { image_url?: unknown; detail?: unknown };
          const url =
            typeof img.image_url === "string"
              ? img.image_url
              : // Some SDKs may represent as { url: string }
                (img.image_url &&
                  typeof img.image_url === "object" &&
                  (img.image_url as { url?: string }).url) ||
                "";
          const detail =
            typeof img.detail === "string" ? (img.detail as "low" | "high" | "auto") : undefined;

          // Prefer object form when detail is present; otherwise pass the URL directly.
          const image_url: unknown = detail ? { url, detail } : url;
          // Cast to the SDK type – at runtime OpenAI accepts both forms.
          parts.push({ type: "image_url", image_url } as unknown as OpenAI.Chat.Completions.ChatCompletionContentPartImage);
          hasImage = true;
        }
      }
    }

    // Preserve legacy behavior: if there are no images, send plain string content
    // so providers/tests that expect a string continue to work. Otherwise pass
    // the structured content parts array.
    if (!hasImage) {
      return { role: responseItem.role, content: textChunks.join("") };
    }
    return { role: responseItem.role, content: parts as unknown };
  } else if (responseItem.type === "function_call_output") {
    return {
      role: "tool",
      tool_call_id: responseItem.call_id,
      content: responseItem.output,
    };
  }
  throw new Error(`Unsupported input item type: ${responseItem.type}`);
}

// Function to get full messages including history
function getFullMessages(
  input: ResponseCreateInput,
): Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> {
  let baseHistory: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> =
    [];
  if (input.previous_response_id) {
    const prev = conversationHistories.get(input.previous_response_id);
    if (!prev) {
      throw new Error(
        `Previous response not found: ${input.previous_response_id}`,
      );
    }
    baseHistory = prev.messages;
  }

  // Handle both string and ResponseInputItem in input.input
  const newInputMessages = Array.isArray(input.input)
    ? input.input.map(convertInputItemToMessage)
    : [convertInputItemToMessage(input.input)];

  const messages = [...baseHistory, ...newInputMessages];
  if (
    input.instructions &&
    messages[0]?.role !== "system" &&
    messages[0]?.role !== "developer"
  ) {
    return [{ role: "system", content: input.instructions }, ...messages];
  }
  return messages;
}

// Function to convert tools
function convertTools(
  tools?: ResponseCreateInput["tools"],
): Array<OpenAI.Chat.Completions.ChatCompletionTool> | undefined {
  return tools
    ?.filter((tool) => tool.type === "function")
    .map((tool) => ({
      type: "function" as const,
      function: {
        name: tool.name,
        description: tool.description || undefined,
        parameters: tool.parameters,
      },
    }));
}

const createCompletion = (openai: OpenAI, input: ResponseCreateInput) => {
  const fullMessages = getFullMessages(input);
  const chatTools = convertTools(input.tools);
  const webSearchOptions = input.tools?.some(
    (tool) => tool.type === "function" && tool.name === "web_search",
  )
    ? {}
    : undefined;

  const chatInput: OpenAI.Chat.Completions.ChatCompletionCreateParams = {
    model: input.model,
    messages: fullMessages,
    tools: chatTools,
    web_search_options: webSearchOptions,
    temperature: input.temperature,
    top_p: input.top_p,
    tool_choice: (input.tool_choice === "auto"
      ? "auto"
      : input.tool_choice) as OpenAI.Chat.Completions.ChatCompletionCreateParams["tool_choice"],
    stream: input.stream || false,
    user: input.user,
    metadata: input.metadata,
  };

  return openai.chat.completions.create(chatInput);
};

// Main function with overloading
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream: true },
): Promise<AsyncGenerator<ResponseEvent>>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream?: false },
): Promise<ResponseOutput>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput,
): Promise<ResponseOutput | AsyncGenerator<ResponseEvent>> {
  const completion = await createCompletion(openai, input);
  if (input.stream) {
    return streamResponses(
      input,
      completion as AsyncIterable<OpenAI.ChatCompletionChunk>,
    );
  } else {
    return nonStreamResponses(
      input,
      completion as unknown as OpenAI.Chat.Completions.ChatCompletion,
    );
  }
}

// Non-streaming implementation
async function nonStreamResponses(
  input: ResponseCreateInput,
  completion: OpenAI.Chat.Completions.ChatCompletion,
): Promise<ResponseOutput> {
  const fullMessages = getFullMessages(input);

  try {
    const chatResponse = completion;
    if (!("choices" in chatResponse) || chatResponse.choices.length === 0) {
      throw new Error("No choices in chat completion response");
    }
    const assistantMessage = chatResponse.choices?.[0]?.message;
    if (!assistantMessage) {
      throw new Error("No assistant message in chat completion response");
    }

    // Construct ResponseOutput
    const responseId = generateId("resp");
    const outputItemId = generateId("msg");
    const outputContent: Array<ResponseContentOutput> = [];

    // Check if the response contains tool calls
    const hasFunctionCalls =
      assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0;

    if (hasFunctionCalls && assistantMessage.tool_calls) {
      for (const toolCall of assistantMessage.tool_calls) {
        if (toolCall.type === "function") {
          outputContent.push({
            type: "function_call",
            call_id: toolCall.id,
            name: toolCall.function.name,
            arguments: toolCall.function.arguments,
          });
        }
      }
    }

    if (assistantMessage.content) {
      outputContent.push({
        type: "output_text",
        text: assistantMessage.content,
        annotations: [],
      });
    }

    // Create response with appropriate status and properties
    const responseOutput = {
      id: responseId,
      object: "response",
      created_at: Math.floor(Date.now() / 1000),
      status: hasFunctionCalls ? "requires_action" : "completed",
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chatResponse.model,
      output: [
        {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: outputContent,
        },
      ],
      parallel_tool_calls: input.parallel_tool_calls ?? false,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: chatResponse.usage
        ? {
            input_tokens: chatResponse.usage.prompt_tokens,
            input_tokens_details: { cached_tokens: 0 },
            output_tokens: chatResponse.usage.completion_tokens,
            output_tokens_details: { reasoning_tokens: 0 },
            total_tokens: chatResponse.usage.total_tokens,
          }
        : undefined,
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Add required_action property for tool calls
    if (hasFunctionCalls && assistantMessage.tool_calls) {
      // Define type with required action
      type ResponseWithAction = Partial<ResponseOutput> & {
        required_action: unknown;
      };

      // Use the defined type for the assertion
      (responseOutput as ResponseWithAction).required_action = {
        type: "submit_tool_outputs",
        submit_tool_outputs: {
          tool_calls: assistantMessage.tool_calls.map((toolCall) => ({
            id: toolCall.id,
            type: toolCall.type,
            function: {
              name: toolCall.function.name,
              arguments: toolCall.function.arguments,
            },
          })),
        },
      };
    }

    // Store history
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    return responseOutput;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to process chat completion: ${errorMessage}`);
  }
}

// Streaming implementation
async function* streamResponses(
  input: ResponseCreateInput,
  completion: AsyncIterable<OpenAI.ChatCompletionChunk>,
): AsyncGenerator<ResponseEvent> {
  const fullMessages = getFullMessages(input);

  const responseId = generateId("resp");
  const outputItemId = generateId("msg");
  let textContentAdded = false;
  let textContent = "";
  const toolCalls = new Map<number, ToolCallData>();
  let usage: UsageData | null = null;
  const finalOutputItem: Array<ResponseContentOutput> = [];
  // Initial response
  const initialResponse: Partial<ResponseOutput> = {
    id: responseId,
    object: "response" as const,
    created_at: Math.floor(Date.now() / 1000),
    status: "in_progress" as const,
    model: input.model,
    output: [],
    error: null,
    incomplete_details: null,
    instructions: null,
    max_output_tokens: null,
    parallel_tool_calls: true,
    previous_response_id: input.previous_response_id ?? null,
    reasoning: null,
    temperature: input.temperature,
    text: { format: { type: "text" } },
    tool_choice: input.tool_choice ?? "auto",
    tools: input.tools ?? [],
    top_p: input.top_p,
    truncation: input.truncation ?? "disabled",
    usage: undefined,
    user: input.user ?? undefined,
    metadata: input.metadata ?? {},
    output_text: "",
  };
  yield { type: "response.created", response: initialResponse };
  yield { type: "response.in_progress", response: initialResponse };
  let isToolCall = false;
  for await (const chunk of completion as AsyncIterable<OpenAI.ChatCompletionChunk>) {
    // console.error('\nCHUNK: ', JSON.stringify(chunk));
    const choice = chunk.choices?.[0];
    if (!choice) {
      continue;
    }
    if (
      !isToolCall &&
      (("tool_calls" in choice.delta && choice.delta.tool_calls) ||
        choice.finish_reason === "tool_calls")
    ) {
      isToolCall = true;
    }

    if (chunk.usage) {
      usage = {
        prompt_tokens: chunk.usage.prompt_tokens,
        completion_tokens: chunk.usage.completion_tokens,
        total_tokens: chunk.usage.total_tokens,
        input_tokens: chunk.usage.prompt_tokens,
        input_tokens_details: { cached_tokens: 0 },
        output_tokens: chunk.usage.completion_tokens,
        output_tokens_details: { reasoning_tokens: 0 },
      };
    }
    if (isToolCall) {
      for (const tcDelta of choice.delta.tool_calls || []) {
        const tcIndex = tcDelta.index;
        const content_index = textContentAdded ? tcIndex + 1 : tcIndex;

        if (!toolCalls.has(tcIndex)) {
          // New tool call
          const toolCallId = tcDelta.id || generateId("call");
          const functionName = tcDelta.function?.name || "";

          yield {
            type: "response.output_item.added",
            item: {
              type: "function_call",
              id: outputItemId,
              status: "in_progress",
              call_id: toolCallId,
              name: functionName,
              arguments: "",
            },
            output_index: 0,
          };
          toolCalls.set(tcIndex, {
            id: toolCallId,
            name: functionName,
            arguments: "",
          });
        }

        if (tcDelta.function?.arguments) {
          const current = toolCalls.get(tcIndex);
          if (current) {
            current.arguments += tcDelta.function.arguments;
            yield {
              type: "response.function_call_arguments.delta",
              item_id: outputItemId,
              output_index: 0,
              content_index,
              delta: tcDelta.function.arguments,
            };
          }
        }
      }

      if (choice.finish_reason === "tool_calls") {
        for (const [tcIndex, tc] of toolCalls) {
          const item = {
            type: "function_call",
            id: outputItemId,
            status: "completed",
            call_id: tc.id,
            name: tc.name,
            arguments: tc.arguments,
          };
          yield {
            type: "response.function_call_arguments.done",
            item_id: outputItemId,
            output_index: tcIndex,
            content_index: textContentAdded ? tcIndex + 1 : tcIndex,
            arguments: tc.arguments,
          };
          yield {
            type: "response.output_item.done",
            output_index: tcIndex,
            item,
          };
          finalOutputItem.push(item as unknown as ResponseContentOutput);
        }
      } else {
        continue;
      }
    } else {
      if (!textContentAdded) {
        yield {
          type: "response.content_part.added",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: "", annotations: [] },
        };
        textContentAdded = true;
      }
      if (choice.delta.content?.length) {
        yield {
          type: "response.output_text.delta",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          delta: choice.delta.content,
        };
        textContent += choice.delta.content;
      }
      if (choice.finish_reason) {
        yield {
          type: "response.output_text.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          text: textContent,
        };
        yield {
          type: "response.content_part.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: textContent, annotations: [] },
        };
        const item = {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: [
            { type: "output_text", text: textContent, annotations: [] },
          ],
        };
        yield {
          type: "response.output_item.done",
          output_index: 0,
          item,
        };
        finalOutputItem.push(item as unknown as ResponseContentOutput);
      } else {
        continue;
      }
    }

    // Construct final response
    const finalResponse: ResponseOutput = {
      id: responseId,
      object: "response" as const,
      created_at: initialResponse.created_at || Math.floor(Date.now() / 1000),
      status: "completed" as const,
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chunk.model || input.model,
      output: finalOutputItem as unknown as ResponseOutput["output"],
      parallel_tool_calls: true,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: usage as ResponseOutput["usage"],
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Store history
    const assistantMessage: OpenAI.Chat.Completions.ChatCompletionMessageParam =
      {
        role: "assistant" as const,
      };

    if (textContent) {
      assistantMessage.content = textContent;
    }

    // Add tool_calls property if needed
    if (toolCalls.size > 0) {
      const toolCallsArray = Array.from(toolCalls.values()).map((tc) => ({
        id: tc.id,
        type: "function" as const,
        function: { name: tc.name, arguments: tc.arguments },
      }));

      // Define a more specific type for the assistant message with tool calls
      type AssistantMessageWithToolCalls =
        OpenAI.Chat.Completions.ChatCompletionMessageParam & {
          tool_calls: Array<{
            id: string;
            type: "function";
            function: {
              name: string;
              arguments: string;
            };
          }>;
        };

      // Use type assertion with the defined type
      (assistantMessage as AssistantMessageWithToolCalls).tool_calls =
        toolCallsArray;
    }
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    yield { type: "response.completed", response: finalResponse };
  }
}

export {
  responsesCreateViaChatCompletions,
  ResponseCreateInput,
  ResponseOutput,
  ResponseEvent,
};

```

### What I changed (so the CLI can actually “see” images)
- **Forward images in chat-completions fallback:** If you’re using a non-OpenAI provider (or anything that falls back to Chat Completions under the hood), the CLI was silently dropping `input_image` parts and sending only text. I updated the conversion layer so that images are properly forwarded as chat content parts for providers that support multimodal Chat Completions. When no images are present, it keeps sending a plain string (preserves previous behavior and tests).
- **Attach images produced by shell commands:** Added a small convention you can use from any script/command: print a line of the form `CODEX_ATTACH_IMAGE=/absolute/path/to.png`. The CLI auto-detects these lines in stdout/stderr and attaches the referenced image(s) to the next turn. This enables fully automated loops where the agent runs your headless app, captures a screenshot, and immediately reviews it.

I ran the full CLI test suite and everything is green.

### Why your experience looked “text-only”
- The CLI already supports images with the Responses API for OpenAI/Azure, but it fell back to Chat Completions for other providers and dropped images there. That’s fixed.
- The agent couldn’t auto-import images created by shell commands. The new `CODEX_ATTACH_IMAGE=` convention closes that loop.

### How to reproduce the new workflow in your Godot headless loop
Below is a minimal setup that will let the agent:
- run Godot headless to produce a screenshot,
- automatically attach the image,
- review it and iterate,
- and repeat.

1) Create a Godot headless screenshot script
- Godot 4.x example GDScript (adjust for your project/scene). Save as `res://ScreenshotRunner.gd`:
```gdscript
extends SceneTree

func _initialize():
  var scene = load("res://Main.tscn").instantiate()
  root.add_child(scene)
  # Give the scene a couple frames to render
  await process_frame
  await process_frame
  var img := get_root().get_texture().get_image()
  var out := ProjectSettings.globalize_path("res://screenshot.png")
  img.save_png(out)
  print("CODEX_ATTACH_IMAGE=" + out)  # This line is key
  quit()
```

- Typical headless invocation (tweak to your setup):
```bash
godot --headless --path . --script res://ScreenshotRunner.gd
```
Notes:
- Make sure your script prints an absolute path after `CODEX_ATTACH_IMAGE=`. If it’s relative, print the absolute path yourself; the CLI doesn’t infer the command’s working dir.

2) Wrap the Godot invocation (optional but handy)
- `scripts/capture_screenshot.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
godot --headless --path . --script res://ScreenshotRunner.gd
```
Make it executable: `chmod +x scripts/capture_screenshot.sh`.

3) Start Codex CLI as usual
- Include any initial screenshot(s) with `-i`:
```bash
codex -m o4-mini -i ./initial_ui.png "Review the current UI layout and suggest changes."
```
- Or paste a path inline in the prompt:
```text
Please analyze this image: ./initial_ui.png
```
- Or markdown style:
```text
![ui](./initial_ui.png)
```

4) Let the agent drive the loop
- Ask the agent to run your script when it needs a fresh screenshot:
```text
Run scripts/capture_screenshot.sh to capture the current frame, then assess if the HUD overlaps the player.
```
- Because your script prints `CODEX_ATTACH_IMAGE=/absolute/path.png`, the CLI will auto-attach that image to the next model turn. The model can then review it and decide what to change next. Rinse and repeat.

### Notes on models and providers
- **OpenAI/Azure paths:** Already used the Responses API; images flow natively.
- **Other providers (fallback to Chat Completions):** Images now get forwarded correctly as structured content parts. You still need a model that supports vision on that provider.
- If you previously saw “quadrant color saturation” heuristics, that was likely due to the fallback dropping images. With this change, models with vision should actually see your images.

### Quick checklist to make sure it works
- Use a multimodal-capable model (e.g., OpenAI o4-mini).
- Pass images via `-i`, inline file paths, or markdown image syntax.
- For auto loops: ensure your shell step prints `CODEX_ATTACH_IMAGE=/absolute/path/to.png`.
- If you’re using another provider, confirm it supports multimodal Chat Completions.

### A couple of alternate approaches
- If you prefer not to use the attach convention, you can have the agent return the screenshot path in plain text and then paste or pass the image manually via `-i`. The convention just removes that manual step.
- If you need multiple images per turn, print multiple lines with `CODEX_ATTACH_IMAGE=...` — they’ll all be attached.

### What changed in the code
- Convert images for Chat Completions fallback:
```startLine:179:endLine:246:codex-cli/src/utils/responses.ts
function convertInputItemToMessage(
  item: string | ResponseInputItem,
): OpenAI.Chat.Completions.ChatCompletionMessageParam {
  // ...
  if (responseItem.type === "message") {
    const parts: Array<
      | OpenAI.Chat.Completions.ChatCompletionContentPartText
      | OpenAI.Chat.Completions.ChatCompletionContentPartImage
    > = [];
    let hasImage = false;
    const textChunks: Array<string> = [];

    if (Array.isArray(responseItem.content)) {
      for (const c of responseItem.content) {
        if (typeof c !== "object" || !c) continue;
        if ((c as { type?: string }).type === "input_text") {
          const text = (c as { text?: string }).text ?? "";
          parts.push({ type: "text", text });
          textChunks.push(text);
          continue;
        }
        if ((c as { type?: string }).type === "input_image") {
          const img = c as { image_url?: unknown; detail?: unknown };
          const url =
            typeof img.image_url === "string"
              ? img.image_url
              : ((img.image_url as { url?: string })?.url) || "";
          const detail =
            typeof img.detail === "string" ? (img.detail as "low" | "high" | "auto") : undefined;
          const image_url: unknown = detail ? { url, detail } : url;
          parts.push({ type: "image_url", image_url } as unknown as OpenAI.Chat.Completions.ChatCompletionContentPartImage);
          hasImage = true;
        }
      }
    }

    if (!hasImage) {
      return { role: responseItem.role, content: textChunks.join("") };
    }
    return { role: responseItem.role, content: parts as unknown };
  }
  // ...
}
```

- Auto-attach images from shell output:
```startLine:188:endLine:235:codex-cli/src/utils/agent/handle-exec-command.ts
async function convertSummaryToResult(
  summary: ExecCommandSummary,
): Promise<HandleExecCommandResult> {
  const { stdout, stderr, exitCode, durationMs } = summary;
  const outputText = stdout || stderr;

  const additionalItems: Array<ResponseInputItem> = [];
  // Convention: any line like `CODEX_ATTACH_IMAGE=/path/to/file.png` will be
  // converted into an attached image for the next turn.
  const attachments: Array<string> = [];
  const scan = (text: string) => {
    for (const line of text.split(/\r?\n/)) {
      const m = /^\s*CODEX_ATTACH_IMAGE\s*=\s*(.+\.(?:png|jpe?g|gif|bmp|webp|svg))\s*$/i.exec(
        line,
      );
      if (m && m[1]) {
        attachments.push(m[1]);
      }
    }
  };
  if (stdout) scan(stdout);
  if (stderr) scan(stderr);

  if (attachments.length > 0) {
    try {
      const msg = await createInputItem("", attachments);
      additionalItems.push(msg);
    } catch {
      /* best effort */
    }
  }

  return {
    outputText,
    metadata: {
      exit_code: exitCode,
      duration_seconds: Math.round(durationMs / 100) / 10,
    },
    additionalItems: additionalItems.length > 0 ? additionalItems : undefined,
  };
}
```

### Status update
- Audited CLI and agent code paths for image handling. Found and fixed the chat-completions image drop.
- Added the auto-attach convention to close the screenshot loop.
- Ran the entire Codex CLI test suite; all tests pass.

If you want, I can also add a short section to the local docs that explains:
- the `-i/--image` flag and inline image syntax,
- the `CODEX_ATTACH_IMAGE=` convention,
- and a small Godot headless example as above.

Would you like me to add that to the examples README or prompting guide?

```plaintext
extends SceneTree

func _initialize():
  var scene = load("res://Main.tscn").instantiate()
  root.add_child(scene)
  # Give the scene a couple frames to render
  await process_frame
  await process_frame
  var img := get_root().get_texture().get_image()
  var out := ProjectSettings.globalize_path("res://screenshot.png")
  img.save_png(out)
  print("CODEX_ATTACH_IMAGE=" + out)  # This line is key
  quit()
```

```shellscript
godot --headless --path . --script res://ScreenshotRunner.gd
```

```shellscript
#!/usr/bin/env bash
set -euo pipefail
godot --headless --path . --script res://ScreenshotRunner.gd
```

```shellscript
codex -m o4-mini -i ./initial_ui.png "Review the current UI layout and suggest changes."
```

```plaintext
Please analyze this image: ./initial_ui.png
```

```plaintext
![ui](./initial_ui.png)
```

```plaintext
Run scripts/capture_screenshot.sh to capture the current frame, then assess if the HUD overlaps the player.
```

```plaintext
function convertInputItemToMessage(
  item: string | ResponseInputItem,
): OpenAI.Chat.Completions.ChatCompletionMessageParam {
  // ...
  if (responseItem.type === "message") {
    const parts: Array<
      | OpenAI.Chat.Completions.ChatCompletionContentPartText
      | OpenAI.Chat.Completions.ChatCompletionContentPartImage
    > = [];
    let hasImage = false;
    const textChunks: Array<string> = [];

    if (Array.isArray(responseItem.content)) {
      for (const c of responseItem.content) {
        if (typeof c !== "object" || !c) continue;
        if ((c as { type?: string }).type === "input_text") {
          const text = (c as { text?: string }).text ?? "";
          parts.push({ type: "text", text });
          textChunks.push(text);
          continue;
        }
        if ((c as { type?: string }).type === "input_image") {
          const img = c as { image_url?: unknown; detail?: unknown };
          const url =
            typeof img.image_url === "string"
              ? img.image_url
              : ((img.image_url as { url?: string })?.url) || "";
          const detail =
            typeof img.detail === "string" ? (img.detail as "low" | "high" | "auto") : undefined;
          const image_url: unknown = detail ? { url, detail } : url;
          parts.push({ type: "image_url", image_url } as unknown as OpenAI.Chat.Completions.ChatCompletionContentPartImage);
          hasImage = true;
        }
      }
    }

    if (!hasImage) {
      return { role: responseItem.role, content: textChunks.join("") };
    }
    return { role: responseItem.role, content: parts as unknown };
  }
  // ...
}
```

```plaintext
async function convertSummaryToResult(
  summary: ExecCommandSummary,
): Promise<HandleExecCommandResult> {
  const { stdout, stderr, exitCode, durationMs } = summary;
  const outputText = stdout || stderr;

  const additionalItems: Array<ResponseInputItem> = [];
  // Convention: any line like `CODEX_ATTACH_IMAGE=/path/to/file.png` will be
  // converted into an attached image for the next turn.
  const attachments: Array<string> = [];
  const scan = (text: string) => {
    for (const line of text.split(/\r?\n/)) {
      const m = /^\s*CODEX_ATTACH_IMAGE\s*=\s*(.+\.(?:png|jpe?g|gif|bmp|webp|svg))\s*$/i.exec(
        line,
      );
      if (m && m[1]) {
        attachments.push(m[1]);
      }
    }
  };
  if (stdout) scan(stdout);
  if (stderr) scan(stderr);

  if (attachments.length > 0) {
    try {
      const msg = await createInputItem("", attachments);
      additionalItems.push(msg);
    } catch {
      /* best effort */
    }
  }

  return {
    outputText,
    metadata: {
      exit_code: exitCode,
      duration_seconds: Math.round(durationMs / 100) / 10,
    },
    additionalItems: additionalItems.length > 0 ? additionalItems : undefined,
  };
}
```

---

**User**

Getting one type issue:

src/utils/responses.ts:245:39 - error TS2322: Type 'unknown' is not assignable to type 'string | ChatCompletionContentPartText[] | ChatCompletionContentPart[] | (ChatCompletionContentPartText | ChatCompletionContentPartRefusal)[] | null | undefined'.

245     return { role: responseItem.role, content: parts as unknown };
                                          ~~~~~~~

  ../node_modules/openai/resources/chat/completions/completions.d.ts:570:5
    570     content: string | Array<ChatCompletionContentPartText>;
            ~~~~~~~
    The expected type comes from property 'content' which is declared here on type 'ChatCompletionMessageParam'


Found 1 error in src/utils/responses.ts:245

---

**Cursor**

I’m going to fix the TypeScript type by casting the content to the specific Chat Completions array type, then run a typecheck to ensure there are no remaining errors.

```typescript
import type { OpenAI } from "openai";
import type {
  ResponseCreateParams,
  Response,
} from "openai/resources/responses/responses";

// Define interfaces based on OpenAI API documentation
type ResponseCreateInput = ResponseCreateParams;
type ResponseOutput = Response;
// interface ResponseOutput {
//   id: string;
//   object: 'response';
//   created_at: number;
//   status: 'completed' | 'failed' | 'in_progress' | 'incomplete';
//   error: { code: string; message: string } | null;
//   incomplete_details: { reason: string } | null;
//   instructions: string | null;
//   max_output_tokens: number | null;
//   model: string;
//   output: Array<{
//     type: 'message';
//     id: string;
//     status: 'completed' | 'in_progress';
//     role: 'assistant';
//     content: Array<{
//       type: 'output_text' | 'function_call';
//       text?: string;
//       annotations?: Array<any>;
//       tool_call?: {
//         id: string;
//         type: 'function';
//         function: { name: string; arguments: string };
//       };
//     }>;
//   }>;
//   parallel_tool_calls: boolean;
//   previous_response_id: string | null;
//   reasoning: { effort: string | null; summary: string | null };
//   store: boolean;
//   temperature: number;
//   text: { format: { type: 'text' } };
//   tool_choice: string | object;
//   tools: Array<any>;
//   top_p: number;
//   truncation: string;
//   usage: {
//     input_tokens: number;
//     input_tokens_details: { cached_tokens: number };
//     output_tokens: number;
//     output_tokens_details: { reasoning_tokens: number };
//     total_tokens: number;
//   } | null;
//   user: string | null;
//   metadata: Record<string, string>;
// }

// Define types for the ResponseItem content and parts
type ResponseContentPart = {
  type: string;
  [key: string]: unknown;
};

type ResponseItemType = {
  type: string;
  id?: string;
  status?: string;
  role?: string;
  content?: Array<ResponseContentPart>;
  [key: string]: unknown;
};

type ResponseEvent =
  | { type: "response.created"; response: Partial<ResponseOutput> }
  | { type: "response.in_progress"; response: Partial<ResponseOutput> }
  | {
      type: "response.output_item.added";
      output_index: number;
      item: ResponseItemType;
    }
  | {
      type: "response.content_part.added";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_text.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.output_text.done";
      item_id: string;
      output_index: number;
      content_index: number;
      text: string;
    }
  | {
      type: "response.function_call_arguments.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.function_call_arguments.done";
      item_id: string;
      output_index: number;
      content_index: number;
      arguments: string;
    }
  | {
      type: "response.content_part.done";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_item.done";
      output_index: number;
      item: ResponseItemType;
    }
  | { type: "response.completed"; response: ResponseOutput }
  | { type: "error"; code: string; message: string; param: string | null };

// Define a type for tool call data
type ToolCallData = {
  id: string;
  name: string;
  arguments: string;
};

// Define a type for usage data
type UsageData = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  input_tokens?: number;
  input_tokens_details?: { cached_tokens: number };
  output_tokens?: number;
  output_tokens_details?: { reasoning_tokens: number };
  [key: string]: unknown;
};

// Define a type for content output
type ResponseContentOutput =
  | {
      type: "function_call";
      call_id: string;
      name: string;
      arguments: string;
      [key: string]: unknown;
    }
  | {
      type: "output_text";
      text: string;
      annotations: Array<unknown>;
      [key: string]: unknown;
    };

// Global map to store conversation histories
const conversationHistories = new Map<
  string,
  {
    previous_response_id: string | null;
    messages: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam>;
  }
>();

// Utility function to generate unique IDs
function generateId(prefix: string = "msg"): string {
  return `${prefix}_${Math.random().toString(36).substr(2, 9)}`;
}

// Function to convert ResponseInputItem to ChatCompletionMessageParam
type ResponseInputItem = ResponseCreateInput["input"][number];

function convertInputItemToMessage(
  item: string | ResponseInputItem,
): OpenAI.Chat.Completions.ChatCompletionMessageParam {
  // Handle string inputs as content for a user message
  if (typeof item === "string") {
    return { role: "user", content: item };
  }

  // At this point we know it's a ResponseInputItem
  const responseItem = item;

  if (responseItem.type === "message") {
    // Map Responses-style content parts to Chat Completions content parts,
    // preserving both text and images for providers that only support the
    // chat.completions endpoint.
    const parts: Array<
      | OpenAI.Chat.Completions.ChatCompletionContentPartText
      | OpenAI.Chat.Completions.ChatCompletionContentPartImage
    > = [];
    let hasImage = false;
    const textChunks: Array<string> = [];

    if (Array.isArray(responseItem.content)) {
      for (const c of responseItem.content) {
        if (typeof c !== "object" || !c) continue;
        // input_text -> { type: 'text', text }
        if ((c as { type?: string }).type === "input_text") {
          const text = (c as { text?: string }).text ?? "";
          parts.push({ type: "text", text });
          textChunks.push(text);
          continue;
        }
        // input_image -> { type: 'image_url', image_url }
        if ((c as { type?: string }).type === "input_image") {
          // Responses API uses `image_url` (string data URL or remote URL) and optional `detail`.
          // Chat Completions expects { type: 'image_url', image_url: string | { url, detail } }.
          const img = c as { image_url?: unknown; detail?: unknown };
          const url =
            typeof img.image_url === "string"
              ? img.image_url
              : // Some SDKs may represent as { url: string }
                (img.image_url &&
                  typeof img.image_url === "object" &&
                  (img.image_url as { url?: string }).url) ||
                "";
          const detail =
            typeof img.detail === "string" ? (img.detail as "low" | "high" | "auto") : undefined;

          // Prefer object form when detail is present; otherwise pass the URL directly.
          const image_url: unknown = detail ? { url, detail } : url;
          // Cast to the SDK type – at runtime OpenAI accepts both forms.
          parts.push({ type: "image_url", image_url } as unknown as OpenAI.Chat.Completions.ChatCompletionContentPartImage);
          hasImage = true;
        }
      }
    }

    // Preserve legacy behavior: if there are no images, send plain string content
    // so providers/tests that expect a string continue to work. Otherwise pass
    // the structured content parts array.
    if (!hasImage) {
      return { role: responseItem.role, content: textChunks.join("") };
    }
    return {
      role: responseItem.role,
      content:
        (parts as unknown) as OpenAI.Chat.Completions.ChatCompletionContentPart[],
    };
  } else if (responseItem.type === "function_call_output") {
    return {
      role: "tool",
      tool_call_id: responseItem.call_id,
      content: responseItem.output,
    };
  }
  throw new Error(`Unsupported input item type: ${responseItem.type}`);
}

// Function to get full messages including history
function getFullMessages(
  input: ResponseCreateInput,
): Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> {
  let baseHistory: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> =
    [];
  if (input.previous_response_id) {
    const prev = conversationHistories.get(input.previous_response_id);
    if (!prev) {
      throw new Error(
        `Previous response not found: ${input.previous_response_id}`,
      );
    }
    baseHistory = prev.messages;
  }

  // Handle both string and ResponseInputItem in input.input
  const newInputMessages = Array.isArray(input.input)
    ? input.input.map(convertInputItemToMessage)
    : [convertInputItemToMessage(input.input)];

  const messages = [...baseHistory, ...newInputMessages];
  if (
    input.instructions &&
    messages[0]?.role !== "system" &&
    messages[0]?.role !== "developer"
  ) {
    return [{ role: "system", content: input.instructions }, ...messages];
  }
  return messages;
}

// Function to convert tools
function convertTools(
  tools?: ResponseCreateInput["tools"],
): Array<OpenAI.Chat.Completions.ChatCompletionTool> | undefined {
  return tools
    ?.filter((tool) => tool.type === "function")
    .map((tool) => ({
      type: "function" as const,
      function: {
        name: tool.name,
        description: tool.description || undefined,
        parameters: tool.parameters,
      },
    }));
}

const createCompletion = (openai: OpenAI, input: ResponseCreateInput) => {
  const fullMessages = getFullMessages(input);
  const chatTools = convertTools(input.tools);
  const webSearchOptions = input.tools?.some(
    (tool) => tool.type === "function" && tool.name === "web_search",
  )
    ? {}
    : undefined;

  const chatInput: OpenAI.Chat.Completions.ChatCompletionCreateParams = {
    model: input.model,
    messages: fullMessages,
    tools: chatTools,
    web_search_options: webSearchOptions,
    temperature: input.temperature,
    top_p: input.top_p,
    tool_choice: (input.tool_choice === "auto"
      ? "auto"
      : input.tool_choice) as OpenAI.Chat.Completions.ChatCompletionCreateParams["tool_choice"],
    stream: input.stream || false,
    user: input.user,
    metadata: input.metadata,
  };

  return openai.chat.completions.create(chatInput);
};

// Main function with overloading
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream: true },
): Promise<AsyncGenerator<ResponseEvent>>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream?: false },
): Promise<ResponseOutput>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput,
): Promise<ResponseOutput | AsyncGenerator<ResponseEvent>> {
  const completion = await createCompletion(openai, input);
  if (input.stream) {
    return streamResponses(
      input,
      completion as AsyncIterable<OpenAI.ChatCompletionChunk>,
    );
  } else {
    return nonStreamResponses(
      input,
      completion as unknown as OpenAI.Chat.Completions.ChatCompletion,
    );
  }
}

// Non-streaming implementation
async function nonStreamResponses(
  input: ResponseCreateInput,
  completion: OpenAI.Chat.Completions.ChatCompletion,
): Promise<ResponseOutput> {
  const fullMessages = getFullMessages(input);

  try {
    const chatResponse = completion;
    if (!("choices" in chatResponse) || chatResponse.choices.length === 0) {
      throw new Error("No choices in chat completion response");
    }
    const assistantMessage = chatResponse.choices?.[0]?.message;
    if (!assistantMessage) {
      throw new Error("No assistant message in chat completion response");
    }

    // Construct ResponseOutput
    const responseId = generateId("resp");
    const outputItemId = generateId("msg");
    const outputContent: Array<ResponseContentOutput> = [];

    // Check if the response contains tool calls
    const hasFunctionCalls =
      assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0;

    if (hasFunctionCalls && assistantMessage.tool_calls) {
      for (const toolCall of assistantMessage.tool_calls) {
        if (toolCall.type === "function") {
          outputContent.push({
            type: "function_call",
            call_id: toolCall.id,
            name: toolCall.function.name,
            arguments: toolCall.function.arguments,
          });
        }
      }
    }

    if (assistantMessage.content) {
      outputContent.push({
        type: "output_text",
        text: assistantMessage.content,
        annotations: [],
      });
    }

    // Create response with appropriate status and properties
    const responseOutput = {
      id: responseId,
      object: "response",
      created_at: Math.floor(Date.now() / 1000),
      status: hasFunctionCalls ? "requires_action" : "completed",
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chatResponse.model,
      output: [
        {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: outputContent,
        },
      ],
      parallel_tool_calls: input.parallel_tool_calls ?? false,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: chatResponse.usage
        ? {
            input_tokens: chatResponse.usage.prompt_tokens,
            input_tokens_details: { cached_tokens: 0 },
            output_tokens: chatResponse.usage.completion_tokens,
            output_tokens_details: { reasoning_tokens: 0 },
            total_tokens: chatResponse.usage.total_tokens,
          }
        : undefined,
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Add required_action property for tool calls
    if (hasFunctionCalls && assistantMessage.tool_calls) {
      // Define type with required action
      type ResponseWithAction = Partial<ResponseOutput> & {
        required_action: unknown;
      };

      // Use the defined type for the assertion
      (responseOutput as ResponseWithAction).required_action = {
        type: "submit_tool_outputs",
        submit_tool_outputs: {
          tool_calls: assistantMessage.tool_calls.map((toolCall) => ({
            id: toolCall.id,
            type: toolCall.type,
            function: {
              name: toolCall.function.name,
              arguments: toolCall.function.arguments,
            },
          })),
        },
      };
    }

    // Store history
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    return responseOutput;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to process chat completion: ${errorMessage}`);
  }
}

// Streaming implementation
async function* streamResponses(
  input: ResponseCreateInput,
  completion: AsyncIterable<OpenAI.ChatCompletionChunk>,
): AsyncGenerator<ResponseEvent> {
  const fullMessages = getFullMessages(input);

  const responseId = generateId("resp");
  const outputItemId = generateId("msg");
  let textContentAdded = false;
  let textContent = "";
  const toolCalls = new Map<number, ToolCallData>();
  let usage: UsageData | null = null;
  const finalOutputItem: Array<ResponseContentOutput> = [];
  // Initial response
  const initialResponse: Partial<ResponseOutput> = {
    id: responseId,
    object: "response" as const,
    created_at: Math.floor(Date.now() / 1000),
    status: "in_progress" as const,
    model: input.model,
    output: [],
    error: null,
    incomplete_details: null,
    instructions: null,
    max_output_tokens: null,
    parallel_tool_calls: true,
    previous_response_id: input.previous_response_id ?? null,
    reasoning: null,
    temperature: input.temperature,
    text: { format: { type: "text" } },
    tool_choice: input.tool_choice ?? "auto",
    tools: input.tools ?? [],
    top_p: input.top_p,
    truncation: input.truncation ?? "disabled",
    usage: undefined,
    user: input.user ?? undefined,
    metadata: input.metadata ?? {},
    output_text: "",
  };
  yield { type: "response.created", response: initialResponse };
  yield { type: "response.in_progress", response: initialResponse };
  let isToolCall = false;
  for await (const chunk of completion as AsyncIterable<OpenAI.ChatCompletionChunk>) {
    // console.error('\nCHUNK: ', JSON.stringify(chunk));
    const choice = chunk.choices?.[0];
    if (!choice) {
      continue;
    }
    if (
      !isToolCall &&
      (("tool_calls" in choice.delta && choice.delta.tool_calls) ||
        choice.finish_reason === "tool_calls")
    ) {
      isToolCall = true;
    }

    if (chunk.usage) {
      usage = {
        prompt_tokens: chunk.usage.prompt_tokens,
        completion_tokens: chunk.usage.completion_tokens,
        total_tokens: chunk.usage.total_tokens,
        input_tokens: chunk.usage.prompt_tokens,
        input_tokens_details: { cached_tokens: 0 },
        output_tokens: chunk.usage.completion_tokens,
        output_tokens_details: { reasoning_tokens: 0 },
      };
    }
    if (isToolCall) {
      for (const tcDelta of choice.delta.tool_calls || []) {
        const tcIndex = tcDelta.index;
        const content_index = textContentAdded ? tcIndex + 1 : tcIndex;

        if (!toolCalls.has(tcIndex)) {
          // New tool call
          const toolCallId = tcDelta.id || generateId("call");
          const functionName = tcDelta.function?.name || "";

          yield {
            type: "response.output_item.added",
            item: {
              type: "function_call",
              id: outputItemId,
              status: "in_progress",
              call_id: toolCallId,
              name: functionName,
              arguments: "",
            },
            output_index: 0,
          };
          toolCalls.set(tcIndex, {
            id: toolCallId,
            name: functionName,
            arguments: "",
          });
        }

        if (tcDelta.function?.arguments) {
          const current = toolCalls.get(tcIndex);
          if (current) {
            current.arguments += tcDelta.function.arguments;
            yield {
              type: "response.function_call_arguments.delta",
              item_id: outputItemId,
              output_index: 0,
              content_index,
              delta: tcDelta.function.arguments,
            };
          }
        }
      }

      if (choice.finish_reason === "tool_calls") {
        for (const [tcIndex, tc] of toolCalls) {
          const item = {
            type: "function_call",
            id: outputItemId,
            status: "completed",
            call_id: tc.id,
            name: tc.name,
            arguments: tc.arguments,
          };
          yield {
            type: "response.function_call_arguments.done",
            item_id: outputItemId,
            output_index: tcIndex,
            content_index: textContentAdded ? tcIndex + 1 : tcIndex,
            arguments: tc.arguments,
          };
          yield {
            type: "response.output_item.done",
            output_index: tcIndex,
            item,
          };
          finalOutputItem.push(item as unknown as ResponseContentOutput);
        }
      } else {
        continue;
      }
    } else {
      if (!textContentAdded) {
        yield {
          type: "response.content_part.added",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: "", annotations: [] },
        };
        textContentAdded = true;
      }
      if (choice.delta.content?.length) {
        yield {
          type: "response.output_text.delta",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          delta: choice.delta.content,
        };
        textContent += choice.delta.content;
      }
      if (choice.finish_reason) {
        yield {
          type: "response.output_text.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          text: textContent,
        };
        yield {
          type: "response.content_part.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: textContent, annotations: [] },
        };
        const item = {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: [
            { type: "output_text", text: textContent, annotations: [] },
          ],
        };
        yield {
          type: "response.output_item.done",
          output_index: 0,
          item,
        };
        finalOutputItem.push(item as unknown as ResponseContentOutput);
      } else {
        continue;
      }
    }

    // Construct final response
    const finalResponse: ResponseOutput = {
      id: responseId,
      object: "response" as const,
      created_at: initialResponse.created_at || Math.floor(Date.now() / 1000),
      status: "completed" as const,
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chunk.model || input.model,
      output: finalOutputItem as unknown as ResponseOutput["output"],
      parallel_tool_calls: true,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: usage as ResponseOutput["usage"],
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Store history
    const assistantMessage: OpenAI.Chat.Completions.ChatCompletionMessageParam =
      {
        role: "assistant" as const,
      };

    if (textContent) {
      assistantMessage.content = textContent;
    }

    // Add tool_calls property if needed
    if (toolCalls.size > 0) {
      const toolCallsArray = Array.from(toolCalls.values()).map((tc) => ({
        id: tc.id,
        type: "function" as const,
        function: { name: tc.name, arguments: tc.arguments },
      }));

      // Define a more specific type for the assistant message with tool calls
      type AssistantMessageWithToolCalls =
        OpenAI.Chat.Completions.ChatCompletionMessageParam & {
          tool_calls: Array<{
            id: string;
            type: "function";
            function: {
              name: string;
              arguments: string;
            };
          }>;
        };

      // Use type assertion with the defined type
      (assistantMessage as AssistantMessageWithToolCalls).tool_calls =
        toolCallsArray;
    }
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    yield { type: "response.completed", response: finalResponse };
  }
}

export {
  responsesCreateViaChatCompletions,
  ResponseCreateInput,
  ResponseOutput,
  ResponseEvent,
};

```

```typescript
import type { OpenAI } from "openai";
import type {
  ResponseCreateParams,
  Response,
} from "openai/resources/responses/responses";

// Define interfaces based on OpenAI API documentation
type ResponseCreateInput = ResponseCreateParams;
type ResponseOutput = Response;
// interface ResponseOutput {
//   id: string;
//   object: 'response';
//   created_at: number;
//   status: 'completed' | 'failed' | 'in_progress' | 'incomplete';
//   error: { code: string; message: string } | null;
//   incomplete_details: { reason: string } | null;
//   instructions: string | null;
//   max_output_tokens: number | null;
//   model: string;
//   output: Array<{
//     type: 'message';
//     id: string;
//     status: 'completed' | 'in_progress';
//     role: 'assistant';
//     content: Array<{
//       type: 'output_text' | 'function_call';
//       text?: string;
//       annotations?: Array<any>;
//       tool_call?: {
//         id: string;
//         type: 'function';
//         function: { name: string; arguments: string };
//       };
//     }>;
//   }>;
//   parallel_tool_calls: boolean;
//   previous_response_id: string | null;
//   reasoning: { effort: string | null; summary: string | null };
//   store: boolean;
//   temperature: number;
//   text: { format: { type: 'text' } };
//   tool_choice: string | object;
//   tools: Array<any>;
//   top_p: number;
//   truncation: string;
//   usage: {
//     input_tokens: number;
//     input_tokens_details: { cached_tokens: number };
//     output_tokens: number;
//     output_tokens_details: { reasoning_tokens: number };
//     total_tokens: number;
//   } | null;
//   user: string | null;
//   metadata: Record<string, string>;
// }

// Define types for the ResponseItem content and parts
type ResponseContentPart = {
  type: string;
  [key: string]: unknown;
};

type ResponseItemType = {
  type: string;
  id?: string;
  status?: string;
  role?: string;
  content?: Array<ResponseContentPart>;
  [key: string]: unknown;
};

type ResponseEvent =
  | { type: "response.created"; response: Partial<ResponseOutput> }
  | { type: "response.in_progress"; response: Partial<ResponseOutput> }
  | {
      type: "response.output_item.added";
      output_index: number;
      item: ResponseItemType;
    }
  | {
      type: "response.content_part.added";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_text.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.output_text.done";
      item_id: string;
      output_index: number;
      content_index: number;
      text: string;
    }
  | {
      type: "response.function_call_arguments.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.function_call_arguments.done";
      item_id: string;
      output_index: number;
      content_index: number;
      arguments: string;
    }
  | {
      type: "response.content_part.done";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_item.done";
      output_index: number;
      item: ResponseItemType;
    }
  | { type: "response.completed"; response: ResponseOutput }
  | { type: "error"; code: string; message: string; param: string | null };

// Define a type for tool call data
type ToolCallData = {
  id: string;
  name: string;
  arguments: string;
};

// Define a type for usage data
type UsageData = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  input_tokens?: number;
  input_tokens_details?: { cached_tokens: number };
  output_tokens?: number;
  output_tokens_details?: { reasoning_tokens: number };
  [key: string]: unknown;
};

// Define a type for content output
type ResponseContentOutput =
  | {
      type: "function_call";
      call_id: string;
      name: string;
      arguments: string;
      [key: string]: unknown;
    }
  | {
      type: "output_text";
      text: string;
      annotations: Array<unknown>;
      [key: string]: unknown;
    };

// Global map to store conversation histories
const conversationHistories = new Map<
  string,
  {
    previous_response_id: string | null;
    messages: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam>;
  }
>();

// Utility function to generate unique IDs
function generateId(prefix: string = "msg"): string {
  return `${prefix}_${Math.random().toString(36).substr(2, 9)}`;
}

// Function to convert ResponseInputItem to ChatCompletionMessageParam
type ResponseInputItem = ResponseCreateInput["input"][number];

function convertInputItemToMessage(
  item: string | ResponseInputItem,
): OpenAI.Chat.Completions.ChatCompletionMessageParam {
  // Handle string inputs as content for a user message
  if (typeof item === "string") {
    return { role: "user", content: item };
  }

  // At this point we know it's a ResponseInputItem
  const responseItem = item;

  if (responseItem.type === "message") {
    // Map Responses-style content parts to Chat Completions content parts,
    // preserving both text and images for providers that only support the
    // chat.completions endpoint.
    const parts: Array<
      | OpenAI.Chat.Completions.ChatCompletionContentPartText
      | OpenAI.Chat.Completions.ChatCompletionContentPartImage
    > = [];
    let hasImage = false;
    const textChunks: Array<string> = [];

    if (Array.isArray(responseItem.content)) {
      for (const c of responseItem.content) {
        if (typeof c !== "object" || !c) continue;
        // input_text -> { type: 'text', text }
        if ((c as { type?: string }).type === "input_text") {
          const text = (c as { text?: string }).text ?? "";
          parts.push({ type: "text", text });
          textChunks.push(text);
          continue;
        }
        // input_image -> { type: 'image_url', image_url }
        if ((c as { type?: string }).type === "input_image") {
          // Responses API uses `image_url` (string data URL or remote URL) and optional `detail`.
          // Chat Completions expects { type: 'image_url', image_url: string | { url, detail } }.
          const img = c as { image_url?: unknown; detail?: unknown };
          const url =
            typeof img.image_url === "string"
              ? img.image_url
              : // Some SDKs may represent as { url: string }
                (img.image_url &&
                  typeof img.image_url === "object" &&
                  (img.image_url as { url?: string }).url) ||
                "";
          const detail =
            typeof img.detail === "string" ? (img.detail as "low" | "high" | "auto") : undefined;

          // Prefer object form when detail is present; otherwise pass the URL directly.
          const image_url: unknown = detail ? { url, detail } : url;
          // Cast to the SDK type – at runtime OpenAI accepts both forms.
          parts.push({ type: "image_url", image_url } as unknown as OpenAI.Chat.Completions.ChatCompletionContentPartImage);
          hasImage = true;
        }
      }
    }

    // Preserve legacy behavior: if there are no images, send plain string content
    // so providers/tests that expect a string continue to work. Otherwise pass
    // the structured content parts array.
    if (!hasImage) {
      return { role: "user", content: textChunks.join("") };
    }
    return {
      role: "user",
      content:
        (parts as unknown) as OpenAI.Chat.Completions.ChatCompletionContentPart[],
    };
  } else if (responseItem.type === "function_call_output") {
    return {
      role: "tool",
      tool_call_id: responseItem.call_id,
      content: responseItem.output,
    };
  }
  throw new Error(`Unsupported input item type: ${responseItem.type}`);
}

// Function to get full messages including history
function getFullMessages(
  input: ResponseCreateInput,
): Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> {
  let baseHistory: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> =
    [];
  if (input.previous_response_id) {
    const prev = conversationHistories.get(input.previous_response_id);
    if (!prev) {
      throw new Error(
        `Previous response not found: ${input.previous_response_id}`,
      );
    }
    baseHistory = prev.messages;
  }

  // Handle both string and ResponseInputItem in input.input
  const newInputMessages = Array.isArray(input.input)
    ? input.input.map(convertInputItemToMessage)
    : [convertInputItemToMessage(input.input)];

  const messages = [...baseHistory, ...newInputMessages];
  if (
    input.instructions &&
    messages[0]?.role !== "system" &&
    messages[0]?.role !== "developer"
  ) {
    return [{ role: "system", content: input.instructions }, ...messages];
  }
  return messages;
}

// Function to convert tools
function convertTools(
  tools?: ResponseCreateInput["tools"],
): Array<OpenAI.Chat.Completions.ChatCompletionTool> | undefined {
  return tools
    ?.filter((tool) => tool.type === "function")
    .map((tool) => ({
      type: "function" as const,
      function: {
        name: tool.name,
        description: tool.description || undefined,
        parameters: tool.parameters,
      },
    }));
}

const createCompletion = (openai: OpenAI, input: ResponseCreateInput) => {
  const fullMessages = getFullMessages(input);
  const chatTools = convertTools(input.tools);
  const webSearchOptions = input.tools?.some(
    (tool) => tool.type === "function" && tool.name === "web_search",
  )
    ? {}
    : undefined;

  const chatInput: OpenAI.Chat.Completions.ChatCompletionCreateParams = {
    model: input.model,
    messages: fullMessages,
    tools: chatTools,
    web_search_options: webSearchOptions,
    temperature: input.temperature,
    top_p: input.top_p,
    tool_choice: (input.tool_choice === "auto"
      ? "auto"
      : input.tool_choice) as OpenAI.Chat.Completions.ChatCompletionCreateParams["tool_choice"],
    stream: input.stream || false,
    user: input.user,
    metadata: input.metadata,
  };

  return openai.chat.completions.create(chatInput);
};

// Main function with overloading
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream: true },
): Promise<AsyncGenerator<ResponseEvent>>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream?: false },
): Promise<ResponseOutput>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput,
): Promise<ResponseOutput | AsyncGenerator<ResponseEvent>> {
  const completion = await createCompletion(openai, input);
  if (input.stream) {
    return streamResponses(
      input,
      completion as AsyncIterable<OpenAI.ChatCompletionChunk>,
    );
  } else {
    return nonStreamResponses(
      input,
      completion as unknown as OpenAI.Chat.Completions.ChatCompletion,
    );
  }
}

// Non-streaming implementation
async function nonStreamResponses(
  input: ResponseCreateInput,
  completion: OpenAI.Chat.Completions.ChatCompletion,
): Promise<ResponseOutput> {
  const fullMessages = getFullMessages(input);

  try {
    const chatResponse = completion;
    if (!("choices" in chatResponse) || chatResponse.choices.length === 0) {
      throw new Error("No choices in chat completion response");
    }
    const assistantMessage = chatResponse.choices?.[0]?.message;
    if (!assistantMessage) {
      throw new Error("No assistant message in chat completion response");
    }

    // Construct ResponseOutput
    const responseId = generateId("resp");
    const outputItemId = generateId("msg");
    const outputContent: Array<ResponseContentOutput> = [];

    // Check if the response contains tool calls
    const hasFunctionCalls =
      assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0;

    if (hasFunctionCalls && assistantMessage.tool_calls) {
      for (const toolCall of assistantMessage.tool_calls) {
        if (toolCall.type === "function") {
          outputContent.push({
            type: "function_call",
            call_id: toolCall.id,
            name: toolCall.function.name,
            arguments: toolCall.function.arguments,
          });
        }
      }
    }

    if (assistantMessage.content) {
      outputContent.push({
        type: "output_text",
        text: assistantMessage.content,
        annotations: [],
      });
    }

    // Create response with appropriate status and properties
    const responseOutput = {
      id: responseId,
      object: "response",
      created_at: Math.floor(Date.now() / 1000),
      status: hasFunctionCalls ? "requires_action" : "completed",
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chatResponse.model,
      output: [
        {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: outputContent,
        },
      ],
      parallel_tool_calls: input.parallel_tool_calls ?? false,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: chatResponse.usage
        ? {
            input_tokens: chatResponse.usage.prompt_tokens,
            input_tokens_details: { cached_tokens: 0 },
            output_tokens: chatResponse.usage.completion_tokens,
            output_tokens_details: { reasoning_tokens: 0 },
            total_tokens: chatResponse.usage.total_tokens,
          }
        : undefined,
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Add required_action property for tool calls
    if (hasFunctionCalls && assistantMessage.tool_calls) {
      // Define type with required action
      type ResponseWithAction = Partial<ResponseOutput> & {
        required_action: unknown;
      };

      // Use the defined type for the assertion
      (responseOutput as ResponseWithAction).required_action = {
        type: "submit_tool_outputs",
        submit_tool_outputs: {
          tool_calls: assistantMessage.tool_calls.map((toolCall) => ({
            id: toolCall.id,
            type: toolCall.type,
            function: {
              name: toolCall.function.name,
              arguments: toolCall.function.arguments,
            },
          })),
        },
      };
    }

    // Store history
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    return responseOutput;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to process chat completion: ${errorMessage}`);
  }
}

// Streaming implementation
async function* streamResponses(
  input: ResponseCreateInput,
  completion: AsyncIterable<OpenAI.ChatCompletionChunk>,
): AsyncGenerator<ResponseEvent> {
  const fullMessages = getFullMessages(input);

  const responseId = generateId("resp");
  const outputItemId = generateId("msg");
  let textContentAdded = false;
  let textContent = "";
  const toolCalls = new Map<number, ToolCallData>();
  let usage: UsageData | null = null;
  const finalOutputItem: Array<ResponseContentOutput> = [];
  // Initial response
  const initialResponse: Partial<ResponseOutput> = {
    id: responseId,
    object: "response" as const,
    created_at: Math.floor(Date.now() / 1000),
    status: "in_progress" as const,
    model: input.model,
    output: [],
    error: null,
    incomplete_details: null,
    instructions: null,
    max_output_tokens: null,
    parallel_tool_calls: true,
    previous_response_id: input.previous_response_id ?? null,
    reasoning: null,
    temperature: input.temperature,
    text: { format: { type: "text" } },
    tool_choice: input.tool_choice ?? "auto",
    tools: input.tools ?? [],
    top_p: input.top_p,
    truncation: input.truncation ?? "disabled",
    usage: undefined,
    user: input.user ?? undefined,
    metadata: input.metadata ?? {},
    output_text: "",
  };
  yield { type: "response.created", response: initialResponse };
  yield { type: "response.in_progress", response: initialResponse };
  let isToolCall = false;
  for await (const chunk of completion as AsyncIterable<OpenAI.ChatCompletionChunk>) {
    // console.error('\nCHUNK: ', JSON.stringify(chunk));
    const choice = chunk.choices?.[0];
    if (!choice) {
      continue;
    }
    if (
      !isToolCall &&
      (("tool_calls" in choice.delta && choice.delta.tool_calls) ||
        choice.finish_reason === "tool_calls")
    ) {
      isToolCall = true;
    }

    if (chunk.usage) {
      usage = {
        prompt_tokens: chunk.usage.prompt_tokens,
        completion_tokens: chunk.usage.completion_tokens,
        total_tokens: chunk.usage.total_tokens,
        input_tokens: chunk.usage.prompt_tokens,
        input_tokens_details: { cached_tokens: 0 },
        output_tokens: chunk.usage.completion_tokens,
        output_tokens_details: { reasoning_tokens: 0 },
      };
    }
    if (isToolCall) {
      for (const tcDelta of choice.delta.tool_calls || []) {
        const tcIndex = tcDelta.index;
        const content_index = textContentAdded ? tcIndex + 1 : tcIndex;

        if (!toolCalls.has(tcIndex)) {
          // New tool call
          const toolCallId = tcDelta.id || generateId("call");
          const functionName = tcDelta.function?.name || "";

          yield {
            type: "response.output_item.added",
            item: {
              type: "function_call",
              id: outputItemId,
              status: "in_progress",
              call_id: toolCallId,
              name: functionName,
              arguments: "",
            },
            output_index: 0,
          };
          toolCalls.set(tcIndex, {
            id: toolCallId,
            name: functionName,
            arguments: "",
          });
        }

        if (tcDelta.function?.arguments) {
          const current = toolCalls.get(tcIndex);
          if (current) {
            current.arguments += tcDelta.function.arguments;
            yield {
              type: "response.function_call_arguments.delta",
              item_id: outputItemId,
              output_index: 0,
              content_index,
              delta: tcDelta.function.arguments,
            };
          }
        }
      }

      if (choice.finish_reason === "tool_calls") {
        for (const [tcIndex, tc] of toolCalls) {
          const item = {
            type: "function_call",
            id: outputItemId,
            status: "completed",
            call_id: tc.id,
            name: tc.name,
            arguments: tc.arguments,
          };
          yield {
            type: "response.function_call_arguments.done",
            item_id: outputItemId,
            output_index: tcIndex,
            content_index: textContentAdded ? tcIndex + 1 : tcIndex,
            arguments: tc.arguments,
          };
          yield {
            type: "response.output_item.done",
            output_index: tcIndex,
            item,
          };
          finalOutputItem.push(item as unknown as ResponseContentOutput);
        }
      } else {
        continue;
      }
    } else {
      if (!textContentAdded) {
        yield {
          type: "response.content_part.added",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: "", annotations: [] },
        };
        textContentAdded = true;
      }
      if (choice.delta.content?.length) {
        yield {
          type: "response.output_text.delta",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          delta: choice.delta.content,
        };
        textContent += choice.delta.content;
      }
      if (choice.finish_reason) {
        yield {
          type: "response.output_text.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          text: textContent,
        };
        yield {
          type: "response.content_part.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: textContent, annotations: [] },
        };
        const item = {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: [
            { type: "output_text", text: textContent, annotations: [] },
          ],
        };
        yield {
          type: "response.output_item.done",
          output_index: 0,
          item,
        };
        finalOutputItem.push(item as unknown as ResponseContentOutput);
      } else {
        continue;
      }
    }

    // Construct final response
    const finalResponse: ResponseOutput = {
      id: responseId,
      object: "response" as const,
      created_at: initialResponse.created_at || Math.floor(Date.now() / 1000),
      status: "completed" as const,
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chunk.model || input.model,
      output: finalOutputItem as unknown as ResponseOutput["output"],
      parallel_tool_calls: true,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: usage as ResponseOutput["usage"],
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Store history
    const assistantMessage: OpenAI.Chat.Completions.ChatCompletionMessageParam =
      {
        role: "assistant" as const,
      };

    if (textContent) {
      assistantMessage.content = textContent;
    }

    // Add tool_calls property if needed
    if (toolCalls.size > 0) {
      const toolCallsArray = Array.from(toolCalls.values()).map((tc) => ({
        id: tc.id,
        type: "function" as const,
        function: { name: tc.name, arguments: tc.arguments },
      }));

      // Define a more specific type for the assistant message with tool calls
      type AssistantMessageWithToolCalls =
        OpenAI.Chat.Completions.ChatCompletionMessageParam & {
          tool_calls: Array<{
            id: string;
            type: "function";
            function: {
              name: string;
              arguments: string;
            };
          }>;
        };

      // Use type assertion with the defined type
      (assistantMessage as AssistantMessageWithToolCalls).tool_calls =
        toolCallsArray;
    }
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    yield { type: "response.completed", response: finalResponse };
  }
}

export {
  responsesCreateViaChatCompletions,
  ResponseCreateInput,
  ResponseOutput,
  ResponseEvent,
};

```

Thanks — I reproduced the type error and fixed it.

What I changed
- In `convertInputItemToMessage`, when we construct the Chat Completions message for multimodal user input, I now:
  - Explicitly set `role: "user"` to satisfy the discriminated union (so TypeScript no longer tries to match the assistant variant).
  - Cast the parts array to the exact type expected by the SDK: `OpenAI.Chat.Completions.ChatCompletionContentPart[]`.

This removes the “Type 'unknown' is not assignable …” error and avoids narrowing issues on the role union.

Edits
- `codex-cli/src/utils/responses.ts`:
  - If no images: return `{ role: "user", content: textChunks.join("") }`.
  - If images exist: return `{ role: "user", content: parts as OpenAI.Chat.Completions.ChatCompletionContentPart[] }`.

Status update
- Ran ESLint on the file—no errors.
- Ran `pnpm -C codex-cli typecheck`—clean.
- The full test suite was already green after the earlier feature changes.

Let me know if you also want me to add a short docs snippet about:
- attaching images via `-i` and inline markdown/file paths,
- the `CODEX_ATTACH_IMAGE=/abs/path.png` convention for auto-attach in loops,
- and a headless Godot screenshot example.

---

**User**

Try to commit and push to Github now.

---

**Cursor**

Running a quick git workflow: check status, create a feature branch, stage the changes, commit with a clear message, and push upstream. If push requires auth, I’ll report the failure details.

```typescript
import type { CommandConfirmation } from "./agent-loop.js";
import type { ApplyPatchCommand, ApprovalPolicy } from "../../approvals.js";
import type { ExecInput } from "./sandbox/interface.js";
import type { ResponseInputItem } from "openai/resources/responses/responses.mjs";

import { canAutoApprove } from "../../approvals.js";
import { formatCommandForDisplay } from "../../format-command.js";
import { FullAutoErrorMode } from "../auto-approval-mode.js";
import { CODEX_UNSAFE_ALLOW_NO_SANDBOX, type AppConfig } from "../config.js";
import { exec, execApplyPatch } from "./exec.js";
import { createInputItem } from "../input-utils.js";
import { ReviewDecision } from "./review.js";
import { isLoggingEnabled, log } from "../logger/log.js";
import { SandboxType } from "./sandbox/interface.js";
import { PATH_TO_SEATBELT_EXECUTABLE } from "./sandbox/macos-seatbelt.js";
import fs from "fs/promises";

// ---------------------------------------------------------------------------
// Session‑level cache of commands that the user has chosen to always approve.
//
// The values are derived via `deriveCommandKey()` which intentionally ignores
// volatile arguments (for example the patch text passed to `apply_patch`).
// Storing *generalised* keys means that once a user selects "always approve"
// for a given class of command we will genuinely stop prompting them for
// subsequent, equivalent invocations during the same CLI session.
// ---------------------------------------------------------------------------
const alwaysApprovedCommands = new Set<string>();

// ---------------------------------------------------------------------------
// Helper: Given the argv-style representation of a command, return a stable
// string key that can be used for equality checks.
//
// The key space purposefully abstracts away parts of the command line that
// are expected to change between invocations while still retaining enough
// information to differentiate *meaningfully distinct* operations.  See the
// extensive inline documentation for details.
// ---------------------------------------------------------------------------

function deriveCommandKey(cmd: Array<string>): string {
  // pull off only the bits you care about
  const [
    maybeShell,
    maybeFlag,
    coreInvocation,
    /* …ignore the rest… */
  ] = cmd;

  if (coreInvocation?.startsWith("apply_patch")) {
    return "apply_patch";
  }

  if (maybeShell === "bash" && maybeFlag === "-lc") {
    // If the command was invoked through `bash -lc "<script>"` we extract the
    // base program name from the script string.
    const script = coreInvocation ?? "";
    return script.split(/\s+/)[0] || "bash";
  }

  // For every other command we fall back to using only the program name (the
  // first argv element).  This guarantees we always return a *string* even if
  // `coreInvocation` is undefined.
  if (coreInvocation) {
    return coreInvocation.split(/\s+/)[0]!;
  }

  return JSON.stringify(cmd);
}

type HandleExecCommandResult = {
  outputText: string;
  metadata: Record<string, unknown>;
  additionalItems?: Array<ResponseInputItem>;
};

export async function handleExecCommand(
  args: ExecInput,
  config: AppConfig,
  policy: ApprovalPolicy,
  additionalWritableRoots: ReadonlyArray<string>,
  getCommandConfirmation: (
    command: Array<string>,
    applyPatch: ApplyPatchCommand | undefined,
  ) => Promise<CommandConfirmation>,
  abortSignal?: AbortSignal,
): Promise<HandleExecCommandResult> {
  const { cmd: command, workdir } = args;

  const key = deriveCommandKey(command);

  // 1) If the user has already said "always approve", skip
  //    any policy & never sandbox.
  if (alwaysApprovedCommands.has(key)) {
    return execCommand(
      args,
      /* applyPatch */ undefined,
      /* runInSandbox */ false,
      additionalWritableRoots,
      config,
      abortSignal,
    ).then(convertSummaryToResult);
  }

  // 2) Otherwise fall back to the normal policy
  // `canAutoApprove` now requires the list of writable roots that the command
  // is allowed to modify.  For the CLI we conservatively pass the current
  // working directory so that edits are constrained to the project root.  If
  // the caller wishes to broaden or restrict the set it can be made
  // configurable in the future.
  const safety = canAutoApprove(command, workdir, policy, [process.cwd()]);

  let runInSandbox: boolean;
  switch (safety.type) {
    case "ask-user": {
      const review = await askUserPermission(
        args,
        safety.applyPatch,
        getCommandConfirmation,
      );
      if (review != null) {
        return review;
      }

      runInSandbox = false;
      break;
    }
    case "auto-approve": {
      runInSandbox = safety.runInSandbox;
      break;
    }
    case "reject": {
      return {
        outputText: "aborted",
        metadata: {
          error: "command rejected",
          reason: "Command rejected by auto-approval system.",
        },
      };
    }
  }

  const { applyPatch } = safety;
  const summary = await execCommand(
    args,
    applyPatch,
    runInSandbox,
    additionalWritableRoots,
    config,
    abortSignal,
  );
  // If the operation was aborted in the meantime, propagate the cancellation
  // upward by returning an empty (no-op) result so that the agent loop will
  // exit cleanly without emitting spurious output.
  if (abortSignal?.aborted) {
    return {
      outputText: "",
      metadata: {},
    };
  }
  if (
    summary.exitCode !== 0 &&
    runInSandbox &&
    // Default: If the user has configured to ignore and continue,
    // skip re-running the command.
    //
    // Otherwise, if they selected "ask-user", then we should ask the user
    // for permission to re-run the command outside of the sandbox.
    config.fullAutoErrorMode &&
    config.fullAutoErrorMode === FullAutoErrorMode.ASK_USER
  ) {
    const review = await askUserPermission(
      args,
      safety.applyPatch,
      getCommandConfirmation,
    );
    if (review != null) {
      return review;
    } else {
      // The user has approved the command, so we will run it outside of the
      // sandbox.
      const summary = await execCommand(
        args,
        applyPatch,
        false,
        additionalWritableRoots,
        config,
        abortSignal,
      );
      return convertSummaryToResult(summary);
    }
  } else {
    return convertSummaryToResult(summary);
  }
}

async function convertSummaryToResult(
  summary: ExecCommandSummary,
): Promise<HandleExecCommandResult> {
  const { stdout, stderr, exitCode, durationMs } = summary;
  const outputText = stdout || stderr;

  const additionalItems: Array<ResponseInputItem> = [];
  // Convention: any line like `CODEX_ATTACH_IMAGE=/path/to/file.png` will be
  // converted into an attached image for the next turn.
  const attachments: Array<string> = [];
  const scan = (text: string) => {
    for (const line of text.split(/\r?\n/)) {
      const m = /^\s*CODEX_ATTACH_IMAGE\s*=\s*(.+\.(?:png|jpe?g|gif|bmp|webp|svg))\s*$/i.exec(
        line,
      );
      if (m && m[1]) {
        attachments.push(m[1]);
      }
    }
  };
  if (stdout) {
    scan(stdout);
  }
  if (stderr) {
    scan(stderr);
  }

  if (attachments.length > 0) {
    try {
      const msg = await createInputItem("", attachments);
      additionalItems.push(msg);
    } catch {
      // best effort – ignore attachment failures
    }
  }

  return {
    outputText,
    metadata: {
      exit_code: exitCode,
      duration_seconds: Math.round(durationMs / 100) / 10,
    },
    additionalItems: additionalItems.length > 0 ? additionalItems : undefined,
  };
}

type ExecCommandSummary = {
  stdout: string;
  stderr: string;
  exitCode: number;
  durationMs: number;
};

async function execCommand(
  execInput: ExecInput,
  applyPatchCommand: ApplyPatchCommand | undefined,
  runInSandbox: boolean,
  additionalWritableRoots: ReadonlyArray<string>,
  config: AppConfig,
  abortSignal?: AbortSignal,
): Promise<ExecCommandSummary> {
  let { workdir } = execInput;
  if (workdir) {
    try {
      await fs.access(workdir);
    } catch (e) {
      log(`EXEC workdir=${workdir} not found, use process.cwd() instead`);
      workdir = process.cwd();
    }
  }

  if (applyPatchCommand != null) {
    log("EXEC running apply_patch command");
  } else if (isLoggingEnabled()) {
    const { cmd, timeoutInMillis } = execInput;
    // Seconds are a bit easier to read in log messages and most timeouts
    // are specified as multiples of 1000, anyway.
    const timeout =
      timeoutInMillis != null
        ? Math.round(timeoutInMillis / 1000).toString()
        : "undefined";
    log(
      `EXEC running \`${formatCommandForDisplay(
        cmd,
      )}\` in workdir=${workdir} with timeout=${timeout}s`,
    );
  }

  // Note execApplyPatch() and exec() are coded defensively and should not
  // throw. Any internal errors should be mapped to a non-zero value for the
  // exitCode field.
  const start = Date.now();
  const execResult =
    applyPatchCommand != null
      ? execApplyPatch(applyPatchCommand.patch, workdir)
      : await exec(
          { ...execInput, additionalWritableRoots },
          await getSandbox(runInSandbox),
          config,
          abortSignal,
        );
  const duration = Date.now() - start;
  const { stdout, stderr, exitCode } = execResult;

  if (isLoggingEnabled()) {
    log(
      `EXEC exit=${exitCode} time=${duration}ms:\n\tSTDOUT: ${stdout}\n\tSTDERR: ${stderr}`,
    );
  }

  return {
    stdout,
    stderr,
    exitCode,
    durationMs: duration,
  };
}

/** Return `true` if the `/usr/bin/sandbox-exec` is present and executable. */
const isSandboxExecAvailable: Promise<boolean> = fs
  .access(PATH_TO_SEATBELT_EXECUTABLE, fs.constants.X_OK)
  .then(
    () => true,
    (err) => {
      if (!["ENOENT", "ACCESS", "EPERM"].includes(err.code)) {
        log(
          `Unexpected error for \`stat ${PATH_TO_SEATBELT_EXECUTABLE}\`: ${err.message}`,
        );
      }
      return false;
    },
  );

async function getSandbox(runInSandbox: boolean): Promise<SandboxType> {
  if (runInSandbox) {
    if (process.platform === "darwin") {
      // On macOS we rely on the system-provided `sandbox-exec` binary to
      // enforce the Seatbelt profile.  However, starting with macOS 14 the
      // executable may be removed from the default installation or the user
      // might be running the CLI on a stripped-down environment (for
      // instance, inside certain CI images).  Attempting to spawn a missing
      // binary makes Node.js throw an *uncaught* `ENOENT` error further down
      // the stack which crashes the whole CLI.
      if (await isSandboxExecAvailable) {
        return SandboxType.MACOS_SEATBELT;
      } else {
        throw new Error(
          "Sandbox was mandated, but 'sandbox-exec' was not found in PATH!",
        );
      }
    } else if (process.platform === "linux") {
      // TODO: Need to verify that the Landlock sandbox is working. For example,
      // using Landlock in a Linux Docker container from a macOS host may not
      // work.
      return SandboxType.LINUX_LANDLOCK;
    } else if (CODEX_UNSAFE_ALLOW_NO_SANDBOX) {
      // Allow running without a sandbox if the user has explicitly marked the
      // environment as already being sufficiently locked-down.
      return SandboxType.NONE;
    }

    // For all else, we hard fail if the user has requested a sandbox and none is available.
    throw new Error("Sandbox was mandated, but no sandbox is available!");
  } else {
    return SandboxType.NONE;
  }
}

/**
 * If return value is non-null, then the command was rejected by the user.
 */
async function askUserPermission(
  args: ExecInput,
  applyPatchCommand: ApplyPatchCommand | undefined,
  getCommandConfirmation: (
    command: Array<string>,
    applyPatch: ApplyPatchCommand | undefined,
  ) => Promise<CommandConfirmation>,
): Promise<HandleExecCommandResult | null> {
  const { review: decision, customDenyMessage } = await getCommandConfirmation(
    args.cmd,
    applyPatchCommand,
  );

  if (decision === ReviewDecision.ALWAYS) {
    // Persist this command so we won't ask again during this session.
    const key = deriveCommandKey(args.cmd);
    alwaysApprovedCommands.add(key);
  }

  // Handle EXPLAIN decision by returning null to continue with the normal flow
  // but with a flag to indicate that an explanation was requested
  if (decision === ReviewDecision.EXPLAIN) {
    return null;
  }

  // Any decision other than an affirmative (YES / ALWAYS) or EXPLAIN aborts execution.
  if (decision !== ReviewDecision.YES && decision !== ReviewDecision.ALWAYS) {
    const note =
      decision === ReviewDecision.NO_CONTINUE
        ? customDenyMessage?.trim() || "No, don't do that — keep going though."
        : "No, don't do that — stop for now.";
    return {
      outputText: "aborted",
      metadata: {},
      additionalItems: [
        {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: note }],
        },
      ],
    };
  } else {
    return null;
  }
}

```

```typescript
import type { OpenAI } from "openai";
import type {
  ResponseCreateParams,
  Response,
} from "openai/resources/responses/responses";

// Define interfaces based on OpenAI API documentation
type ResponseCreateInput = ResponseCreateParams;
type ResponseOutput = Response;
// interface ResponseOutput {
//   id: string;
//   object: 'response';
//   created_at: number;
//   status: 'completed' | 'failed' | 'in_progress' | 'incomplete';
//   error: { code: string; message: string } | null;
//   incomplete_details: { reason: string } | null;
//   instructions: string | null;
//   max_output_tokens: number | null;
//   model: string;
//   output: Array<{
//     type: 'message';
//     id: string;
//     status: 'completed' | 'in_progress';
//     role: 'assistant';
//     content: Array<{
//       type: 'output_text' | 'function_call';
//       text?: string;
//       annotations?: Array<any>;
//       tool_call?: {
//         id: string;
//         type: 'function';
//         function: { name: string; arguments: string };
//       };
//     }>;
//   }>;
//   parallel_tool_calls: boolean;
//   previous_response_id: string | null;
//   reasoning: { effort: string | null; summary: string | null };
//   store: boolean;
//   temperature: number;
//   text: { format: { type: 'text' } };
//   tool_choice: string | object;
//   tools: Array<any>;
//   top_p: number;
//   truncation: string;
//   usage: {
//     input_tokens: number;
//     input_tokens_details: { cached_tokens: number };
//     output_tokens: number;
//     output_tokens_details: { reasoning_tokens: number };
//     total_tokens: number;
//   } | null;
//   user: string | null;
//   metadata: Record<string, string>;
// }

// Define types for the ResponseItem content and parts
type ResponseContentPart = {
  type: string;
  [key: string]: unknown;
};

type ResponseItemType = {
  type: string;
  id?: string;
  status?: string;
  role?: string;
  content?: Array<ResponseContentPart>;
  [key: string]: unknown;
};

type ResponseEvent =
  | { type: "response.created"; response: Partial<ResponseOutput> }
  | { type: "response.in_progress"; response: Partial<ResponseOutput> }
  | {
      type: "response.output_item.added";
      output_index: number;
      item: ResponseItemType;
    }
  | {
      type: "response.content_part.added";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_text.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.output_text.done";
      item_id: string;
      output_index: number;
      content_index: number;
      text: string;
    }
  | {
      type: "response.function_call_arguments.delta";
      item_id: string;
      output_index: number;
      content_index: number;
      delta: string;
    }
  | {
      type: "response.function_call_arguments.done";
      item_id: string;
      output_index: number;
      content_index: number;
      arguments: string;
    }
  | {
      type: "response.content_part.done";
      item_id: string;
      output_index: number;
      content_index: number;
      part: ResponseContentPart;
    }
  | {
      type: "response.output_item.done";
      output_index: number;
      item: ResponseItemType;
    }
  | { type: "response.completed"; response: ResponseOutput }
  | { type: "error"; code: string; message: string; param: string | null };

// Define a type for tool call data
type ToolCallData = {
  id: string;
  name: string;
  arguments: string;
};

// Define a type for usage data
type UsageData = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  input_tokens?: number;
  input_tokens_details?: { cached_tokens: number };
  output_tokens?: number;
  output_tokens_details?: { reasoning_tokens: number };
  [key: string]: unknown;
};

// Define a type for content output
type ResponseContentOutput =
  | {
      type: "function_call";
      call_id: string;
      name: string;
      arguments: string;
      [key: string]: unknown;
    }
  | {
      type: "output_text";
      text: string;
      annotations: Array<unknown>;
      [key: string]: unknown;
    };

// Global map to store conversation histories
const conversationHistories = new Map<
  string,
  {
    previous_response_id: string | null;
    messages: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam>;
  }
>();

// Utility function to generate unique IDs
function generateId(prefix: string = "msg"): string {
  return `${prefix}_${Math.random().toString(36).substr(2, 9)}`;
}

// Function to convert ResponseInputItem to ChatCompletionMessageParam
type ResponseInputItem = ResponseCreateInput["input"][number];

function convertInputItemToMessage(
  item: string | ResponseInputItem,
): OpenAI.Chat.Completions.ChatCompletionMessageParam {
  // Handle string inputs as content for a user message
  if (typeof item === "string") {
    return { role: "user", content: item };
  }

  // At this point we know it's a ResponseInputItem
  const responseItem = item;

  if (responseItem.type === "message") {
    // Map Responses-style content parts to Chat Completions content parts,
    // preserving both text and images for providers that only support the
    // chat.completions endpoint.
    const parts: Array<
      | OpenAI.Chat.Completions.ChatCompletionContentPartText
      | OpenAI.Chat.Completions.ChatCompletionContentPartImage
    > = [];
    let hasImage = false;
    const textChunks: Array<string> = [];

    if (Array.isArray(responseItem.content)) {
      for (const c of responseItem.content) {
        if (typeof c !== "object" || !c) {
          continue;
        }
        // input_text -> { type: 'text', text }
        if ((c as { type?: string }).type === "input_text") {
          const text = (c as { text?: string }).text ?? "";
          parts.push({ type: "text", text });
          textChunks.push(text);
          continue;
        }
        // input_image -> { type: 'image_url', image_url }
        if ((c as { type?: string }).type === "input_image") {
          // Responses API uses `image_url` (string data URL or remote URL) and optional `detail`.
          // Chat Completions expects { type: 'image_url', image_url: string | { url, detail } }.
          const img = c as { image_url?: unknown; detail?: unknown };
          const url =
            typeof img.image_url === "string"
              ? img.image_url
              : // Some SDKs may represent as { url: string }
                (img.image_url &&
                  typeof img.image_url === "object" &&
                  (img.image_url as { url?: string }).url) ||
                "";
          const detail =
            typeof img.detail === "string" ? (img.detail as "low" | "high" | "auto") : undefined;

          // Prefer object form when detail is present; otherwise pass the URL directly.
          const image_url: unknown = detail ? { url, detail } : url;
          // Cast to the SDK type – at runtime OpenAI accepts both forms.
          parts.push({ type: "image_url", image_url } as unknown as OpenAI.Chat.Completions.ChatCompletionContentPartImage);
          hasImage = true;
        }
      }
    }

    // Preserve legacy behavior: if there are no images, send plain string content
    // so providers/tests that expect a string continue to work. Otherwise pass
    // the structured content parts array.
    if (!hasImage) {
      return { role: "user", content: textChunks.join("") };
    }
    return {
      role: "user",
      content:
        (parts as unknown) as Array<OpenAI.Chat.Completions.ChatCompletionContentPart>,
    };
  } else if (responseItem.type === "function_call_output") {
    return {
      role: "tool",
      tool_call_id: responseItem.call_id,
      content: responseItem.output,
    };
  }
  throw new Error(`Unsupported input item type: ${responseItem.type}`);
}

// Function to get full messages including history
function getFullMessages(
  input: ResponseCreateInput,
): Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> {
  let baseHistory: Array<OpenAI.Chat.Completions.ChatCompletionMessageParam> =
    [];
  if (input.previous_response_id) {
    const prev = conversationHistories.get(input.previous_response_id);
    if (!prev) {
      throw new Error(
        `Previous response not found: ${input.previous_response_id}`,
      );
    }
    baseHistory = prev.messages;
  }

  // Handle both string and ResponseInputItem in input.input
  const newInputMessages = Array.isArray(input.input)
    ? input.input.map(convertInputItemToMessage)
    : [convertInputItemToMessage(input.input)];

  const messages = [...baseHistory, ...newInputMessages];
  if (
    input.instructions &&
    messages[0]?.role !== "system" &&
    messages[0]?.role !== "developer"
  ) {
    return [{ role: "system", content: input.instructions }, ...messages];
  }
  return messages;
}

// Function to convert tools
function convertTools(
  tools?: ResponseCreateInput["tools"],
): Array<OpenAI.Chat.Completions.ChatCompletionTool> | undefined {
  return tools
    ?.filter((tool) => tool.type === "function")
    .map((tool) => ({
      type: "function" as const,
      function: {
        name: tool.name,
        description: tool.description || undefined,
        parameters: tool.parameters,
      },
    }));
}

const createCompletion = (openai: OpenAI, input: ResponseCreateInput) => {
  const fullMessages = getFullMessages(input);
  const chatTools = convertTools(input.tools);
  const webSearchOptions = input.tools?.some(
    (tool) => tool.type === "function" && tool.name === "web_search",
  )
    ? {}
    : undefined;

  const chatInput: OpenAI.Chat.Completions.ChatCompletionCreateParams = {
    model: input.model,
    messages: fullMessages,
    tools: chatTools,
    web_search_options: webSearchOptions,
    temperature: input.temperature,
    top_p: input.top_p,
    tool_choice: (input.tool_choice === "auto"
      ? "auto"
      : input.tool_choice) as OpenAI.Chat.Completions.ChatCompletionCreateParams["tool_choice"],
    stream: input.stream || false,
    user: input.user,
    metadata: input.metadata,
  };

  return openai.chat.completions.create(chatInput);
};

// Main function with overloading
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream: true },
): Promise<AsyncGenerator<ResponseEvent>>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput & { stream?: false },
): Promise<ResponseOutput>;
async function responsesCreateViaChatCompletions(
  openai: OpenAI,
  input: ResponseCreateInput,
): Promise<ResponseOutput | AsyncGenerator<ResponseEvent>> {
  const completion = await createCompletion(openai, input);
  if (input.stream) {
    return streamResponses(
      input,
      completion as AsyncIterable<OpenAI.ChatCompletionChunk>,
    );
  } else {
    return nonStreamResponses(
      input,
      completion as unknown as OpenAI.Chat.Completions.ChatCompletion,
    );
  }
}

// Non-streaming implementation
async function nonStreamResponses(
  input: ResponseCreateInput,
  completion: OpenAI.Chat.Completions.ChatCompletion,
): Promise<ResponseOutput> {
  const fullMessages = getFullMessages(input);

  try {
    const chatResponse = completion;
    if (!("choices" in chatResponse) || chatResponse.choices.length === 0) {
      throw new Error("No choices in chat completion response");
    }
    const assistantMessage = chatResponse.choices?.[0]?.message;
    if (!assistantMessage) {
      throw new Error("No assistant message in chat completion response");
    }

    // Construct ResponseOutput
    const responseId = generateId("resp");
    const outputItemId = generateId("msg");
    const outputContent: Array<ResponseContentOutput> = [];

    // Check if the response contains tool calls
    const hasFunctionCalls =
      assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0;

    if (hasFunctionCalls && assistantMessage.tool_calls) {
      for (const toolCall of assistantMessage.tool_calls) {
        if (toolCall.type === "function") {
          outputContent.push({
            type: "function_call",
            call_id: toolCall.id,
            name: toolCall.function.name,
            arguments: toolCall.function.arguments,
          });
        }
      }
    }

    if (assistantMessage.content) {
      outputContent.push({
        type: "output_text",
        text: assistantMessage.content,
        annotations: [],
      });
    }

    // Create response with appropriate status and properties
    const responseOutput = {
      id: responseId,
      object: "response",
      created_at: Math.floor(Date.now() / 1000),
      status: hasFunctionCalls ? "requires_action" : "completed",
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chatResponse.model,
      output: [
        {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: outputContent,
        },
      ],
      parallel_tool_calls: input.parallel_tool_calls ?? false,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: chatResponse.usage
        ? {
            input_tokens: chatResponse.usage.prompt_tokens,
            input_tokens_details: { cached_tokens: 0 },
            output_tokens: chatResponse.usage.completion_tokens,
            output_tokens_details: { reasoning_tokens: 0 },
            total_tokens: chatResponse.usage.total_tokens,
          }
        : undefined,
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Add required_action property for tool calls
    if (hasFunctionCalls && assistantMessage.tool_calls) {
      // Define type with required action
      type ResponseWithAction = Partial<ResponseOutput> & {
        required_action: unknown;
      };

      // Use the defined type for the assertion
      (responseOutput as ResponseWithAction).required_action = {
        type: "submit_tool_outputs",
        submit_tool_outputs: {
          tool_calls: assistantMessage.tool_calls.map((toolCall) => ({
            id: toolCall.id,
            type: toolCall.type,
            function: {
              name: toolCall.function.name,
              arguments: toolCall.function.arguments,
            },
          })),
        },
      };
    }

    // Store history
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    return responseOutput;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to process chat completion: ${errorMessage}`);
  }
}

// Streaming implementation
async function* streamResponses(
  input: ResponseCreateInput,
  completion: AsyncIterable<OpenAI.ChatCompletionChunk>,
): AsyncGenerator<ResponseEvent> {
  const fullMessages = getFullMessages(input);

  const responseId = generateId("resp");
  const outputItemId = generateId("msg");
  let textContentAdded = false;
  let textContent = "";
  const toolCalls = new Map<number, ToolCallData>();
  let usage: UsageData | null = null;
  const finalOutputItem: Array<ResponseContentOutput> = [];
  // Initial response
  const initialResponse: Partial<ResponseOutput> = {
    id: responseId,
    object: "response" as const,
    created_at: Math.floor(Date.now() / 1000),
    status: "in_progress" as const,
    model: input.model,
    output: [],
    error: null,
    incomplete_details: null,
    instructions: null,
    max_output_tokens: null,
    parallel_tool_calls: true,
    previous_response_id: input.previous_response_id ?? null,
    reasoning: null,
    temperature: input.temperature,
    text: { format: { type: "text" } },
    tool_choice: input.tool_choice ?? "auto",
    tools: input.tools ?? [],
    top_p: input.top_p,
    truncation: input.truncation ?? "disabled",
    usage: undefined,
    user: input.user ?? undefined,
    metadata: input.metadata ?? {},
    output_text: "",
  };
  yield { type: "response.created", response: initialResponse };
  yield { type: "response.in_progress", response: initialResponse };
  let isToolCall = false;
  for await (const chunk of completion as AsyncIterable<OpenAI.ChatCompletionChunk>) {
    // console.error('\nCHUNK: ', JSON.stringify(chunk));
    const choice = chunk.choices?.[0];
    if (!choice) {
      continue;
    }
    if (
      !isToolCall &&
      (("tool_calls" in choice.delta && choice.delta.tool_calls) ||
        choice.finish_reason === "tool_calls")
    ) {
      isToolCall = true;
    }

    if (chunk.usage) {
      usage = {
        prompt_tokens: chunk.usage.prompt_tokens,
        completion_tokens: chunk.usage.completion_tokens,
        total_tokens: chunk.usage.total_tokens,
        input_tokens: chunk.usage.prompt_tokens,
        input_tokens_details: { cached_tokens: 0 },
        output_tokens: chunk.usage.completion_tokens,
        output_tokens_details: { reasoning_tokens: 0 },
      };
    }
    if (isToolCall) {
      for (const tcDelta of choice.delta.tool_calls || []) {
        const tcIndex = tcDelta.index;
        const content_index = textContentAdded ? tcIndex + 1 : tcIndex;

        if (!toolCalls.has(tcIndex)) {
          // New tool call
          const toolCallId = tcDelta.id || generateId("call");
          const functionName = tcDelta.function?.name || "";

          yield {
            type: "response.output_item.added",
            item: {
              type: "function_call",
              id: outputItemId,
              status: "in_progress",
              call_id: toolCallId,
              name: functionName,
              arguments: "",
            },
            output_index: 0,
          };
          toolCalls.set(tcIndex, {
            id: toolCallId,
            name: functionName,
            arguments: "",
          });
        }

        if (tcDelta.function?.arguments) {
          const current = toolCalls.get(tcIndex);
          if (current) {
            current.arguments += tcDelta.function.arguments;
            yield {
              type: "response.function_call_arguments.delta",
              item_id: outputItemId,
              output_index: 0,
              content_index,
              delta: tcDelta.function.arguments,
            };
          }
        }
      }

      if (choice.finish_reason === "tool_calls") {
        for (const [tcIndex, tc] of toolCalls) {
          const item = {
            type: "function_call",
            id: outputItemId,
            status: "completed",
            call_id: tc.id,
            name: tc.name,
            arguments: tc.arguments,
          };
          yield {
            type: "response.function_call_arguments.done",
            item_id: outputItemId,
            output_index: tcIndex,
            content_index: textContentAdded ? tcIndex + 1 : tcIndex,
            arguments: tc.arguments,
          };
          yield {
            type: "response.output_item.done",
            output_index: tcIndex,
            item,
          };
          finalOutputItem.push(item as unknown as ResponseContentOutput);
        }
      } else {
        continue;
      }
    } else {
      if (!textContentAdded) {
        yield {
          type: "response.content_part.added",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: "", annotations: [] },
        };
        textContentAdded = true;
      }
      if (choice.delta.content?.length) {
        yield {
          type: "response.output_text.delta",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          delta: choice.delta.content,
        };
        textContent += choice.delta.content;
      }
      if (choice.finish_reason) {
        yield {
          type: "response.output_text.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          text: textContent,
        };
        yield {
          type: "response.content_part.done",
          item_id: outputItemId,
          output_index: 0,
          content_index: 0,
          part: { type: "output_text", text: textContent, annotations: [] },
        };
        const item = {
          type: "message",
          id: outputItemId,
          status: "completed",
          role: "assistant",
          content: [
            { type: "output_text", text: textContent, annotations: [] },
          ],
        };
        yield {
          type: "response.output_item.done",
          output_index: 0,
          item,
        };
        finalOutputItem.push(item as unknown as ResponseContentOutput);
      } else {
        continue;
      }
    }

    // Construct final response
    const finalResponse: ResponseOutput = {
      id: responseId,
      object: "response" as const,
      created_at: initialResponse.created_at || Math.floor(Date.now() / 1000),
      status: "completed" as const,
      error: null,
      incomplete_details: null,
      instructions: null,
      max_output_tokens: null,
      model: chunk.model || input.model,
      output: finalOutputItem as unknown as ResponseOutput["output"],
      parallel_tool_calls: true,
      previous_response_id: input.previous_response_id ?? null,
      reasoning: null,
      temperature: input.temperature,
      text: { format: { type: "text" } },
      tool_choice: input.tool_choice ?? "auto",
      tools: input.tools ?? [],
      top_p: input.top_p,
      truncation: input.truncation ?? "disabled",
      usage: usage as ResponseOutput["usage"],
      user: input.user ?? undefined,
      metadata: input.metadata ?? {},
      output_text: "",
    } as ResponseOutput;

    // Store history
    const assistantMessage: OpenAI.Chat.Completions.ChatCompletionMessageParam =
      {
        role: "assistant" as const,
      };

    if (textContent) {
      assistantMessage.content = textContent;
    }

    // Add tool_calls property if needed
    if (toolCalls.size > 0) {
      const toolCallsArray = Array.from(toolCalls.values()).map((tc) => ({
        id: tc.id,
        type: "function" as const,
        function: { name: tc.name, arguments: tc.arguments },
      }));

      // Define a more specific type for the assistant message with tool calls
      type AssistantMessageWithToolCalls =
        OpenAI.Chat.Completions.ChatCompletionMessageParam & {
          tool_calls: Array<{
            id: string;
            type: "function";
            function: {
              name: string;
              arguments: string;
            };
          }>;
        };

      // Use type assertion with the defined type
      (assistantMessage as AssistantMessageWithToolCalls).tool_calls =
        toolCallsArray;
    }
    const newHistory = [...fullMessages, assistantMessage];
    conversationHistories.set(responseId, {
      previous_response_id: input.previous_response_id ?? null,
      messages: newHistory,
    });

    yield { type: "response.completed", response: finalResponse };
  }
}

export {
  responsesCreateViaChatCompletions,
  ResponseCreateInput,
  ResponseOutput,
  ResponseEvent,
};

```

### Done: committed and pushed
- Created and pushed branch: add-multimodal-input
- Commit includes:
  - Forwarding `input_image` content to Chat Completions fallback.
  - Auto-attach convention for images from shell output via CODEX_ATTACH_IMAGE=/abs/path.png.
- Pre-commit hooks ran lint and typecheck; I fixed the issues, re-staged, and the commit succeeded.
- CI-like local checks:
  - pnpm test (CLI package) passed: 72/72 files, 247 tests passed, 2 skipped.
  - Typecheck clean.

### Status update
I hit a pre-commit lint failure due to curly and array-type style rules on staged content. I updated the code to satisfy the rules, re-staged, committed, and pushed successfully.

If you want, I can open a PR with a brief summary and usage notes for the new auto-attach pattern and multimodal fallback behavior.

