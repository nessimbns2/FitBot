/**
 * src/components/AccountSettings.tsx
 * Account card for the profile page: display name, password change, account deletion.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, Mail, Trash2, UserRound } from 'lucide-react';
import { Button, Card, Dialog } from '../design';
import { useAuth } from '../context/AuthContext';

type Notify = (type: 'success' | 'error', message: string) => void;

const inputClass =
  'w-full bg-[var(--bg-subtle)] border border-[var(--border-prominent)] text-[var(--text-primary)] text-sm rounded-xl px-3.5 py-2.5 min-h-[44px] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focused)] focus:border-transparent transition-all';

function LabeledInput({ label, ...props }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs sm:text-sm font-semibold text-[var(--text-primary)]">{label}</span>
      <input className={inputClass} {...props} />
    </label>
  );
}

export function AccountSettings({ notify }: { notify: Notify }) {
  const { user, updateName, changePassword, deleteAccount } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState(user?.full_name || '');
  const [savingName, setSavingName] = useState(false);

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [savingPw, setSavingPw] = useState(false);

  const [showDelete, setShowDelete] = useState(false);
  const [deletePw, setDeletePw] = useState('');
  const [deleting, setDeleting] = useState(false);

  const onSaveName = async (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) return notify('error', 'Name must contain at least 2 characters.');
    setSavingName(true);
    try {
      await updateName(name);
      notify('success', 'Account name updated.');
    } catch (err: any) {
      notify('error', err.message || 'Could not update the name.');
    } finally {
      setSavingName(false);
    }
  };

  const onChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw.length < 8 || !/[A-Za-z]/.test(newPw) || !/\d/.test(newPw)) {
      return notify('error', 'New password: at least 8 characters with a letter and a digit.');
    }
    setSavingPw(true);
    try {
      await changePassword(currentPw, newPw);
      setCurrentPw('');
      setNewPw('');
      notify('success', 'Password changed.');
    } catch (err: any) {
      notify('error', err.message || 'Could not change the password.');
    } finally {
      setSavingPw(false);
    }
  };

  const onDelete = async () => {
    setDeleting(true);
    try {
      await deleteAccount(deletePw);
      navigate('/register', { replace: true });
    } catch (err: any) {
      notify('error', err.message || 'Could not delete the account.');
      setDeleting(false);
    }
  };

  return (
    <Card title="Account & Security" subtitle="Your login details. Passwords are stored as bcrypt hashes only.">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <form onSubmit={onSaveName} className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <Mail className="w-4 h-4" />
            <span className="truncate">{user?.email}</span>
          </div>
          <LabeledInput label="Display name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoComplete="name" />
          <Button type="submit" variant="secondary" size="sm" isLoading={savingName} leftIcon={<UserRound className="w-3.5 h-3.5" />} className="self-start">
            Save name
          </Button>
        </form>

        <form onSubmit={onChangePassword} className="flex flex-col gap-4">
          <LabeledInput label="Current password" type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} autoComplete="current-password" />
          <LabeledInput label="New password" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} autoComplete="new-password" />
          <Button
            type="submit"
            variant="secondary"
            size="sm"
            isLoading={savingPw}
            disabled={!currentPw || !newPw}
            leftIcon={<KeyRound className="w-3.5 h-3.5" />}
            className="self-start"
          >
            Change password
          </Button>
        </form>
      </div>

      <div className="mt-8 pt-5 border-t border-[var(--border-subtle)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[var(--text-primary)]">Delete account</p>
          <p className="text-xs text-[var(--text-secondary)]">Permanently removes your profile, chats, workouts and meals.</p>
        </div>
        <Button variant="danger" size="sm" onClick={() => setShowDelete(true)} leftIcon={<Trash2 className="w-3.5 h-3.5" />}>
          Delete account
        </Button>
      </div>

      <Dialog isOpen={showDelete} onClose={() => setShowDelete(false)} title="Delete your account?">
        <div className="space-y-4">
          <p className="text-sm text-[var(--text-secondary)]">
            This cannot be undone. All your data will be erased from the database. Enter your password to confirm.
          </p>
          <LabeledInput label="Password" type="password" value={deletePw} onChange={(e) => setDeletePw(e.target.value)} autoComplete="current-password" />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setShowDelete(false)}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" onClick={onDelete} isLoading={deleting} disabled={!deletePw}>
              Delete permanently
            </Button>
          </div>
        </div>
      </Dialog>
    </Card>
  );
}
