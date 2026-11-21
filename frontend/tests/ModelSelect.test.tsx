import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ModelSelect } from "../src/components/ModelSelect";
const options = [
  { value: "automatic" as const, label: "Automatic" },
  { value: "bm25" as const, label: "BM25" },
  { value: "bge" as const, label: "BGE + FAISS", disabled: true },
];
it("navega por teclado, evita opciones deshabilitadas y confirma con Enter", async () => {
  const onChange = vi.fn();
  const user = userEvent.setup();
  render(
    <ModelSelect
      value="automatic"
      options={options}
      disabled={false}
      onChange={onChange}
    />,
  );
  const trigger = screen.getByRole("combobox", {
    name: "Retrieval model",
  });
  trigger.focus();
  await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
  expect(onChange).toHaveBeenCalledWith("bm25");
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  await user.click(trigger);
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});
it("cierra con Tab o al pulsar fuera sin cambiar el modelo", async () => {
  const onChange = vi.fn();
  const user = userEvent.setup();
  render(
    <>
      <ModelSelect
        value="automatic"
        options={options}
        disabled={false}
        onChange={onChange}
      />
      <button>Fuera</button>
    </>,
  );
  await user.click(screen.getByRole("combobox"));
  await user.tab();
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  await user.click(screen.getByRole("combobox"));
  await user.click(screen.getByText("Fuera"));
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(onChange).not.toHaveBeenCalled();
});
