/**
 * Debounce utility to prevent excessive function calls.
 * Essential for preventing race conditions in real-time updates.
 *
 * TypeScript Generics Usage:
 * - <T>: T is a generic type parameter representing any function type.
 * - By constraining T to (...args: unknown[]) => unknown, we ensure T is a function that can take any arguments and return any value.
 * - Parameters<T> is a TypeScript utility type that extracts the parameter types of function T as a tuple.
 * - This allows the returned debounced function to have the exact same argument types as the original function.
 */

/**
 * Creates a debounced version of a function that delays invoking func until after 
 * wait milliseconds have elapsed since the last time the debounced function was invoked.
 * 
 * @template T - The type of the function to debounce. T must be a function type.
 * @param func - The function to debounce.
 * @param wait - The number of milliseconds to delay.
 * @param immediate - If true, trigger the function on the leading edge instead of trailing.
 * @returns Debounced function with the same parameters as func.
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number,
  immediate: boolean = false
): (...args: Parameters<T>) => void {
  // timeout holds the reference to the timer. NodeJS.Timeout is used for compatibility with Node and browser.
  let timeout: NodeJS.Timeout | null = null;
  
  // The returned function preserves the argument types of func using Parameters<T>.
  return (...args: Parameters<T>) => {
    const later = () => {
      timeout = null;
      if (!immediate) func(...args);
    };
    
    const callNow = immediate && !timeout;
    
    if (timeout) {
      clearTimeout(timeout);
    }
    
    timeout = setTimeout(later, wait);
    
    if (callNow) {
      func(...args);
    }
  };
}

/**
 * Creates a throttled version of a function that only invokes func at most once per 
 * every wait milliseconds.
 * 
 * TypeScript Generics Usage:
 * - <T>: T is a generic type parameter representing any function type.
 * - Parameters<T> ensures the returned throttled function has the same argument types as func.
 * 
 * @template T - The type of the function to throttle. T must be a function type.
 * @param func - The function to throttle.
 * @param wait - The number of milliseconds to throttle invocations to.
 * @returns Throttled function with the same parameters as func.
 */
export function throttle<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  
  // The returned function preserves the argument types of func using Parameters<T>.
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, wait);
    }
  };
}

/**
 * Creates a batched version of a function that collects multiple calls and 
 * executes them together after a delay.
 * 
 * TypeScript Generics Usage:
 * - <T>: T is a generic type parameter representing the type of items to batch.
 * - func: (items: T[]) => void - The function to call with the batch of items.
 * - The returned function takes a single item of type T.
 * 
 * @template T - The type of items to batch.
 * @param func - The function to batch, which receives an array of T.
 * @param wait - The number of milliseconds to wait before executing.
 * @param maxBatchSize - Maximum number of items to batch together.
 * @returns Batched function that accepts a single item of type T.
 */
export function batch<T>(
  func: (items: T[]) => void,
  wait: number,
  maxBatchSize: number = 10
): (item: T) => void {
  let items: T[] = [];
  let timeout: NodeJS.Timeout | null = null;
  
  // flush calls the batch function with all collected items and resets the batch.
  const flush = () => {
    if (items.length > 0) {
      func([...items]);
      items = [];
    }
    timeout = null;
  };
  
  // The returned function accepts a single item of type T.
  return (item: T) => {
    items.push(item);
    
    // If we've reached max batch size, flush immediately
    if (items.length >= maxBatchSize) {
      if (timeout) {
        clearTimeout(timeout);
      }
      flush();
      return;
    }
    
    // Otherwise, wait for the timeout
    if (!timeout) {
      timeout = setTimeout(flush, wait);
    }
  };
}