import { useCallback } from "react";
import { useStore } from "../store";

/** Returns a curried change handler: set("field") -> (event) => store update. */
export const useNodeField = (id) => {
  const update = useStore((state) => state.updateNodeField);
  return useCallback((field) => (event) => update(id, field, event.target.value), [id, update]);
};

export const Field = ({ label, hint, children }) => (
  <label className="nf-field">
    <span className="nf-label">{label}</span>
    {children}
    {hint && <span className="nf-hint">{hint}</span>}
  </label>
);

export const Select = ({ value, onChange, options }) => (
  <select className="nf-input nodrag" value={value} onChange={onChange}>
    {options.map((option) => {
      const [optionValue, optionLabel] = Array.isArray(option) ? option : [option, option];
      return (
        <option key={optionValue} value={optionValue}>
          {optionLabel}
        </option>
      );
    })}
  </select>
);

export const TextInput = ({ value, onChange, placeholder, type = "text", ...rest }) => (
  <input className="nf-input nodrag" type={type} value={value ?? ""} onChange={onChange} placeholder={placeholder} {...rest} />
);

export const TextArea = ({ value, onChange, placeholder, rows = 3, mono = false }) => (
  <textarea
    className={`nf-input nf-textarea nodrag nowheel${mono ? " is-mono" : ""}`}
    value={value ?? ""}
    onChange={onChange}
    placeholder={placeholder}
    rows={rows}
    spellCheck={false}
  />
);
