import { useCallback, useEffect, useRef, useState } from 'react'
import { py } from '../api'
import ContextMenu, { type MucPhai } from './ContextMenu'

export interface NhomMenu { ten: string; muc: MucPhai[] }

/** Thanh tiêu đề tự vẽ.
 *
 *  Windows 10 không cho đổi màu thanh tiêu đề hệ thống (`DWMWA_CAPTION_COLOR` là của
 *  Win11, trên Win10 trả E_INVALIDARG — đã đo), nên muốn đúng màu app thì phải bỏ
 *  khung và tự vẽ. Toàn bộ tính năng cửa sổ được vá lại ở `khung_cua_so.py`.
 *
 *  KHÔNG có dòng JS nào lo việc KÉO cửa sổ: phía Python báo cho Windows rằng dải này
 *  là `HTCAPTION`, và Windows tự lo kéo, Aero Snap, double-click phóng to, chuột phải
 *  ra menu hệ thống. Việc duy nhất của component này là nói cho Python biết CHỖ NÀO
 *  không phải caption — logo, 4 menu, 3 nút — để chúng vẫn bấm được.
 */
export default function TitleBar({ tieuDe, menus }: { tieuDe: string; menus: NhomMenu[] }) {
  const [mo, setMo] = useState<{ i: number; x: number; y: number } | null>(null)
  const [phongTo, setPhongTo] = useState(false)
  const thanh = useRef<HTMLDivElement>(null)

  /** Báo Python các khoảng x KHÔNG được coi là caption.
   *
   *  Phải báo lại mỗi lần cửa sổ đổi kích thước: cụm 3 nút bám mép phải nên toạ độ
   *  của nó trôi theo. Không cập nhật thì bấm nút Đóng lại hoá ra kéo cửa sổ. */
  const baoVung = useCallback(() => {
    const e = thanh.current
    if (!e) return
    const vung = [...e.querySelectorAll('[data-khong-keo]')].map(k => {
      const r = k.getBoundingClientRect()
      return [Math.round(r.left), Math.round(r.right)]
    })
    py.vung_khong_keo(vung, Math.round(e.getBoundingClientRect().height))
  }, [])

  useEffect(() => {
    baoVung()
    const f = () => { baoVung(); py.cua_so_dang_phong_to().then(r => setPhongTo(!!r.value)) }
    window.addEventListener('resize', f)
    py.cua_so_dang_phong_to().then(r => setPhongTo(!!r.value))
    return () => window.removeEventListener('resize', f)
  }, [baoVung])
  // Chữ menu do người dùng đổi (tên Process) làm cụm trái rộng hẹp khác đi -> báo lại.
  useEffect(() => { baoVung() }, [menus, tieuDe, baoVung])

  const bamMenu = (i: number, e: React.MouseEvent<HTMLButtonElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    setMo(x => (x && x.i === i ? null : { i, x: r.left, y: r.bottom }))
  }

  return (
    <>
      <div className="thanh-tieu-de" ref={thanh}>
        <img className="logo-app" src="./favicon.ico" alt="" data-khong-keo />
        {menus.map((m, i) => (
          <button key={m.ten} data-khong-keo
                  className={'menu-tren' + (mo?.i === i ? ' dang-mo' : '')}
                  onClick={e => bamMenu(i, e)}
                  onMouseEnter={e => { if (mo) bamMenu(i, e) }}>
            {m.ten}
          </button>
        ))}
        {/* Khoảng giữa để trống CỐ Ý: đó chính là vùng kéo cửa sổ. */}
        <div className="ten-cua-so">{tieuDe}</div>
        <div className="nut-cua-so" data-khong-keo>
          <button className="nut-cs" title="Thu nhỏ"
                  onClick={() => py.cua_so_thu_nho()}>
            <svg width="10" height="10" viewBox="0 0 10 10"><path d="M0 5h10" stroke="currentColor" /></svg>
          </button>
          <button className="nut-cs" title={phongTo ? 'Khôi phục' : 'Phóng to'}
                  onClick={() => py.cua_so_phong_to().then(r => setPhongTo(!!r.value))}>
            {phongTo ? (
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor">
                <rect x="0.5" y="2.5" width="7" height="7" /><path d="M2.5 2.5V0.5h7v7h-2" />
              </svg>
            ) : (
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor">
                <rect x="0.5" y="0.5" width="9" height="9" />
              </svg>
            )}
          </button>
          <button className="nut-cs dong" title="Đóng"
                  onClick={() => py.cua_so_dong()}>
            <svg width="10" height="10" viewBox="0 0 10 10" stroke="currentColor">
              <path d="M0 0l10 10M10 0L0 10" />
            </svg>
          </button>
        </div>
      </div>

      {mo && (
        <ContextMenu x={mo.x} y={mo.y} muc={menus[mo.i].muc} onDong={() => setMo(null)} />
      )}
    </>
  )
}
