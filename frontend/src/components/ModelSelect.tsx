import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { DEFAULT_MODEL_LABEL, type ModelChoice } from "../lib/types";

type Option = { value: ModelChoice; label: string; disabled?: boolean };
export function ModelSelect({
  value,
  options,
  disabled,
  onChange,
}: {
  value: ModelChoice;
  options: Option[];
  disabled: boolean;
  onChange: (value: ModelChoice) => void;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const listId = useId();
  const selected = options.find((option) => option.value === value);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);
  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);
  const reveal = () => {
    setActive(
      Math.max(
        0,
        options.findIndex((option) => option.value === value),
      ),
    );
    setOpen(true);
  };
  const choose = (index: number) => {
    if (!options[index]?.disabled) {
      onChange(options[index].value);
      setOpen(false);
    }
  };
  function keyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const enabled = options
        .map((option, i) => (option.disabled ? -1 : i))
        .filter((i) => i >= 0);
      if (!enabled.length) return;
      const position = enabled.indexOf(active);
      const next =
        event.key === "Home"
          ? enabled[0]
          : event.key === "End"
            ? enabled.at(-1)!
            : enabled[
                (position +
                  (event.key === "ArrowDown" ? 1 : -1) +
                  enabled.length) %
                  enabled.length
              ];
      setActive(
        open || event.key === "Home" || event.key === "End"
          ? next
          : Math.max(
              0,
              options.findIndex((option) => option.value === value),
            ),
      );
      setOpen(true);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (open) choose(active);
      else reveal();
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
    } else if (event.key === "Tab") setOpen(false);
  }
  return (
    <div ref={root} className="model-picker">
      <label className="sr-only" htmlFor="model">
        Retrieval model
      </label>
      <button
        type="button"
        id="model"
        role="combobox"
        className="model-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        onKeyDown={keyDown}
        onClick={() => (open ? setOpen(false) : reveal())}
        onBlur={() => setOpen(false)}
      >
        <span>{selected?.label || DEFAULT_MODEL_LABEL}</span>
        <svg
          aria-hidden="true"
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
        >
          <path d="m3 6 5 5 5-5" />
        </svg>
      </button>
      {open && (
        <ul
          id={listId}
          className="model-menu"
          role="listbox"
          aria-label="Available models"
        >
          {options.map((option, index) => (
            <li
              key={option.value}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={value === option.value}
              aria-disabled={option.disabled || undefined}
              data-active={index === active}
              onPointerMove={() => {
                if (!option.disabled) setActive(index);
              }}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(index)}
            >
              <span>{option.label}</span>
              {value === option.value && <span aria-hidden="true">✓</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
