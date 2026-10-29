import { useState } from "react";

import { ConfirmDialog, Modal } from "./Modal";
import { useStore } from "./store";

const useAction = () => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async (task) => {
    setBusy(true);
    setError("");
    try {
      await task();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, setError, run };
};

const ProfileForm = () => {
  const user = useStore((s) => s.user);
  const updateProfile = useStore((s) => s.updateProfile);
  const notify = useStore((s) => s.notify);
  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email);
  const [password, setPassword] = useState("");
  const { busy, error, run } = useAction();

  const emailChanged = email.trim().toLowerCase() !== user.email;
  const nameChanged = name.trim() !== user.name;

  const submit = async (event) => {
    event.preventDefault();
    const payload = {};
    if (nameChanged) payload.name = name.trim();
    if (emailChanged) {
      payload.email = email.trim();
      payload.current_password = password;
    }
    const ok = await run(() => updateProfile(payload));
    if (ok) {
      setPassword("");
      notify("success", "Profile updated");
    }
  };

  return (
    <form onSubmit={submit} className="nf-account-section">
      <div className="nf-section-title">Profile</div>
      <label className="nf-field">
        <span className="nf-label">Name</span>
        <input className="nf-input" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
      </label>
      <label className="nf-field">
        <span className="nf-label">Email</span>
        <input className="nf-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      {emailChanged && (
        <label className="nf-field">
          <span className="nf-label">Current password</span>
          <input className="nf-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          <span className="nf-hint">Required to change your email.</span>
        </label>
      )}
      {error && <div className="nf-alert is-error" role="alert">{error}</div>}
      <button
        type="submit"
        className="nf-btn is-primary"
        disabled={busy || !name.trim() || !email.trim() || (!nameChanged && !emailChanged) || (emailChanged && !password)}
      >
        {busy ? "Saving…" : "Save profile"}
      </button>
    </form>
  );
};

const PasswordForm = () => {
  const changePassword = useStore((s) => s.changePassword);
  const notify = useStore((s) => s.notify);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const { busy, error, setError, run } = useAction();

  const submit = async (event) => {
    event.preventDefault();
    if (next !== confirm) {
      setError("The new passwords do not match.");
      return;
    }
    const ok = await run(() => changePassword(current, next));
    if (ok) {
      setCurrent("");
      setNext("");
      setConfirm("");
      notify("success", "Password changed. Other devices have been signed out.");
    }
  };

  return (
    <form onSubmit={submit} className="nf-account-section">
      <div className="nf-section-title">Change password</div>
      <label className="nf-field">
        <span className="nf-label">Current password</span>
        <input className="nf-input" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
      </label>
      <label className="nf-field">
        <span className="nf-label">New password</span>
        <input className="nf-input" type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" minLength={8} />
        <span className="nf-hint">At least 8 characters.</span>
      </label>
      <label className="nf-field">
        <span className="nf-label">Confirm new password</span>
        <input className="nf-input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
      </label>
      {error && <div className="nf-alert is-error" role="alert">{error}</div>}
      <button type="submit" className="nf-btn is-primary" disabled={busy || !current || next.length < 8 || !confirm}>
        {busy ? "Changing…" : "Change password"}
      </button>
    </form>
  );
};

const DangerZone = () => {
  const deleteAccount = useStore((s) => s.deleteAccount);
  const notify = useStore((s) => s.notify);
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const { busy, error, run } = useAction();

  const remove = async () => {
    const ok = await run(() => deleteAccount(password));
    if (ok) notify("info", "Your account has been deleted.");
  };

  return (
    <div className="nf-account-section nf-danger-zone">
      <div className="nf-section-title">Danger zone</div>
      <p className="nf-muted">Deleting your account permanently removes your profile, all saved workflows and your file workspace.</p>
      <button type="button" className="nf-btn is-danger-outline" onClick={() => setConfirming(true)}>
        Delete my account
      </button>
      {confirming && (
        <ConfirmDialog
          title="Delete your account?"
          message={
            <>
              This cannot be undone. Enter your password to confirm.
              <input
                className="nf-input nf-confirm-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                autoComplete="current-password"
                autoFocus
              />
              {error && <span className="nf-alert is-error" role="alert">{error}</span>}
            </>
          }
          confirmLabel="Delete forever"
          danger
          busy={busy}
          confirmDisabled={!password}
          onConfirm={remove}
          onCancel={() => setConfirming(false)}
        />
      )}
    </div>
  );
};

export const AccountDialog = ({ onClose }) => (
  <Modal title="Account" subtitle="Manage your profile and security" onClose={onClose}>
    <ProfileForm />
    <PasswordForm />
    <DangerZone />
  </Modal>
);
