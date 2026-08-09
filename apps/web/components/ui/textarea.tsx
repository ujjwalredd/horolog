"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

const textareaVariants = cva(
  "flex min-h-[60px] w-full rounded-xl border border-border bg-input px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-vertical transition-colors scrollbar-thin scrollbar-track-transparent scrollbar-thumb-border hover:scrollbar-thumb-muted-foreground scrollbar-corner-transparent shadow-sm",
  {
    variants: {
      variant: {
        default: "border-border",
        destructive:
          "border-destructive focus-visible:ring-destructive",
        ghost:
          "border-transparent bg-accent focus-visible:bg-input focus-visible:border-border",
      },
      size: {
        default: "min-h-[80px] px-3 py-2",
        sm: "min-h-[60px] px-3 py-2 text-xs",
        lg: "min-h-[100px] px-4 py-2",
        xl: "min-h-[120px] px-6 py-3 text-base",
        fixed: "h-[80px] px-3 py-2 resize-none",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface TextareaProps
  extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "size">,
    VariantProps<typeof textareaVariants> {
  error?: boolean;
  clearable?: boolean;
  onClear?: () => void;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    { className, variant, size, error, clearable, onClear, value, ...props },
    ref
  ) => {
    const [internalValue, setInternalValue] = React.useState(
      props.defaultValue || ""
    );
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);

    React.useImperativeHandle(ref, () => textareaRef.current!);

    const textareaVariant = error ? "destructive" : variant;

    const isControlled = value !== undefined;
    const textareaValue = isControlled ? value : internalValue;
    const showClearButton =
      clearable && textareaValue && String(textareaValue).length > 0;

    const handleTextareaChange = (
      e: React.ChangeEvent<HTMLTextAreaElement>
    ) => {
      if (!isControlled) {
        setInternalValue(e.target.value);
      }
      props.onChange?.(e);
    };

    const handleClear = () => {
      if (!isControlled) {
        setInternalValue("");
      }

      onClear?.();

      if (textareaRef.current) {
        const textarea = textareaRef.current;
        textarea.value = "";
        const syntheticEvent = {
          target: textarea,
          currentTarget: textarea,
          nativeEvent: new Event("input", { bubbles: true }),
          isDefaultPrevented: () => false,
          isPropagationStopped: () => false,
          persist: () => {},
          preventDefault: () => {},
          stopPropagation: () => {},
          bubbles: true,
          cancelable: true,
          defaultPrevented: false,
          eventPhase: 0,
          isTrusted: true,
          timeStamp: Date.now(),
          type: "change",
        } as React.ChangeEvent<HTMLTextAreaElement>;

        props.onChange?.(syntheticEvent);
        textarea.focus();
      }
    };

    return (
      <div className="relative w-full">
        <textarea
          className={cn(
            textareaVariants({ variant: textareaVariant, size, className }),
            showClearButton && "pr-10"
          )}
          ref={textareaRef}
          {...(isControlled
            ? { value: textareaValue }
            : { defaultValue: props.defaultValue })}
          onChange={handleTextareaChange}
          {...(({ defaultValue, ...rest }) => rest)(props)}
        />
        {showClearButton && (
          <div className="absolute right-3 top-3 flex items-center gap-1 z-10">
            <button
              type="button"
              onClick={handleClear}
              className="text-muted-foreground hover:text-foreground transition-colors [&_svg]:size-4 [&_svg]:shrink-0"
              tabIndex={-1}
            >
              <X />
            </button>
          </div>
        )}
      </div>
    );
  }
);

Textarea.displayName = "Textarea";

export { Textarea, textareaVariants };
