"""
Anti-Detection V4 — Deep stealth injection with iframe recursion.

Features:
  - WebDriver override
  - Chrome runtime spoofing
  - Permissions API bypass
  - Plugins & Languages fingerprint
  - Canvas fingerprint noise (pixel-level poisoning)
  - WebGL vendor/renderer spoofing
  - Font measurement noise
  - Recursive iframe injection (critical for betting sites)
  - MutationObserver for dynamically added iframes
  - Modernizr hairline fix
"""

# V4 Full Stealth Injection — "THE GHOST PROTOCOL"
STEALTH_INJECTION_V4 = """
(() => {
    const installStealth = (win) => {
        if (win._stealth_active) return;
        win._stealth_active = true;

        // 1. Webdriver Override
        Object.defineProperty(win.navigator, 'webdriver', { get: () => undefined });

        // 2. Chrome Runtime Spoof (simulates installed extensions)
        win.chrome = win.chrome || {};
        win.chrome.runtime = win.chrome.runtime || {};

        // 3. Permissions API Bypass
        try {
            const originalQuery = win.navigator.permissions.query;
            win.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        } catch(e) {}

        // 4. Plugins & Languages (coherent fingerprint)
        try {
            Object.defineProperty(win.navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(win.navigator, 'languages', { get: () => ['it-IT', 'it', 'en-US', 'en'] });
        } catch(e) {}

        // 5. Canvas Fingerprint Noise (breaks unique graphic hash)
        try {
            const origToDataURL = win.HTMLCanvasElement.prototype.toDataURL;
            win.HTMLCanvasElement.prototype.toDataURL = function(type) {
                const ctx = this.getContext('2d');
                if (ctx) {
                    const imageData = ctx.getImageData(0, 0, Math.min(this.width, 2), Math.min(this.height, 2));
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] = imageData.data[i] ^ (Math.random() > 0.5 ? 1 : 0);
                    }
                    ctx.putImageData(imageData, 0, 0);
                }
                return origToDataURL.apply(this, arguments);
            };
        } catch(e) {}

        // 6. WebGL Vendor/Renderer Spoof
        try {
            const getParam = win.WebGLRenderingContext.prototype.getParameter;
            win.WebGLRenderingContext.prototype.getParameter = function(param) {
                if (param === 37445) return 'Google Inc. (Intel)';
                if (param === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)';
                return getParam.apply(this, arguments);
            };
        } catch(e) {}

        // 7. Font Measurement Noise
        try {
            const origMeasure = win.CanvasRenderingContext2D.prototype.measureText;
            win.CanvasRenderingContext2D.prototype.measureText = function(text) {
                const result = origMeasure.apply(this, arguments);
                const noise = 0.00001 * (Math.random() - 0.5);
                Object.defineProperty(result, 'width', { value: result.width + noise });
                return result;
            };
        } catch(e) {}

        // 8. Iframe Recursive Injection (critical for betting/ads)
        try {
            const contentWindowGetter = Object.getOwnPropertyDescriptor(
                win.HTMLIFrameElement.prototype, 'contentWindow'
            ).get;
            Object.defineProperty(win.HTMLIFrameElement.prototype, 'contentWindow', {
                get: function() {
                    const w = contentWindowGetter.apply(this, arguments);
                    if (w) {
                        try { installStealth(w); } catch(e) {}
                    }
                    return w;
                }
            });
        } catch(e) {}

        // 9. Modernizr Hairline Fix
        try {
            const elementDescriptor = Object.getOwnPropertyDescriptor(
                win.HTMLElement.prototype, 'offsetHeight'
            );
            if (elementDescriptor) {
                Object.defineProperty(win.HTMLDivElement.prototype, 'offsetHeight', {
                    ...elementDescriptor,
                    get: function() {
                        if (this.id === 'modernizr') return 1;
                        return elementDescriptor.get.apply(this, arguments);
                    },
                });
            }
        } catch(e) {}
    };

    installStealth(window);

    // Observer for dynamically added iframes (AJAX-loaded)
    new MutationObserver(mutations => {
        mutations.forEach(m => {
            m.addedNodes.forEach(n => {
                if (n.tagName === 'IFRAME' && n.contentWindow) {
                    try { installStealth(n.contentWindow); } catch(e) {}
                }
            });
        });
    }).observe(document.documentElement, { childList: true, subtree: true });
})();
"""
