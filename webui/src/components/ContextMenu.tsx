import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import Icon from './Icon'

/** Menu chuột phải.
 *
 *  WebView2 đã tắt sẵn menu mặc định của trình duyệt (`AreDefaultContextMenusEnabled`
 *  bằng cờ debug, mà bản phát hành thì debug tắt) — nên chuột phải vốn không làm gì
 *  cả, và cái menu này không tranh chấp với thứ gì.
 */
export interface MucPhai {
  /** Đường kẻ ngăn nhóm. Có `ngan` thì các trường khác bị bỏ qua. */
  ngan?: boolean
  ten?: string
  icon?: string
  tat?: boolean
  /** Lý do bị mờ — hiện thành tooltip. Mờ mà không nói vì sao là bực nhất. */
  viSao?: string
  onClick?: () => void
  con?: MucPhai[]
}

export default function ContextMenu({ x, y, muc, onDong }: {
  x: number
  y: number
  muc: MucPhai[]
  onDong: () => void
}) {
  const boc = useRef<HTMLDivElement>(null)
  const [viTri, setViTri] = useState({ x, y })
  const [moCon, setMoCon] = useState<number | null>(null)

  // Kẹp vào trong cửa sổ SAU khi đã dựng xong: phải đo được thật rồi mới biết nó có
  // tràn ra ngoài không. Bấm phải sát mép phải/dưới là trường hợp thường gặp, không
  // phải ngoại lệ hiếm.
  useLayoutEffect(() => {
    const e = boc.current
    if (!e) return
    const r = e.getBoundingClientRect()
    const le = 6
    setViTri({
      x: Math.max(le, Math.min(x, window.innerWidth - r.width - le)),
      y: Math.max(le, Math.min(y, window.innerHeight - r.height - le)),
    })
  }, [x, y])

  useEffect(() => {
    const bamNgoai = (e: MouseEvent) => {
      if (!boc.current?.contains(e.target as globalThis.Node)) onDong()
    }
    const phim = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); onDong() } }
    // `mousedown` chứ không phải `click`: đóng ngay lúc nhấn xuống thì cú nhấn đó
    // không lọt xuống canvas thành ra vừa đóng menu vừa bỏ chọn khối.
    window.addEventListener('mousedown', bamNgoai, true)
    window.addEventListener('keydown', phim, true)
    window.addEventListener('resize', onDong)
    return () => {
      window.removeEventListener('mousedown', bamNgoai, true)
      window.removeEventListener('keydown', phim, true)
      window.removeEventListener('resize', onDong)
    }
  }, [onDong])

  const ve = (m: MucPhai, i: number, trongCon: boolean) => {
    if (m.ngan) return <div key={i} className="ngan-menu" />
    const coCon = !!m.con?.length
    return (
      <button
        key={i}
        className={'muc-phai' + (coCon ? ' co-con' : '')}
        disabled={m.tat}
        title={m.tat ? m.viSao : undefined}
        onMouseEnter={() => !trongCon && setMoCon(coCon ? i : null)}
        onClick={() => {
          if (m.tat || coCon) return
          m.onClick?.()
          onDong()
        }}
      >
        <span className="hinh-muc">{m.icon ? <Icon name={m.icon} size={13} /> : null}</span>
        <span className="chu-muc">{m.ten}</span>
        {coCon && <span className="mui-con">▸</span>}
        {coCon && moCon === i && (
          <div className="menu-con">
            {m.con!.map((c, k) => ve(c, k, true))}
          </div>
        )}
      </button>
    )
  }

  return (
    <div className="menu-phai" ref={boc}
         style={{ left: viTri.x, top: viTri.y }}
         onContextMenu={e => e.preventDefault()}>
      {muc.map((m, i) => ve(m, i, false))}
    </div>
  )
}
