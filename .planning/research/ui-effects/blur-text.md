# Blur Text

Source URLs:
- Page: https://reactbits.dev/text-animations/blur-text
- Component: https://raw.githubusercontent.com/DavidHDev/react-bits/main/src/content/TextAnimations/BlurText/BlurText.jsx

## Category

Text Animations. Text reveals on scroll-into-view by animating each word (or character) from blurred + transparent + offset to sharp + opaque + in place, staggered per segment for a cascading focus-in effect.

## Dependencies

`motion` (Framer Motion v11+, imported as `motion/react`) for the keyframed `motion.span` animation. `IntersectionObserver` (native browser API) to trigger on viewport entry. Tailwind utility classes are used on the spans (`inline-block`, `will-change-[transform,filter,opacity]`) but the animation itself is JS-driven via the motion library, not pure CSS. No `three`/WebGL.

## Source

### BlurText.jsx

```jsx
import { motion } from 'motion/react';
import { useEffect, useRef, useState, useMemo } from 'react';

const buildKeyframes = (from, steps) => {
  const keys = new Set([...Object.keys(from), ...steps.flatMap(s => Object.keys(s))]);

  const keyframes = {};
  keys.forEach(k => {
    keyframes[k] = [from[k], ...steps.map(s => s[k])];
  });
  return keyframes;
};

const BlurText = ({
  text = '',
  delay = 200,
  className = '',
  animateBy = 'words',
  direction = 'top',
  threshold = 0.1,
  rootMargin = '0px',
  animationFrom,
  animationTo,
  easing = t => t,
  onAnimationComplete,
  stepDuration = 0.35
}) => {
  const elements = animateBy === 'words' ? text.split(' ') : text.split('');
  const [inView, setInView] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.unobserve(ref.current);
        }
      },
      { threshold, rootMargin }
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  const defaultFrom = useMemo(
    () =>
      direction === 'top' ? { filter: 'blur(10px)', opacity: 0, y: -50 } : { filter: 'blur(10px)', opacity: 0, y: 50 },
    [direction]
  );

  const defaultTo = useMemo(
    () => [
      {
        filter: 'blur(5px)',
        opacity: 0.5,
        y: direction === 'top' ? 5 : -5
      },
      { filter: 'blur(0px)', opacity: 1, y: 0 }
    ],
    [direction]
  );

  const fromSnapshot = animationFrom ?? defaultFrom;
  const toSnapshots = animationTo ?? defaultTo;

  const stepCount = toSnapshots.length + 1;
  const totalDuration = stepDuration * (stepCount - 1);
  const times = Array.from({ length: stepCount }, (_, i) => (stepCount === 1 ? 0 : i / (stepCount - 1)));

  return (
    <p ref={ref} className={className} style={{ display: 'flex', flexWrap: 'wrap' }}>
      {elements.map((segment, index) => {
        const animateKeyframes = buildKeyframes(fromSnapshot, toSnapshots);

        const spanTransition = {
          duration: totalDuration,
          times,
          delay: (index * delay) / 1000
        };
        spanTransition.ease = easing;

        return (
          <motion.span
            className="inline-block will-change-[transform,filter,opacity]"
            key={index}
            initial={fromSnapshot}
            animate={inView ? animateKeyframes : fromSnapshot}
            transition={spanTransition}
            onAnimationComplete={index === elements.length - 1 ? onAnimationComplete : undefined}
          >
            {segment === ' ' ? ' ' : segment}
            {animateBy === 'words' && index < elements.length - 1 && ' '}
          </motion.span>
        );
      })}
    </p>
  );
};

export default BlurText;
```

> Verbatim note: in the original source the two string literals in the JSX (`segment === ' ' ? ' ' : segment` and the trailing `' '` for word spacing) use the unicode no-break space escape ` `. In the fenced block above those appear as literal NBSP glyphs; treat them as ` `.

## Technique

The text is split into an array of words (on spaces) or characters. An `IntersectionObserver` flips `inView` true once the paragraph enters the viewport (then unobserves, so it animates only once). Each segment is a `motion.span` that starts at a "from" snapshot (`blur(10px)`, `opacity: 0`, offset `y` of -50 or +50 depending on `direction`) and animates through a keyframe sequence built by `buildKeyframes`: a midpoint (`blur(5px)`, `opacity: 0.5`, small overshoot `y`) and a final state (`blur(0px)`, `opacity: 1`, `y: 0`). `buildKeyframes` merges the from-object and each step into per-property arrays that Framer Motion interpolates. The `times` array spreads the keyframes evenly across `totalDuration`, and each span's `delay` is `index * delay / 1000` seconds, producing the staggered cascade. The last span carries the `onAnimationComplete` callback.

## Svelte 5 port note

Ports cleanly. Two viable routes for Svelte 5 + Tailwind v4:

1. Svelte transitions / custom CSS (no library): split `text` into segments in a `$derived`, render each in a `<span>`, and gate visibility with an `IntersectionObserver` wired in an `$effect` (set an `inView = $state(false)`). Drive the blur/opacity/translate with a per-span CSS transition or keyframe animation whose `transition-delay` / `animation-delay` is `${i * delay}ms`. This is the lightest and matches the dark theme without extra deps. The two-step keyframe (blur 10->5->0, opacity 0->0.5->1, y -50->5->0) maps directly to a `@keyframes` rule.
2. `motion-one` (closest to source): Framer Motion's `motion/react` maps to `motion-one`'s `animate()` with `offset`/`times` and per-element `delay`; call it inside the `IntersectionObserver` callback. Use this if you want the exact multi-keyframe easing semantics.

For dark theme just inherit text color; nothing in the effect is color-bound. Add a `prefers-reduced-motion` short-circuit (render final state immediately). Note React `y` is a transform offset in px — emit `translateY(...)` in the Svelte version. Keep the `&nbsp;` (` `) handling for word spacing.
