import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
var DEFAULT_PROXY_TARGET = 'http://127.0.0.1:8000';
function trimTrailingSlash(value) {
    return value.replace(/\/$/, '');
}
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var env = loadEnv(mode, '.', '');
    var proxyTarget = trimTrailingSlash(env.VITE_API_PROXY_TARGET || env.VITE_API_BASE_URL || DEFAULT_PROXY_TARGET);
    return {
        plugins: [react()],
        server: {
            port: 5173,
            proxy: {
                '/api': {
                    target: proxyTarget,
                    changeOrigin: true,
                },
            },
        },
    };
});
