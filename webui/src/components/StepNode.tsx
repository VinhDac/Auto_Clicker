import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { Card, StepKind } from '../types'
import IconNet, { ICON_HANH_DONG } from './Icon'

/** Số dòng hành động hiện tối đa trên một hộp.
 *
 * Yêu cầu là "nhìn hộp phải hiểu Loop này chạy những gì" — nhưng một Loop 40 hành động
 * mà vẽ hết thì hộp cao bằng cả màn hình và sơ đồ hết đọc được. Cắt ở đây rồi ghi rõ
 * còn bao nhiêu; muốn xem hết thì double-click mở hộp thoại.
 */
const TOI_DA_DONG = 8

const MAU: Record<StepKind, string> = {
  loop: 'var(--loop)',
  group: 'var(--group)',
  action: 'var(--action)',
}

const TEN_LOAI: Record<StepKind, string> = {
  loop: 'Action_Loop',
  group: 'Nhóm 1 lần',
  action: 'HĐ lẻ',
}

/** Icon vẽ bằng SVG, KHÔNG dùng emoji.
 *
 * Emoji hiện thành ô vuông ở nhiều chỗ trong bản tkinter (🔁 và ⚡ trong Listbox) vì
 * phụ thuộc font hệ thống. Vẽ hình thì không bao giờ dính chuyện đó nữa.
 */
function IconLoaiKhoi({ kind }: { kind: StepKind }) {
  const c = MAU[kind]
  if (kind === 'loop') {
    return (
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden>
        <path d="M3 8a5 5 0 0 1 8.5-3.5M13 8a5 5 0 0 1-8.5 3.5"
              stroke={c} strokeWidth="1.6" strokeLinecap="round" />
        <path d="M11.5 2.2v2.6H8.9M4.5 13.8v-2.6h2.6"
              stroke={c} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  if (kind === 'group') {
    return (
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden>
        <rect x="2.2" y="3" width="11.6" height="10" rx="1.6" stroke={c} strokeWidth="1.5" />
        <path d="M5 6.2h6M5 8.6h6M5 11h3.5" stroke={c} strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    )
  }
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M9 1.8 3.4 9.2h3.4l-.8 5 5.6-7.4H8.2z" stroke={c} strokeWidth="1.4"
            strokeLinejoin="round" />
    </svg>
  )
}

const SIDES: [string, Position][] = [
  ['top', Position.Top],
  ['right', Position.Right],
  ['bottom', Position.Bottom],
  ['left', Position.Left],
]

export default function StepNode({ data, selected }: NodeProps) {
  const card = (data as { card: Card }).card
  const thuTu = (data as { thuTu?: number }).thuTu
  const hien = card.lines.slice(0, TOI_DA_DONG)
  const con = card.lines.length - hien.length

  return (
    <>
      {/* 4 cổng ở giữa 4 cạnh — mỗi cạnh phải có CẢ source LẪN target.
          Chỉ đặt source thì kéo nối vẫn được (nhờ ConnectionMode.Loose) nhưng React
          Flow không phân giải nổi đầu ĐÍCH của một đường nối đã có, và vẽ ra mấy
          mẩu cụt bên cạnh hộp. Cái target trùng id, trùng vị trí, ẩn đi và không
          bắt chuột — nó chỉ cần TỒN TẠI để đường nối bám vào. */}
      {SIDES.map(([id, pos]) => (
        <Handle key={id} type="source" id={id} position={pos} />
      ))}
      {SIDES.map(([id, pos]) => (
        <Handle key={'t-' + id} type="target" id={id} position={pos}
                style={{ opacity: 0, pointerEvents: 'none' }} />
      ))}

      <div className={'hop' + (selected ? ' dang-chon' : '') + (thuTu ? '' : ' khong-toi')}>
        {/* Số THỨ TỰ CHẠY THẬT, do Python tính bằng chính phép duyệt của bộ máy.
            Không có số = đường nối không dẫn tới khối này, nó sẽ KHÔNG chạy —
            phải nhìn thấy được ngay, không thì lại rơi vào cảnh sơ đồ nói dối. */}
        <div className={'so-thu-tu' + (thuTu ? '' : ' trong')}
             title={thuTu ? `Chạy thứ ${thuTu}` : 'Không có đường nối dẫn tới — sẽ không chạy'}>
          {thuTu ?? '–'}
        </div>
        <div className="dau">
          <span className="dai-mau" style={{ background: MAU[card.kind] }} />
          <IconLoaiKhoi kind={card.kind} />
          <span className="ten" title={card.title}>{card.title}</span>
          <span className="loai">{TEN_LOAI[card.kind]}</span>
        </div>

        <div className="than">
          {hien.length === 0 && <div className="dong rong">chưa có hành động nào</div>}
          {hien.map((d, i) => (
            <div key={i}
                 className={'dong' + (d.prologue ? ' mo-dau' : '') + (d.goal ? ' muc-tieu' : '')}
                 title={d.text}>
              <span className="danh">{d.prologue ? '1×' : card.kind === 'loop' ? '↻' : ''}</span>
              <IconNet name={ICON_HANH_DONG[d.type ?? ''] ?? ''} size={12} />
              <span>{d.text}</span>
            </div>
          ))}
          {con > 0 && (
            <div className="dong con-nua">
              <span className="danh" /><span>… còn {con} hành động</span>
            </div>
          )}
        </div>

        {card.badges.length > 0 && (
          <div className="chan">
            {card.badges.map((b, i) => <span key={i} className="the">{b}</span>)}
            {card.co_muc_tieu && <span className="the muc-tieu">có mục tiêu</span>}
          </div>
        )}
      </div>
    </>
  )
}
