import React, { useEffect } from 'react';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';
import { Toast as ToastType } from '../types';

interface ToastProps {
  toast: ToastType;
  onRemove: (id: string) => void;
}

export const Toast: React.FC<ToastProps> = ({ toast, onRemove }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onRemove(toast.id);
    }, 5000);

    return () => clearTimeout(timer);
  }, [toast.id, onRemove]);

  const getToastStyles = () => {
    switch (toast.type) {
      case 'success':
        return {
          bg: 'bg-success/20 border-success/30',
          text: 'text-success',
          icon: CheckCircle,
        };
      case 'error':
        return {
          bg: 'bg-error/20 border-error/30',
          text: 'text-error',
          icon: XCircle,
        };
      case 'info':
        return {
          bg: 'bg-primary/20 border-primary/30',
          text: 'text-primary',
          icon: Info,
        };
    }
  };

  const { bg, text, icon: Icon } = getToastStyles();

  return (
    <div className={`
      ${bg} border rounded-lg shadow-lg p-4 flex items-center gap-3 
      animate-slide-in min-w-[320px] max-w-md
    `}>
      <Icon className={`w-5 h-5 flex-shrink-0 ${text}`} />
      <p className={`flex-1 text-sm ${text}`}>{toast.message}</p>
      <button
        onClick={() => onRemove(toast.id)}
        className={`p-1 hover:bg-white/10 rounded transition-colors ${text}`}
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};

interface ToastContainerProps {
  toasts: ToastType[];
  onRemoveToast: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onRemoveToast }) => {
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onRemove={onRemoveToast} />
      ))}
    </div>
  );
};