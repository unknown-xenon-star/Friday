import { state } from './state.js';

export function showBanner(message, type) {
    const banner = document.getElementById('notify-banner');
    const text = document.getElementById('notify-text');

    banner.className = `notification-banner ${type}`;
    text.innerHTML = message.replace(/\n/g, '<br/>');
    banner.classList.add('show');
}

export function hideBanner() {
    const banner = document.getElementById('notify-banner');
    banner.classList.remove('show');
}

export function showToast(message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse forwards';
        setTimeout(() => {
            if (container.contains(toast)) {
                container.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

export function showUpdateToast() {
    const container = document.getElementById('toast-container');
    if (state.activeUpdateToast && container.contains(state.activeUpdateToast)) {
        state.updateToastCount++;
        state.activeUpdateToast.innerHTML = `📂 Added next function/node to graph (+${state.updateToastCount})`;
        
        clearTimeout(state.updateToastTimer);
        state.updateToastTimer = setTimeout(() => {
            const toastToDismiss = state.activeUpdateToast;
            toastToDismiss.style.animation = 'slideIn 0.3s ease reverse forwards';
            setTimeout(() => {
                if (container.contains(toastToDismiss)) {
                    container.removeChild(toastToDismiss);
                }
            }, 300);
            state.activeUpdateToast = null;
            state.updateToastCount = 0;
        }, 3000);
    } else {
        state.updateToastCount = 0;
        state.activeUpdateToast = document.createElement('div');
        state.activeUpdateToast.className = 'toast';
        state.activeUpdateToast.innerHTML = `📂 Added next function/node to graph`;
        container.appendChild(state.activeUpdateToast);

        state.updateToastTimer = setTimeout(() => {
            const toastToDismiss = state.activeUpdateToast;
            toastToDismiss.style.animation = 'slideIn 0.3s ease reverse forwards';
            setTimeout(() => {
                if (container.contains(toastToDismiss)) {
                    container.removeChild(toastToDismiss);
                }
            }, 300);
            state.activeUpdateToast = null;
            state.updateToastCount = 0;
        }, 3000);
    }
}
