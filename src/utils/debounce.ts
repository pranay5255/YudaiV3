/**
 * Debounce utility to prevent excessive function calls
 * Essential for preventing race conditions in real-time updates
 */

/**
 * Creates a debounced version of a function that delays invoking func until after 
 * wait milliseconds have elapsed since the last time the debounced function was invoked.
 * 
 * @param func - The function to debounce
 * @param wait - The number of milliseconds to delay
 * @param immediate - If true, trigger the function on the leading edge instead of trailing
 * @returns Debounced function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number,
  immediate: boolean = false
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;
  
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
 * @param func - The function to throttle
 * @param wait - The number of milliseconds to throttle invocations to
 * @returns Throttled function
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  
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
 * @param func - The function to batch
 * @param wait - The number of milliseconds to wait before executing
 * @param maxBatchSize - Maximum number of items to batch together
 * @returns Batched function
 */
export function batch<T>(
  func: (items: T[]) => void,
  wait: number,
  maxBatchSize: number = 10
): (item: T) => void {
  let items: T[] = [];
  let timeout: NodeJS.Timeout | null = null;
  
  const flush = () => {
    if (items.length > 0) {
      func([...items]);
      items = [];
    }
    timeout = null;
  };
  
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