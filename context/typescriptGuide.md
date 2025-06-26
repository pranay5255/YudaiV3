# TypeScript Syntax & Type System Guide for YudaiV3

## **1. TypeScript Configuration**

### **tsconfig.json Settings**
```json
{
  "compilerOptions": {
    "target": "ESNext",           // Latest ECMAScript features
    "lib": ["dom", "dom.iterable", "esnext"], // Available APIs
    "strict": true,               // Enable all strict type checking
    "jsx": "preserve",           // Keep JSX for Next.js
    "paths": {
      "@/*": ["./*"]             // Path aliases for imports
    }
  }
}
```

## **2. Import/Export Type Syntax**

### **Type-Only Imports**
```typescript
// Import only types (not runtime values)
import type { Message } from "ai";
import type { Components } from "react-markdown";
import type { RefObject } from "react";
import type { ChatRequestOptions, CreateMessage } from "ai";

// Mixed imports (values + types)
import { useEffect, useRef, type RefObject } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { clsx, type ClassValue } from "clsx";
```

### **Type Exports**
```typescript
// Export interfaces
export interface ButtonProps {
  variant?: "default" | "destructive" | "outline";
  size?: "default" | "sm" | "lg" | "icon";
  asChild?: boolean;
}

// Export type aliases
export type ButtonVariant = "default" | "destructive" | "outline";
export type ButtonSize = "default" | "sm" | "lg" | "icon";
```

## **3. React Component Type Patterns**

### **Functional Component Props**
```typescript
// Inline prop types
const MyComponent = ({ prop1, prop2 }: { prop1: string; prop2: number }) => {
  return <div>{prop1}: {prop2}</div>;
};

// Interface-based props
interface MyComponentProps {
  prop1: string;
  prop2: number;
  optionalProp?: boolean;
}

const MyComponent = ({ prop1, prop2, optionalProp }: MyComponentProps) => {
  return <div>{prop1}: {prop2}</div>;
};

// Props with children
interface PropsWithChildren {
  children: React.ReactNode;
  title: string;
}

const ComponentWithChildren = ({ children, title }: PropsWithChildren) => {
  return (
    <div>
      <h1>{title}</h1>
      {children}
    </div>
  );
};
```

### **Extending HTML Element Props**
```typescript
// Extend native HTML button attributes
export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline";
  size?: "default" | "sm" | "lg" | "icon";
  asChild?: boolean;
}

// Extend textarea props
const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<"textarea">
>(({ className, ...props }, ref) => {
  return <textarea ref={ref} {...props} />;
});
```

## **4. Generic Types**

### **Generic Functions**
```typescript
// Generic hook with constraints
export function useScrollToBottom<T extends HTMLElement>(): [
  RefObject<T>,
  RefObject<T>,
] {
  const containerRef = useRef<T>(null);
  const endRef = useRef<T>(null);
  return [containerRef, endRef];
}

// Usage
const [messagesContainerRef, messagesEndRef] = useScrollToBottom<HTMLDivElement>();
```

### **Generic Components**
```typescript
// Generic component with type constraints
interface GenericProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
}

const GenericList = <T,>({ items, renderItem }: GenericProps<T>) => {
  return (
    <div>
      {items.map((item, index) => renderItem(item, index))}
    </div>
  );
};
```

## **5. React Hook Types**

### **useState with Types**
```typescript
// Explicit typing
const [messages, setMessages] = useState<Message[]>([]);
const [input, setInput] = useState<string>("");
const [isLoading, setIsLoading] = useState<boolean>(false);

// Union types
const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

// Complex object types
interface User {
  id: string;
  name: string;
  email: string;
}

const [user, setUser] = useState<User | null>(null);
```

### **useRef with Types**
```typescript
// HTML element refs
const textareaRef = useRef<HTMLTextAreaElement>(null);
const buttonRef = useRef<HTMLButtonElement>(null);
const divRef = useRef<HTMLDivElement>(null);

// Custom component refs
const customRef = useRef<CustomComponent>(null);

// Mutable values
const timeoutRef = useRef<NodeJS.Timeout | null>(null);
const countRef = useRef<number>(0);
```

