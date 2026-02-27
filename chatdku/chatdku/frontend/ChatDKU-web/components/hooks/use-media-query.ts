import { useState, useEffect } from 'react'

/**
 * Custom hook that matches a media query and returns whether it matches.
 * Handles SSR safely by defaulting to false and updating on client-side.
 * Re-renders component when the media query match changes (e.g., on resize).
 * 
 * @param query The media query to match against (e.g., "(min-width: 768px)")
 * @returns boolean indicating if the media query matches
 */
export function useMediaQuery(query: string): boolean {
  // Initialize state with false for SSR
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    // Skip effect on server
    if (typeof window !== 'undefined') {
      // Create media query list
      const mediaQuery = window.matchMedia(query)
      
      // Set initial value
      setMatches(mediaQuery.matches)

      // Create event listener
      const listener = (event: MediaQueryListEvent) => {
        setMatches(event.matches)
      }

      // Add listener
      mediaQuery.addEventListener('change', listener)

      // Cleanup
      return () => {
        mediaQuery.removeEventListener('change', listener)
      }
    }
  }, [query]) // Re-run effect if query changes

  return matches
}
