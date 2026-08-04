import type { ReactNode } from 'react'

/** Thanh công cụ kiểu ribbon của Paint: nút nhóm lại, nhãn nhóm nằm DƯỚI, có vạch
 *  ngăn giữa các nhóm. Mọi thứ "thêm vào" nằm ở trên; canvas phía dưới chỉ để di
 *  chuyển và nối. */

function Nhom({ ten, children }: { ten: string; children: ReactNode }) {
  return (
    <div className="nhom-ribbon">
      <div className="cac-nut">{children}</div>
      <div className="ten-nhom">{ten}</div>
    </div>
  )
}

function Nut({ ten, icon, onClick, tat, title }: {
  ten: string; icon: ReactNode; onClick?: () => void; tat?: boolean; title?: string
}) {
  return (
    <button className="nut-lon" onClick={onClick} disabled={tat} title={title || ten}>
      <span className="hinh">{icon}</span>
      <span>{ten}</span>
    </button>
  )
}

const S = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

const I = {
  loop: <svg viewBox="0 0 22 22" width="22" height="22"><path {...S} d="M4 11a7 7 0 0 1 11.9-5M18 11a7 7 0 0 1-11.9 5" /><path {...S} d="M15.5 3v3.4h-3.2M6.5 19v-3.4h3.2" /></svg>,
  group: <svg viewBox="0 0 22 22" width="22" height="22"><rect {...S} x="3" y="4.5" width="16" height="13" rx="2" /><path {...S} d="M6.5 8.5h9M6.5 11.5h9M6.5 14.5h5" /></svg>,
  action: <svg viewBox="0 0 22 22" width="22" height="22"><path {...S} d="M12.5 2.5 5 12.5h4.6L8.5 19.5 16 9.5h-4.6z" /></svg>,
  rename: <svg viewBox="0 0 22 22" width="22" height="22"><path {...S} d="M13.5 4.5l4 4L8 18H4v-4z" /><path {...S} d="M11.5 6.5l4 4" /></svg>,
  copy: <svg viewBox="0 0 22 22" width="22" height="22"><rect {...S} x="7" y="7" width="11" height="11" rx="1.8" /><path {...S} d="M14.5 4.5H5.8A1.3 1.3 0 0 0 4.5 5.8v8.7" /></svg>,
  del: <svg viewBox="0 0 22 22" width="22" height="22"><path {...S} d="M4.5 6.5h13M9 6.5V4.5h4v2M6.5 6.5l1 12h7l1-12" /><path {...S} d="M9.5 9.5v6M12.5 9.5v6" /></svg>,
  undo: <svg viewBox="0 0 22 22" width="22" height="22"><path {...S} d="M6 9.5H14a4.5 4.5 0 0 1 0 9h-3" /><path {...S} d="M9 6l-3.5 3.5L9 13" /></svg>,
  redo: <svg viewBox="0 0 22 22" width="22" height="22"><path {...S} d="M16 9.5H8a4.5 4.5 0 0 0 0 9h3" /><path {...S} d="M13 6l3.5 3.5L13 13" /></svg>,
  save: <svg viewBox="0 0 22 22" width="22" height="22"><path {...S} d="M4.5 5.8A1.3 1.3 0 0 1 5.8 4.5h8.4l3.3 3.3v8.4a1.3 1.3 0 0 1-1.3 1.3H5.8a1.3 1.3 0 0 1-1.3-1.3z" /><path {...S} d="M7.5 4.5v4h6v-4M7.5 17.5v-4h7v4" /></svg>,
  open: <svg viewBox="0 0 22 22" width="22" height="22"><path {...S} d="M3.5 17V6.5A1 1 0 0 1 4.5 5.5h4l2 2.2h6a1 1 0 0 1 1 1V17z" /><path {...S} d="M3.5 17l2.6-6h13l-2.6 6z" /></svg>,
  fit: <svg viewBox="0 0 22 22" width="22" height="22"><path {...S} d="M4 8V4.5h3.5M18 8V4.5h-3.5M4 14v3.5h3.5M18 14v3.5h-3.5" /><rect {...S} x="8" y="8" width="6" height="6" rx="1" /></svg>,
}

export interface RibbonProps {
  themLoop: () => void
  themNhom: () => void
  themHanhDong: () => void
  doiTen: () => void
  nhanBan: () => void
  xoa: () => void
  hoanTac: () => void
  lamLai: () => void
  luu: () => void
  mo: () => void
  vuaManHinh: () => void
  coChon: boolean
  coTheHoanTac: boolean
  coTheLamLai: boolean
}

export default function Ribbon(p: RibbonProps) {
  return (
    <div className="ribbon">
      <Nhom ten="Thêm khối">
        <Nut ten="Loop" icon={I.loop} onClick={p.themLoop} title="Thêm Action_Loop (lặp)" />
        <Nut ten="Nhóm" icon={I.group} onClick={p.themNhom} title="Thêm Nhóm HĐ 1 lần" />
        <Nut ten="HĐ lẻ" icon={I.action} onClick={p.themHanhDong} title="Thêm 1 hành động lẻ" />
      </Nhom>

      <Nhom ten="Sửa">
        <Nut ten="Đổi tên" icon={I.rename} onClick={p.doiTen} tat={!p.coChon} title="Đổi tên khối đang chọn (F2)" />
        <Nut ten="Nhân bản" icon={I.copy} onClick={p.nhanBan} tat={!p.coChon} title="Nhân bản khối đang chọn (Ctrl+D)" />
        <Nut ten="Xoá" icon={I.del} onClick={p.xoa} tat={!p.coChon} title="Xoá khối đang chọn (Delete)" />
      </Nhom>

      <Nhom ten="Hoàn tác">
        <Nut ten="Hoàn tác" icon={I.undo} onClick={p.hoanTac} tat={!p.coTheHoanTac} title="Ctrl+Z" />
        <Nut ten="Làm lại" icon={I.redo} onClick={p.lamLai} tat={!p.coTheLamLai} title="Ctrl+Y" />
      </Nhom>

      <Nhom ten="Template">
        <Nut ten="Lưu" icon={I.save} onClick={p.luu} title="Lưu Process thành template" />
        <Nut ten="Mở" icon={I.open} onClick={p.mo} title="Mở template Process" />
      </Nhom>

      <Nhom ten="Xem">
        <Nut ten="Vừa khung" icon={I.fit} onClick={p.vuaManHinh} title="Thu phóng cho vừa toàn bộ sơ đồ" />
      </Nhom>
    </div>
  )
}
