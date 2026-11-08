import { useSyncExternalStore } from 'react'

/** Prices are hidden until asked for, so the inventory can be shown to someone without showing
 *  what everything cost. The choice belongs to this browser, not to the account. */
const KEY = 'my-stuff.show-prices'
const listeners = new Set<() => void>()

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === 'true'
  } catch {
    return false
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function usePricesVisible(): boolean {
  return useSyncExternalStore(subscribe, read)
}

export function setPricesVisible(visible: boolean) {
  try {
    localStorage.setItem(KEY, String(visible))
  } catch {
    // Private windows can refuse storage. The toggle then does nothing, and prices stay hidden.
  }
  listeners.forEach((listener) => listener())
}
