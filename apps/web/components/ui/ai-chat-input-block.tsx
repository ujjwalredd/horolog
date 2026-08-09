"use client";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Toggle } from "@/components/ui/toggle";
import { Input } from "@/components/ui/input";

import { useState } from "react";
import { Globe, Lightbulb, Mic, Paperclip, Send, Key } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

interface AIChatInputProps {
  onSubmit: (data: { input: string; provider: string; model: string; apiKey?: string }) => void;
  busy?: boolean;
}

const BasicAIChatInput = ({ onSubmit, busy = false }: AIChatInputProps) => {
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState("default");
  const [apiKey, setApiKey] = useState("");

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleProviderChange = (value: string) => {
    setProvider(value);
  };

  const handleSubmit = () => {
    if (!input.trim() || busy) return;
    
    // Choose model names according to selection
    let model = "default";
    if (provider === "openai") {
      model = "gpt-4o";
    } else if (provider === "anthropic") {
      model = "claude-3-5-sonnet-latest";
    }

    onSubmit({
      input: input.trim(),
      provider,
      model,
      apiKey: (provider === "openai" || provider === "anthropic") ? apiKey.trim() : undefined,
    });
    setInput(""); // Clear input after submission
  };

  return (
    <div className="flex items-center flex-col gap-3 max-w-2xl w-full">
      <div className="flex items-center justify-between w-full max-sm:flex-col max-sm:gap-2">
        <span className="text-[12px] font-medium text-fg-muted">AI Scheduling Assistant</span>
        <Select onValueChange={handleProviderChange} value={provider}>
          <SelectTrigger className="w-48 font-medium h-9 text-xs" variant={"ghost"}>
            <SelectValue placeholder="Select LLM Engine" />
          </SelectTrigger>
          <SelectContent className="text-sm">
            <SelectItem value="default">Default configured model</SelectItem>
            <SelectItem value="openai">OpenAI (GPT-4o)</SelectItem>
            <SelectItem value="anthropic">Anthropic (Claude 3.5)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {(provider === "openai" || provider === "anthropic") && (
        <div className="w-full flex items-center gap-2">
          <Input
            type="password"
            placeholder={`Enter custom ${provider === "openai" ? "OpenAI" : "Anthropic"} API Key...`}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="h-9 text-xs"
            leftIcon={<Key size={14} className="text-muted-foreground" />}
          />
        </div>
      )}

      <Card className="w-full rounded-2xl border border-border bg-card shadow-sm">
        <CardContent className="p-4 space-y-3">
          <div className="w-full">
            <Textarea
              placeholder="e.g. 'Write the design doc, 3 hours by Friday' or 'Gym three times a week for an hour'..."
              value={input}
              onChange={handleInputChange}
              disabled={busy}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              className="flex-grow border-none ring-0 outline-none shadow-none focus:border-none focus:ring-0 focus:outline-none focus:shadow-none hover:border-none hover:ring-0 hover:outline-none hover:shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 resize-none bg-transparent min-h-[70px] text-[14px]"
            />
          </div>

          <div className="w-full flex items-center justify-between gap-2">
            <div className="flex items-center gap-1">
              <Button variant={"ghost"} size={"icon"} className="h-8 w-8 rounded-md">
                <Paperclip size={15} />
              </Button>
              <Toggle className="h-8 w-8 rounded-md p-0 flex items-center justify-center">
                <Lightbulb size={15} className="shrink-0"/>
              </Toggle>
              <Toggle variant="default" className="h-8 font-normal flex gap-1.5 items-center text-xs px-2.5 rounded-md">
                <Globe size={14} className="shrink-0" /> <span className="max-sm:hidden">Web Search</span>
              </Toggle>
            </div>
            <div className="flex items-center gap-1.5">
              <Toggle variant="outline" className="h-8 w-8 rounded-md p-0 flex items-center justify-center" aria-label="Voice capture">
                <Mic size={14} className="shrink-0"/>
              </Toggle>

              <Button onClick={handleSubmit} size={"icon"} className="h-8 w-8 rounded-md" disabled={busy || !input.trim()}>
                <Send size={14} />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default BasicAIChatInput;