### **useCallback with Types**
```typescript
// Function with explicit parameter types
const handleSubmit = useCallback((
  event?: { preventDefault?: () => void },
  options?: ChatRequestOptions
) => {
  event?.preventDefault();
  // Implementation
}, [dependencies]);

// Event handlers
const handleInput = useCallback((event: React.ChangeEvent<HTMLTextAreaElement>) => {
  setInput(event.target.value);
}, [setInput]);
```

## **6. Event Types**

### **React Event Types**
```typescript
// Form events
const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
  event.preventDefault();
};

// Input events
const handleInput = (event: React.ChangeEvent<HTMLInputElement>) => {
  setValue(event.target.value);
};

const handleTextareaChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
  setValue(event.target.value);
};

// Keyboard events
const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitForm();
  }
};

// Click events
const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
  console.log(event.currentTarget.value);
};

// Focus events
const handleFocus = (event: React.FocusEvent<HTMLInputElement>) => {
  console.log(event.target.value);
};
```

## **7. External Library Types**

### **Vercel AI SDK Types**
```typescript
import type { Message, CreateMessage, ChatRequestOptions } from "ai";

// Message type structure
interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string | null;
  toolInvocations?: ToolInvocation[];
  experimental_attachments?: Attachment[];
}

// Tool invocation types
interface ToolInvocation {
  toolName: string;
  toolCallId: string;
  state: "pending" | "result" | "error";
  result?: any;
}

// Attachment types
interface Attachment {
  name?: string;
  url: string;
  contentType?: string;
}
```

### **React Markdown Types**
```typescript
import { type Components } from "react-markdown";

// Component mapping type
const components: Partial<Components> = {
  code: ({ inline, className, children, ...props }) => {
    // Component implementation
  },
  h1: ({ children, ...props }) => {
    return <h1 {...props}>{children}</h1>;
  },
  // ... other components
};
```

### **Framer Motion Types**
```typescript
import { motion } from "framer-motion";

// Motion component props
<motion.div
  initial={{ y: 5, opacity: 0 }}
  animate={{ y: 0, opacity: 1 }}
  transition={{ delay: 0.05 * index }}
  className="..."
>
  {children}
</motion.div>
```

## **8. Utility Types**

### **Partial, Required, Pick, Omit**
```typescript
// Partial - makes all properties optional
type PartialProps = Partial<ButtonProps>;

// Required - makes all properties required
type RequiredProps = Required<ButtonProps>;

// Pick - select specific properties
type ButtonVariantProps = Pick<ButtonProps, "variant" | "size">;

// Omit - exclude specific properties
type ButtonWithoutVariant = Omit<ButtonProps, "variant">;
```

### **Record, ReturnType, Parameters**
```typescript
// Record - object with specific key/value types
type ButtonVariants = Record<string, string>;

// ReturnType - extract return type of function
type SubmitFunctionReturn = ReturnType<typeof handleSubmit>;

// Parameters - extract parameter types of function
type SubmitFunctionParams = Parameters<typeof handleSubmit>;
```

## **9. Conditional Types**

### **Type Guards**
```typescript
// Type guard functions
function isUserMessage(message: Message): message is Message & { role: "user" } {
  return message.role === "user";
}

function isAssistantMessage(message: Message): message is Message & { role: "assistant" } {
  return message.role === "assistant";
}

// Usage
if (isUserMessage(message)) {
  // TypeScript knows message.role is "user"
  console.log(message.content);
}
```

### **Conditional Rendering Types**
```typescript
// Conditional types based on props
type ConditionalProps<T> = T extends { variant: "destructive" }
  ? { danger: boolean }
  : { danger?: boolean };

// Usage in components
interface ConditionalButtonProps extends ButtonProps {
  danger?: boolean;
}
```

## **10. Type Assertions**

### **as Keyword**
```typescript
// Type assertions
<Markdown>{message.content as string}</Markdown>

// Assert non-null
const element = ref.current as HTMLDivElement;

// Assert specific type
const result = data as WeatherResult;
```

### **Type Guards with Assertions**
```typescript
// Custom type guards
function isWeatherTool(toolName: string): toolName is "get_current_weather" {
  return toolName === "get_current_weather";
}

// Usage
if (isWeatherTool(toolInvocation.toolName)) {
  // TypeScript knows toolName is "get_current_weather"
  return <Weather weatherAtLocation={result} />;
}
```

## **11. Advanced Type Patterns**

