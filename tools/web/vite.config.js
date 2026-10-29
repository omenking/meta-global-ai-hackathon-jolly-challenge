import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/static/app/',
  build: {
    outDir: '../static/app',
    emptyOutDir: true,
  },
});
