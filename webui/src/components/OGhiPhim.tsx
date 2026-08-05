import { useEffect, useRef, useState } from 'react'
import { py } from '../api'

/** Ô nhập tên phím + nút "bấm phím để ghi".
 *
 *  Dùng chung cho hành động "Nhấn phím" và cho phím dừng khẩn trong Cài đặt. Hai chỗ
 *  cùng một vấn đề: bắt người dùng nhớ và gõ đúng tên phím theo cách gọi của pyautogui
 *  ("escape", "pagedown", "num1"), trong khi họ có sẵn cái bàn phím ngay trước mặt.
 *
 *  BẮT BUỘC nghe ở tầng `capture` và chặn đứng sự kiện: phím hay ghi nhất lại đúng là
 *  mấy phím đã có nghĩa sẵn trong app (Escape đóng hộp thoại, Tab nhảy ô, Enter bấm
 *  nút mặc định). Riêng Escape còn phải khoá thêm ở Modal — listener của Modal đăng ký
 *  từ lúc mở nên luôn chạy TRƯỚC listener này; đó là việc của `onDangGhi`.
 *
 *  Quy đổi tên phím do `core.key_from_browser` làm, không phải JS: phím chạy được hay
 *  không là do pyautogui quyết, mà chỉ Python nhìn thấy nó.
 */
export default function OGhiPhim({ giaTri, onDoi, onDangGhi, rong = 140, oRef }: {
  giaTri: string
  onDoi: (v: string) => void
  /** Báo lên cha để cha khoá phím Esc ở Modal của nó suốt lúc đang chờ ghi. */
  onDangGhi?: (b: boolean) => void
  rong?: number
  oRef?: React.RefObject<HTMLInputElement>
}) {
  const [dangGhi, setDangGhi] = useState(false)
  const [loi, setLoi] = useState('')

  // Giữ callback trong ref: cha hay truyền hàm mũi tên viết thẳng, mỗi lần render lại
  // là một hàm mới. Cho thẳng vào mảng phụ thuộc thì effect chạy lại mỗi lần render,
  // gỡ ra gắn vào listener liên tục — vô ích và dễ hụt đúng lúc đang chờ phím.
  const baoRa = useRef(onDangGhi)
  const doiRa = useRef(onDoi)
  baoRa.current = onDangGhi
  doiRa.current = onDoi

  useEffect(() => { baoRa.current?.(dangGhi) }, [dangGhi])

  useEffect(() => {
    if (!dangGhi) return
    const f = (e: KeyboardEvent) => {
      // Phím bổ trợ bấm một mình thì bỏ qua: giữ Shift rồi mới bấm phím thật là thói
      // quen bình thường, ghi luôn "shift" là cướp mất cú bấm.
      if (['Shift', 'Control', 'Alt', 'Meta'].includes(e.key)) return
      e.preventDefault()
      e.stopPropagation()
      setDangGhi(false)
      py.ghi_phim(e.key, e.code).then(r => {
        if (r.ok && r.value) { doiRa.current(r.value); setLoi('') }
        else setLoi(r.error ?? 'không ghi được phím')
      })
    }
    window.addEventListener('keydown', f, true)
    return () => window.removeEventListener('keydown', f, true)
  }, [dangGhi])

  return (
    <>
      <input ref={oRef} className="o" style={{ width: rong }} value={giaTri}
             onChange={e => { onDoi(e.target.value); setLoi('') }} spellCheck={false} />
      <button className={'nut' + (dangGhi ? ' chinh' : '')} style={{ marginLeft: 8 }}
              onClick={() => { setLoi(''); setDangGhi(x => !x) }}>
        {dangGhi ? '⌨ Đang chờ… bấm một phím' : '⌨ Bấm phím để ghi'}
      </button>
      {loi && <span className="loi-ghi">{loi}</span>}
    </>
  )
}
