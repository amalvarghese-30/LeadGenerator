import React from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from './Button';

interface ConfirmModalProps {
  isOpen: boolean;
  onClose?: () => void;
  onCancel?: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  message: string;
  confirmLabel?: string;
  confirmText?: string;
  cancelLabel?: string;
  cancelText?: string;
  isLoading?: boolean;
  variant?: 'danger' | 'warning' | 'primary';
  confirmVariant?: 'danger' | 'warning' | 'primary';
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  onClose,
  onCancel,
  onConfirm,
  title,
  message,
  confirmLabel,
  confirmText,
  cancelLabel,
  cancelText,
  isLoading = false,
  variant,
  confirmVariant,
}) => {
  if (!isOpen) return null;

  const handleClose = onCancel || onClose || (() => {});
  const actualConfirmText = confirmText || confirmLabel || 'Confirm';
  const actualCancelText = cancelText || cancelLabel || 'Cancel';
  const actualVariant = confirmVariant || variant || 'danger';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in">
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-100 overflow-hidden">
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                actualVariant === 'danger' ? 'bg-rose-50 text-rose-600' : 'bg-amber-50 text-amber-600'
              }`}
            >
              <AlertTriangle className="w-5 h-5 stroke-[2.2]" />
            </div>
            <div className="flex-1">
              <h3 className="text-base font-bold text-slate-900 leading-tight">{title}</h3>
              <p className="mt-2 text-xs text-slate-500 leading-relaxed">{message}</p>
            </div>
            <button
              onClick={handleClose}
              className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-50 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="mt-6 flex items-center justify-end gap-2.5">
            <Button variant="secondary" size="sm" onClick={handleClose} disabled={isLoading}>
              {actualCancelText}
            </Button>
            <Button
              variant={actualVariant === 'danger' ? 'danger' : 'primary'}
              size="sm"
              onClick={onConfirm}
              isLoading={isLoading}
            >
              {actualConfirmText}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
