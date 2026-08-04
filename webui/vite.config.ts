import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // './' là BẮT BUỘC: pywebview nạp trang từ đĩa, đường dẫn tuyệt đối kiểu '/assets/…'
  // sẽ trỏ ra gốc ổ đĩa và trang trắng bóc.
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
  },
})
