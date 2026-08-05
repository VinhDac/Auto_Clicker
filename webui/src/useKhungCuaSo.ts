import { useEffect, useRef } from 'react'
import { py } from './api'

/** Bề dày vùng bắt kéo-giãn ở mép cửa sổ. Bằng đúng viền của cửa sổ Windows thường. */
const BIEN = 6

/** Mã vùng của Win32 — Windows dùng chính mấy số này để biết đang giãn cạnh nào. */
const HT = {
  trai: 10, phai: 11, tren: 12, trenTrai: 13, trenPhai: 14,
  duoi: 15, duoiTrai: 16, duoiPhai: 17, caption: 2,
} as const

const CON_TRO: Record<number, string> = {
  10: 'ew-resize', 11: 'ew-resize', 12: 'ns-resize', 15: 'ns-resize',
  13: 'nwse-resize', 17: 'nwse-resize', 14: 'nesw-resize', 16: 'nesw-resize',
}

/** Kéo và giãn cửa sổ, khi thanh tiêu đề do web tự vẽ.
 *
 *  VÌ SAO WEB PHẢI LÀM VIỆC NÀY, chứ không để Win32 lo:
 *  WebView2 là một cửa sổ CON phủ KÍN cửa sổ app (đo được: `Chrome_RenderWidgetHostHWND`
 *  đúng bằng kích thước cửa sổ). Windows hỏi cửa sổ nằm trên cùng dưới con trỏ, mà đó
 *  luôn là cửa sổ con ấy — cửa sổ cha KHÔNG BAO GIỜ được hỏi. Nên mọi cách vá
 *  `WM_NCHITTEST` ở phía cha đều trả lời một câu hỏi không ai đặt ra, và đó chính là
 *  lý do bản đầu tiên không kéo, không giãn, không snap được gì cả.
 *
 *  Web thì ngược lại: nó nhận được mọi sự kiện chuột. Nên web phát hiện "đang bấm ở
 *  mép / ở dải tiêu đề" rồi nhờ Python khởi động đúng thao tác của Windows. Từ lúc đó
 *  trở đi là vòng lặp kéo của chính hệ điều hành — Aero Snap, double-click phóng to,
 *  giãn theo cạnh đều đi kèm.
 */
export function useKhungCuaSo(caoTieuDe = 32) {
  const troCuoi = useRef('')
  const lanTruoc = useRef({ t: 0, x: 0, y: 0 })

  useEffect(() => {
    /** Điểm này thuộc mép nào của cửa sổ, hay không mép nào. */
    const mep = (x: number, y: number): number | null => {
      const w = window.innerWidth, h = window.innerHeight
      const tr = y < BIEN, du = y >= h - BIEN, tt = x < BIEN, ph = x >= w - BIEN
      if (tr && tt) return HT.trenTrai
      if (tr && ph) return HT.trenPhai
      if (du && tt) return HT.duoiTrai
      if (du && ph) return HT.duoiPhai
      if (tt) return HT.trai
      if (ph) return HT.phai
      if (tr) return HT.tren
      if (du) return HT.duoi
      return null
    }

    /** Chỗ này có phải vùng kéo của thanh tiêu đề không?
     *  `[data-khong-keo]` = logo, 4 menu, 3 nút — bấm vào chúng là bấm nút, không kéo. */
    const laVungKeo = (e: MouseEvent) =>
      e.clientY < caoTieuDe && !(e.target as HTMLElement)?.closest?.('[data-khong-keo]')

    const bamXuong = (e: MouseEvent) => {
      if (e.button !== 0) return
      const m = mep(e.clientX, e.clientY)
      if (m !== null) { e.preventDefault(); e.stopPropagation(); py.keo_cua_so(m); return }
      if (!laVungKeo(e)) return
      e.preventDefault()
      // TỰ nhận ra cú bấm đúp ngay tại mousedown, không chờ sự kiện `dblclick`:
      // cú bấm ĐẦU đã khởi động vòng kéo của Windows, mà vòng đó là modal và nuốt
      // luôn cú bấm thứ hai — trình duyệt không bao giờ thấy `dblclick` nữa.
      const gio = Date.now()
      const l = lanTruoc.current
      const dup = gio - l.t < 500                     // 500ms = mặc định của Windows
        && Math.abs(e.clientX - l.x) < 6 && Math.abs(e.clientY - l.y) < 6
      lanTruoc.current = { t: dup ? 0 : gio, x: e.clientX, y: e.clientY }
      if (dup) { py.cua_so_phong_to(); return }       // t=0 để bấm 3 lần không lật lại
      py.keo_cua_so(HT.caption)
    }

    // Con trỏ đổi hình ở mép, đúng như cửa sổ thường. Chỉ ghi khi ĐỔI — gán
    // style mỗi lần rê chuột là ép trình duyệt tính lại liên tục.
    const reChuot = (e: MouseEvent) => {
      const m = mep(e.clientX, e.clientY)
      const t = m === null ? '' : CON_TRO[m]
      if (t !== troCuoi.current) {
        troCuoi.current = t
        document.body.style.cursor = t
      }
    }

    // `capture: true` để chạy TRƯỚC React: bấm ở mép cửa sổ thì đó là thao tác giãn,
    // không được để nó rơi xuống thành cú bấm vào canvas phía dưới.
    window.addEventListener('mousedown', bamXuong, true)
    window.addEventListener('mousemove', reChuot, true)
    return () => {
      window.removeEventListener('mousedown', bamXuong, true)
      window.removeEventListener('mousemove', reChuot, true)
      document.body.style.cursor = ''
    }
  }, [caoTieuDe])
}
