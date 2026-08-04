import { useEffect, type ReactNode } from 'react'

/** Vỏ hộp thoại dùng chung.
 *
 * Bản tkinter từng dính lỗi hộp thoại "loé" lúc mở (dựng xong mới hiện mới hết) và
 * lỗi `ttk.Combobox` chiếm grab toàn cục làm treo cả máy. Ở web thì không có khái
 * niệm grab, và nội dung đã dựng xong trước khi trình duyệt vẽ — hai lớp lỗi đó
 * không tồn tại nữa.
 */
export default function Modal({ title, width = 560, onClose, footer, children }: {
  title: string
  width?: number
  onClose: () => void
  footer?: ReactNode
  children: ReactNode
}) {
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose() }
    }
    window.addEventListener('keydown', f, true)
    return () => window.removeEventListener('keydown', f, true)
  }, [onClose])

  return (
    <div className="lop-phu" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="hop-thoai" style={{ width }} onMouseDown={e => e.stopPropagation()}>
        <div className="ht-dau">
          <span>{title}</span>
          <button className="ht-dong" onClick={onClose} title="Đóng (Esc)">✕</button>
        </div>
        <div className="ht-than">{children}</div>
        <div className="ht-chan">{footer}</div>
      </div>
    </div>
  )
}
