/** Bộ icon NÉT dùng chung.
 *
 * Trước đây giao diện trộn hai thứ: emoji tô màu (🔍 🌀 🎮 🎯 🖼 🗑 …) và icon nét
 * vẽ tay ở ribbon. Emoji tô màu luôn chỏi vì:
 *   - nó mang màu riêng, không theo `currentColor` nên không hoà với theme,
 *   - hình dáng phụ thuộc font hệ thống, mỗi máy một kiểu,
 *   - nét dày mỏng không khớp với các icon còn lại.
 *
 * Toàn bộ vẽ bằng `stroke="currentColor"` nên tự ăn màu chỗ đặt: mờ khi nút bị tắt,
 * sáng khi hover, đổi theo màu nhấn nếu cần.
 *
 * KHÔNG đụng tới ký hiệu đơn sắc (→ ↻ ⇧ ▤ ■ ▶ ① ✕): chúng vốn đã là nét một màu.
 */

const S = {
  fill: 'none' as const,
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

const HINH: Record<string, React.ReactNode> = {
  /* --- loại hành động (hiện trong hộp trên canvas & danh sách hành động) --- */
  'left-click': <><path {...S} d="M5.5 6.2a2.5 2.5 0 0 1 2.5-2.5h0a2.5 2.5 0 0 1 2.5 2.5v3.6a2.5 2.5 0 0 1-2.5 2.5h0a2.5 2.5 0 0 1-2.5-2.5z" /><path {...S} d="M5.5 6.6h2.5V3.8" /></>,
  'right-click': <><path {...S} d="M5.5 6.2a2.5 2.5 0 0 1 2.5-2.5h0a2.5 2.5 0 0 1 2.5 2.5v3.6a2.5 2.5 0 0 1-2.5 2.5h0a2.5 2.5 0 0 1-2.5-2.5z" /><path {...S} d="M10.5 6.6H8V3.8" /></>,
  'mod-click': <><path {...S} d="M6.6 7.4a2.2 2.2 0 0 1 2.2-2.2h0a2.2 2.2 0 0 1 2.2 2.2v3.2a2.2 2.2 0 0 1-2.2 2.2h0a2.2 2.2 0 0 1-2.2-2.2z" /><path {...S} d="M2 4.4h3.2M3.6 2.8v3.2" /></>,
  'key-press': <><rect {...S} x="2" y="4.5" width="12" height="7.5" rx="1.4" /><path {...S} d="M4.4 6.9h.01M7 6.9h.01M9.6 6.9h.01M12 6.9h.01M4.4 9.4h7.2" /></>,
  'move-wasd': <><rect {...S} x="1.8" y="4.6" width="12.4" height="7.4" rx="2.6" /><path {...S} d="M4.2 8.3h2.2M5.3 7.2v2.2" /><circle {...S} cx="10.4" cy="7.6" r=".55" /><circle {...S} cx="11.8" cy="9.1" r=".55" /></>,
  delay: <><circle {...S} cx="8" cy="8.4" r="5.2" /><path {...S} d="M8 5.6v2.8l1.9 1.1" /></>,
  'check-mod': <><circle {...S} cx="7.2" cy="7.2" r="4.2" /><path {...S} d="M10.3 10.3l3 3" /></>,
  abyss: <><path {...S} d="M8 2.4a5.6 5.6 0 1 1-5.6 5.6A4.2 4.2 0 0 1 8 4.9a3 3 0 0 1 3 3 2 2 0 0 1-3 1.7" /></>,
  /* Rẽ nhánh: một đường vào, hai đường ra — đúng hình người dùng vẽ trên giấy. */
  'confirm-mod': <><path {...S} d="M2 8h3.4M5.4 8L9 4.4M5.4 8L9 11.6" /><circle {...S} cx="11.2" cy="4.4" r="1.9" /><circle {...S} cx="11.2" cy="11.6" r="1.9" /></>,

  /* --- nút --- */
  target: <><circle {...S} cx="8" cy="8" r="5.6" /><circle {...S} cx="8" cy="8" r="2.1" /><path {...S} d="M8 .8v2.2M8 13v2.2M.8 8h2.2M13 8h2.2" /></>,
  frame: <><rect {...S} x="2" y="3" width="12" height="10" rx="1.4" /><path {...S} d="M2 10.4l3-2.8 2.6 2.4 2.4-2.2 3 2.6" /><circle {...S} cx="6" cy="6" r="1" /></>,
  grid: <><rect {...S} x="2" y="3.4" width="12" height="9.2" rx="1.2" /><path {...S} d="M6 3.4v9.2M10 3.4v9.2M2 6.5h12M2 9.5h12" /></>,
  trash: <><path {...S} d="M2.6 4.4h10.8M6 4.4V2.8h4v1.6M4 4.4l.8 9h6.4l.8-9" /><path {...S} d="M6.6 6.8v4.2M9.4 6.8v4.2" /></>,
  plus: <><path {...S} d="M8 3v10M3 8h10" /></>,
  ban: <><circle {...S} cx="8" cy="8" r="5.6" /><path {...S} d="M4 4l8 8" /></>,
  gear: <><circle {...S} cx="8" cy="8" r="4.9" /><circle {...S} cx="8" cy="8" r="1.9" /><g strokeWidth={2} stroke="currentColor" strokeLinecap="round"><path d="M8 1.3v1.4M8 13.3v1.4M14.7 8h-1.4M2.7 8H1.3" /><path d="M12.7 3.3l-1 1M4.3 11.7l-1 1M12.7 12.7l-1-1M4.3 4.3l-1-1" /></g></>,
  edit: <><path {...S} d="M9.8 3.2l3 3L6 13H3v-3z" /><path {...S} d="M8.4 4.6l3 3" /></>,
  loop: <><path {...S} d="M3 8a5 5 0 0 1 8.5-3.5M13 8a5 5 0 0 1-8.5 3.5" /><path {...S} d="M11.5 2.2v2.6H8.9M4.5 13.8v-2.6h2.6" /></>,
  up: <><path {...S} d="M8 12.6V3.6M4.2 7.4L8 3.6l3.8 3.8" /></>,

  /* --- menu chuột phải --- */
  copy: <><rect {...S} x="5.6" y="2.4" width="8" height="9.6" rx="1.3" /><path {...S} d="M10.6 14.2H3.7a1.3 1.3 0 0 1-1.3-1.3V5.2" /></>,
  paste: <><path {...S} d="M6 3.2H4.3a1.3 1.3 0 0 0-1.3 1.3v8.2a1.3 1.3 0 0 0 1.3 1.3h7.4a1.3 1.3 0 0 0 1.3-1.3V4.5a1.3 1.3 0 0 0-1.3-1.3H10" /><rect {...S} x="6" y="1.8" width="4" height="2.8" rx=".9" /></>,
  group: <><rect {...S} x="2.2" y="3.4" width="11.6" height="9.2" rx="1.4" /><path {...S} d="M4.8 6.4h6.4M4.8 8.6h6.4M4.8 10.8h3.6" /></>,
  action: <><path {...S} d="M9.4 1.8 4 9h3.3l-.8 5.2L11.9 7H8.6z" /></>,
  branch: <><path {...S} d="M1.8 8h3.9M5.7 8l3.1-3.1M5.7 8l3.1 3.1" /><circle {...S} cx="11.3" cy="4.9" r="1.8" /><circle {...S} cx="11.3" cy="11.1" r="1.8" /></>,
  folder: <><path {...S} d="M2 12.6V4.4a1 1 0 0 1 1-1h3.2l1.4 1.8H13a1 1 0 0 1 1 1v6.4a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1z" /></>,
  save: <><path {...S} d="M3.4 2.6h7.4L13.4 5.2v8.2a1 1 0 0 1-1 1H3.6a1 1 0 0 1-1-1V3.6a1 1 0 0 1 .8-1z" /><path {...S} d="M5.4 2.6v3.6h5V2.6M5.4 14.4V9.8h5.2v4.6" /></>,
  undo: <><path {...S} d="M6 5.2 2.8 8.4 6 11.6" /><path {...S} d="M2.8 8.4h6.4a3.6 3.6 0 0 1 0 7.2H7" /></>,
  redo: <><path {...S} d="m10 5.2 3.2 3.2L10 11.6" /><path {...S} d="M13.2 8.4H6.8a3.6 3.6 0 0 0 0 7.2H9" /></>,
  unlink: <><path {...S} d="M6.6 9.4 4.9 11a2.6 2.6 0 0 1-3.7-3.7l1.7-1.7M9.4 6.6 11 4.9a2.6 2.6 0 0 1 3.7 3.7L13 10.3" /><path {...S} d="M2 2l12 12" /></>,
  down: <><path {...S} d="M8 3.4v9M4.2 8.6L8 12.4l3.8-3.8" /></>,
}

export default function Icon({ name, size = 14 }: { name: string; size?: number }) {
  const h = HINH[name]
  if (!h) return null
  return (
    <svg viewBox="0 0 16 16" width={size} height={size} className="icon" aria-hidden>{h}</svg>
  )
}

/** Loại hành động -> tên icon. Web tự quyết VẼ GÌ; Python chỉ nói ĐÓ LÀ GÌ (`type`). */
export const ICON_HANH_DONG: Record<string, string> = {
  left_click: 'left-click',
  right_click: 'right-click',
  mod_click: 'mod-click',
  key_press: 'key-press',
  move_wasd: 'move-wasd',
  delay: 'delay',
  check_mod: 'check-mod',
  confirm_mod: 'confirm-mod',
  abyss: 'abyss',
}
