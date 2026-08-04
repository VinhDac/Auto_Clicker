import { useCallback, useEffect, useState } from 'react'
import { py } from '../api'
import type { Bootstrap, Step } from '../types'
import Modal from './Modal'
import ActionDialog from './ActionDialog'

/** Hộp thoại sửa 1 Loop / 1 Nhóm HĐ 1 lần — dựng lại bố cục "Sửa Action_Loop" cũ:
 *  hàng cấu hình trên cùng, danh sách hành động bên trái, cột nút bên phải.
 *
 *  Nhóm dùng CHUNG khung này, chỉ tắt bớt: không số vòng, không giữ Shift, không dấu
 *  "Loop từ đây" — vì nhóm chạy đúng 1 lượt nên mấy thứ đó vô nghĩa.
 */
export default function StepDialog({ step, boot, mods, onLuu, onDong }: {
  step: Step
  boot: Bootstrap
  mods: string[]
  onLuu: (s: Step) => void
  onDong: () => void
}) {
  const laLoop = step.kind === 'loop'
  const [s, setS] = useState<Step>(() => JSON.parse(JSON.stringify(step)))
  const [dong, setDong] = useState<string[]>([])
  const [chon, setChon] = useState(-1)
  const [suaHD, setSuaHD] = useState<{ i: number; a: Record<string, any> } | null>(null)

  const hd: Record<string, any>[] = (s.actions as Record<string, any>[]) ?? []
  const batDau = Math.max(0, Math.min(Number(s.loop_start_index ?? 0), hd.length))

  const lamMoi = useCallback(() => {
    py.describe_actions(hd).then(r => r.ok && setDong(r.value ?? []))
  }, [hd])
  useEffect(() => { lamMoi() }, [lamMoi])

  const dat = (k: string, v: unknown) => setS(x => ({ ...x, [k]: v }))
  const datHD = (x: Record<string, any>[]) => setS(o => ({ ...o, actions: x }))

  const giuPhim = String(s.hold_keys ?? '')

  async function them() {
    const r = await py.action_defaults('left_click')
    setSuaHD({ i: -1, a: r.value ?? { type: 'left_click' } })
  }
  function sua(i: number) { if (hd[i]) setSuaHD({ i, a: hd[i] }) }

  function luuHD(a: Record<string, any>) {
    if (!suaHD) return
    if (suaHD.i < 0) datHD([...hd, a])
    else datHD(hd.map((x, i) => (i === suaHD.i ? a : x)))
    setSuaHD(null)
  }

  function doiTen(i: number) {
    const a = hd[i]
    if (!a) return
    const moi = window.prompt('Tên hành động (để trống thì dùng mô tả tự sinh):', a.name ?? '')
    if (moi == null) return
    const x = { ...a }
    if (moi.trim()) x.name = moi.trim()
    else delete x.name
    datHD(hd.map((v, k) => (k === i ? x : v)))
  }

  function xoa(i: number) {
    if (i < 0) return
    datHD(hd.filter((_, k) => k !== i))
    // Xoá hành động NẰM TRƯỚC dấu "Loop từ đây" thì dấu phải lùi theo, nếu không
    // ranh giới chạy-1-lần / lặp âm thầm trượt sang hành động khác.
    if (i < batDau) dat('loop_start_index', Math.max(0, batDau - 1))
    setChon(-1)
  }

  function chuyen(i: number, huong: number) {
    const j = i + huong
    if (i < 0 || j < 0 || j >= hd.length) return
    const x = [...hd]
    ;[x[i], x[j]] = [x[j], x[i]]
    datHD(x)
    setChon(j)
  }

  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (suaHD) return
      const o = e.target as HTMLElement
      if (o && (o.tagName === 'INPUT' || o.tagName === 'SELECT')) return
      if (e.key === 'Delete') { e.preventDefault(); xoa(chon) }
      else if (e.key === 'F2') { e.preventDefault(); doiTen(chon) }
    }
    window.addEventListener('keydown', f)
    return () => window.removeEventListener('keydown', f)
  })

  return (
    <>
      <Modal title={laLoop ? 'Sửa Action_Loop' : 'Sửa Nhóm HĐ 1 lần'} width={640} onClose={onDong}
             footer={<>
               <span className="day" />
               <button className="nut" onClick={onDong}>Huỷ</button>
               <button className="nut chinh" onClick={() => onLuu(s)}>Lưu</button>
             </>}>
        {/* Ba thứ này nằm CÙNG MỘT HÀNG như bản tkinter — `o day` (rộng 100%) sẽ ép
            xuống dòng, nên ô tên dùng `co-gian` để chia phần còn lại. */}
        <div className="hang khong-xuong-dong">
          <label className="nhan-o">{laLoop ? 'Tên Loop:' : 'Tên nhóm:'}</label>
          <input className="o co-gian" value={String(s.name ?? '')}
                 onChange={e => dat('name', e.target.value)} />
          {laLoop && (
            <>
              <label className="nhan-o phu">Số vòng lặp:</label>
              <input className="o so" value={String(s.max_loops ?? boot.default_max_loops)}
                     onChange={e => dat('max_loops', e.target.value)} />
              <label className="tick ngang" style={{ marginLeft: 14 }}>
                <input type="checkbox" checked={!!giuPhim}
                       onChange={e => dat('hold_keys', e.target.checked ? 'shift' : '')} />
                ⇧ Giữ Shift suốt Loop
              </label>
            </>
          )}
        </div>

        <div className="tieu-de-phu">
          Hành động (double-click sửa • F2 đổi tên • Del xoá):
        </div>
        <div className="khung-hd">
          <div className="danh-sach cao-10">
            {dong.map((x, i) => (
              <div key={i}
                   className={'muc' + (i === chon ? ' chon' : '') + (laLoop && i < batDau ? ' mo' : '')}
                   onClick={() => setChon(i)} onDoubleClick={() => sua(i)}>
                <span className="danh-hd">{laLoop ? (i < batDau ? '1×' : '↻') : ''}</span>
                {x}{laLoop && i < batDau ? '   (1 lần)' : ''}
              </div>
            ))}
            {dong.length === 0 && <div className="muc mo">chưa có hành động nào</div>}
          </div>
          <div className="cot-nut">
            <button className="nut" onClick={them}>+ Thêm</button>
            <button className="nut" disabled={chon < 0} onClick={() => sua(chon)}>✏ Sửa</button>
            <button className="nut" disabled={chon < 0} onClick={() => doiTen(chon)}>🏷 Đổi tên</button>
            <button className="nut" disabled={chon < 0} onClick={() => xoa(chon)}>🗑 Xoá</button>
            <button className="nut" disabled={chon < 0} onClick={() => chuyen(chon, -1)}>⬆ Lên</button>
            <button className="nut" disabled={chon < 0} onClick={() => chuyen(chon, 1)}>⬇ Xuống</button>
            {laLoop && (
              <button className="nut" disabled={chon < 0} style={{ marginTop: 10 }}
                      onClick={() => dat('loop_start_index', chon)}>🔁 Loop từ đây</button>
            )}
          </div>
        </div>
        <div className="goi-y">
          {laLoop
            ? 'Xám + "(1 lần)" = chạy 1 lần lúc đầu  •  ↻ = lặp mỗi vòng  •  thêm "Kiểm tra mod" để Loop tự dừng khi ra mod'
            : 'Nhóm chạy đúng 1 lượt từ trên xuống, không lặp.'}
        </div>
      </Modal>

      {suaHD && (
        <ActionDialog action={suaHD.a} boot={boot} mods={mods}
                      onLuu={luuHD} onDong={() => setSuaHD(null)} />
      )}
    </>
  )
}
