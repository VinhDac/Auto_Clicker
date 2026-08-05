import { useEffect, type ReactNode } from 'react'

/** Vỏ hộp thoại dùng chung.
 *
 * Bản tkinter từng dính lỗi hộp thoại "loé" lúc mở (dựng xong mới hiện mới hết) và
 * lỗi `ttk.Combobox` chiếm grab toàn cục làm treo cả máy. Ở web thì không có khái
 * niệm grab, và nội dung đã dựng xong trước khi trình duyệt vẽ — hai lớp lỗi đó
 * không tồn tại nữa.
 */
export default function Modal({ title, width = 560, onClose, footer, children, khoaEsc }: {
  title: string
  width?: number
  onClose: () => void
  footer?: ReactNode
  children: ReactNode
  /** Tạm khoá phím Esc.
   *
   *  Cần cho lúc "bấm phím để ghi": Escape là phím hay ghi nhất (đóng panel trong
   *  game), mà nó cũng là phím đóng hộp thoại. Không khoá thì bấm Esc để ghi lại
   *  thành đóng luôn hộp thoại — và ô nhập phím không bao giờ ghi được Escape.
   *
   *  Không sửa được bằng cách chặn ở nơi khác: listener của Modal gắn `capture:true`
   *  trên window từ lúc mở, nên nó luôn chạy TRƯỚC mọi listener đăng ký sau. */
  khoaEsc?: boolean
}) {
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (khoaEsc) return
      if (e.key === 'Escape') { e.stopPropagation(); onClose() }
    }
    window.addEventListener('keydown', f, true)
    return () => window.removeEventListener('keydown', f, true)
  }, [onClose, khoaEsc])

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
