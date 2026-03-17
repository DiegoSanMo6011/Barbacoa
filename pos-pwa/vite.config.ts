import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '')
    const edgeTarget = env.VITE_EDGE_URL || 'http://localhost:8000'

    return {
        plugins: [
            react(),
            VitePWA({
                registerType: 'autoUpdate',
                includeAssets: ['pwa-192.svg', 'pwa-512.svg'],
                manifest: {
                    name: 'Barbacoa POS',
                    short_name: 'Barbacoa',
                    description: 'Sistema de cobro e inventario offline-first',
                    theme_color: '#1f5eff',
                    background_color: '#f4f7fb',
                    display: 'standalone',
                    orientation: 'portrait',
                    start_url: '/venta',
                    scope: '/',
                    icons: [
                        {
                            src: '/pwa-192.svg',
                            sizes: '192x192',
                            type: 'image/svg+xml',
                            purpose: 'any maskable',
                        },
                        {
                            src: '/pwa-512.svg',
                            sizes: '512x512',
                            type: 'image/svg+xml',
                            purpose: 'any maskable',
                        },
                    ],
                },
                workbox: {
                    navigateFallback: '/index.html',
                    runtimeCaching: [
                        {
                            urlPattern: /^https?:\/\/.*\/api\/.*/i,
                            handler: 'NetworkFirst',
                            options: {
                                cacheName: 'api-cache',
                                networkTimeoutSeconds: 5,
                            },
                        },
                    ],
                },
            }),
        ],
        server: {
            port: 5173,
            host: true, // accesible en red local (all-in-one)
            proxy: {
                '/api': {
                    target: edgeTarget,
                    changeOrigin: true,
                    secure: false,
                    rewrite: (path) => path.replace(/^\/api/, ''),
                },
            },
        },
    }
})