### **Discriminated Unions**
```typescript
// Message with discriminated union
type Message = 
  | { role: "user"; content: string; userId: string }
  | { role: "assistant"; content: string; model: string }
  | { role: "system"; content: string; systemId: string };

// Usage
function renderMessage(message: Message) {
  switch (message.role) {
    case "user":
      return <UserMessage content={message.content} userId={message.userId} />;
    case "assistant":
      return <AssistantMessage content={message.content} model={message.model} />;
    case "system":
      return <SystemMessage content={message.content} systemId={message.systemId} />;
  }
}
```

### **Template Literal Types**
```typescript
// Template literal types for CSS classes
type ButtonSize = "sm" | "md" | "lg";
type ButtonVariant = "primary" | "secondary" | "danger";

type ButtonClass = `btn-${ButtonSize}-${ButtonVariant}`;

// Usage
const buttonClass: ButtonClass = "btn-md-primary";
```

## **12. Error Handling Types**

### **Error Boundaries**
```typescript
interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error: Error }>;
}
```

### **Async Error Types**
```typescript
// Async function error handling
const handleAsyncOperation = async (): Promise<Result | Error> => {
  try {
    const result = await apiCall();
    return result;
  } catch (error) {
    return error as Error;
  }
};
```

## **13. Path Aliases and Module Resolution**

### **Path Mapping**
```typescript
// tsconfig.json paths
{
  "paths": {
    "@/*": ["./*"],
    "@/components/*": ["./components/*"],
    "@/lib/*": ["./lib/*"],
    "@/hooks/*": ["./hooks/*"]
  }
}

// Usage in imports
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useScrollToBottom } from "@/hooks/use-scroll-to-bottom";
```

## **14. Type Safety Best Practices**

### **Strict Null Checks**
```typescript
// With strict null checks enabled
const [user, setUser] = useState<User | null>(null);

// Safe access
const userName = user?.name; // string | undefined
const userEmail = user?.email ?? "no-email@example.com";

// Type guards
if (user) {
  // TypeScript knows user is not null
  console.log(user.name);
}
```

### **Exhaustive Type Checking**
```typescript
// Ensure all cases are handled
function handleMessageRole(role: Message["role"]) {
  switch (role) {
    case "user":
      return "User Message";
    case "assistant":
      return "Assistant Message";
    case "system":
      return "System Message";
    default:
      // TypeScript error if new role is added but not handled
      const exhaustiveCheck: never = role;
      return exhaustiveCheck;
  }
}
```

## **15. Common Patterns in YudaiV3**

### **Component Props Pattern**
```typescript
// Used throughout the codebase
interface ComponentProps {
  children: React.ReactNode;
  className?: string;
  // ... other props
}

const Component = ({ children, className, ...props }: ComponentProps) => {
  return (
    <div className={cn("base-classes", className)} {...props}>
      {children}
    </div>
  );
};
```

### **Hook Return Types**
```typescript
// Custom hooks return typed arrays
export function useScrollToBottom<T extends HTMLElement>(): [
  RefObject<T>,
  RefObject<T>,
] {
  // Implementation
  return [containerRef, endRef];
}

// Usage with destructuring
const [containerRef, endRef] = useScrollToBottom<HTMLDivElement>();
```

### **Event Handler Types**
```typescript
// Consistent event handling pattern
const handleInput = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
  setInput(event.target.value);
  adjustHeight();
};

const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitForm();
  }
};
```

### **Conditional Rendering with Type Guards**
```typescript
// Type-safe conditional rendering
{message.role === "assistant" && (
  <div className="avatar-container">
    <SparklesIcon size={14} />
  </div>
)}

{message.toolInvocations?.map((toolInvocation) => {
  const { toolName, toolCallId, state } = toolInvocation;
  
  if (state === "result") {
    return (
      <div key={toolCallId}>
        {toolName === "get_current_weather" ? (
          <Weather weatherAtLocation={result} />
        ) : (
          <pre>{JSON.stringify(result, null, 2)}</pre>
        )}
      </div>
    );
  }
  return <div key={toolCallId} className="skeleton">Loading...</div>;
})}
```

This comprehensive TypeScript guide covers all the type patterns and syntax used in the YudaiV3 codebase, providing you with a complete reference for understanding and working with the type system. 