import { useEffect, useMemo, useRef, useState } from 'react'
import { py } from '../api'
import type { Bootstrap } from '../types'
import Modal from './Modal'
import Icon from './Icon'

/** Hộp thoại sửa 1 hành động — dựng lại đúng bố cục của bản tkinter.
 *
 * Thứ tự trường, chữ nhãn, chữ gợi ý đều giữ nguyên: người dùng đã quen tay ở đó,
 * và họ nói rõ là muốn tái hiện y hệt trải nghiệm cũ.
 *
 * Luật hợp lệ KHÔNG nằm ở đây — bấm Lưu thì gửi bản thô sang `api.save_action`,
 * dùng chung `core.build_action` với hộp thoại tkinter.
 */

type Draft = Record<string, any>

const NHAN_HYBRID_MAC_DINH = 'any'
/** Danh sách mod có 3223 dòng. Vẽ hết ra DOM thì cuộn giật; cắt ở đây, và có ô tìm
 *  kiếm ngay trên nên không ai phải cuộn qua 3000 dòng. */
const TRAN_MOD = 300

function O({ nhan, children, rong }: { nhan?: string; children: React.ReactNode; rong?: boolean }) {
  return (
    <div className={'hang' + (rong ? ' rong' : '')}>
      {nhan !== undefined && <label className="nhan-o">{nhan}</label>}
      {children}
    </div>
  )
}

function Goi({ children }: { children: React.ReactNode }) {
  return <div className="goi-y">{children}</div>
}

export default function ActionDialog({ action, boot, mods, onLuu, onDong }: {
  action: Draft
  boot: Bootstrap
  mods: string[]
  onLuu: (a: Draft) => void
  onDong: () => void
}) {
  const [d, setD] = useState<Draft>(() => JSON.parse(JSON.stringify(action)))
  const [loi, setLoi] = useState<string | null>(null)
  const [tim, setTim] = useState('')
  const [modChon, setModChon] = useState<string | null>(null)
  const [tier, setTier] = useState('')
  const [hybrid, setHybrid] = useState(NHAN_HYBRID_MAC_DINH)
  const [nguong, setNguong] = useState('')
  const [dongCond, setDongCond] = useState<string[]>([])
  const [dongExcl, setDongExcl] = useState<string[]>([])
  const [chonCond, setChonCond] = useState(-1)
  const [chonExcl, setChonExcl] = useState(-1)
  const [keoCond, setKeoCond] = useState<number | null>(null)
  const oDauTien = useRef<HTMLInputElement>(null)

  const t: string = d.type
  const laDiem = boot.point_types.includes(t)
  const laMod = t === 'check_mod' || t === 'abyss'

  const dat = (k: string, v: unknown) => setD((x: Draft) => ({ ...x, [k]: v }))
  const datDiem = (i: number, v: string) =>
    setD((x: Draft) => {
      const p = [...(x.point ?? [0, 0])]
      p[i] = v
      return { ...x, point: p }
    })

  /* mô tả dòng điều kiện do Python sinh — JS không tự ghép chuỗi tier/hybrid */
  useEffect(() => {
    if (!laMod) return
    py.describe_conditions(d.conditions ?? [], t).then(r => r.ok && setDongCond(r.value ?? []))
  }, [d.conditions, t, laMod])
  useEffect(() => {
    if (t !== 'abyss') return
    py.describe_conditions(d.excludes ?? [], 'abyss').then(r => r.ok && setDongExcl(r.value ?? []))
  }, [d.excludes, t])

  useEffect(() => { oDauTien.current?.focus() }, [])

  /* DEL_COND — phím Delete xoá dòng đang chọn ở bảng điều kiện / loại trừ,
     giống hệt bản tkinter (cond_box và excl_box đều bind <Delete>). */
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      const o = e.target as HTMLElement
      if (o && (o.tagName === 'INPUT' || o.tagName === 'SELECT')) return
      if (e.key !== 'Delete') return
      if (chonExcl >= 0) {
        e.preventDefault()
        dat('excludes', (d.excludes ?? []).filter((_: unknown, i: number) => i !== chonExcl))
        setChonExcl(-1)
      } else if (chonCond >= 0) {
        e.preventDefault()
        dat('conditions', (d.conditions ?? []).filter((_: unknown, i: number) => i !== chonCond))
        setChonCond(-1)
      }
    }
    window.addEventListener('keydown', f)
    return () => window.removeEventListener('keydown', f)
  })

  /** DRAG_COND — kéo-thả đổi thứ tự điều kiện. Thứ tự Ở ĐÂY LÀ ƯU TIÊN: dòng trên
   *  được kiểm trước, khớp là dừng. Nên đổi thứ tự phải dễ như bản cũ. */
  function thaCond(dich: number) {
    if (keoCond === null || keoCond === dich) return
    const x = [...(d.conditions ?? [])]
    const [m] = x.splice(keoCond, 1)
    x.splice(dich, 0, m)
    dat('conditions', x)
    setChonCond(dich)
    setKeoCond(null)
  }

  const modLoc = useMemo(() => {
    const w = tim.trim().toLowerCase().split(/\s+/).filter(Boolean)
    if (!w.length) return mods.slice(0, TRAN_MOD)
    const ra: string[] = []
    for (const m of mods) {
      const ml = m.toLowerCase()
      if (w.every(x => ml.includes(x))) { ra.push(m); if (ra.length >= TRAN_MOD) break }
    }
    return ra
  }, [tim, mods])

  async function doiLoai(loai: string) {
    const r = await py.action_defaults(loai)
    // Giữ lại TÊN và TOẠ ĐỘ khi đổi loại: đổi từ Trái-click sang Phải-click mà mất
    // điểm vừa chọn thì rất bực.
    setD((x: Draft) => ({ ...(r.value ?? { type: loai }), name: x.name, point: x.point ?? (r.value as Draft)?.point }))
    setLoi(null)
  }

  async function chonDiem() {
    const r = await py.pick_point()
    if (r.ok && r.value) dat('point', [r.value[0], r.value[1]])
  }

  async function canKhungAbyss() {
    const r = await py.pick_abyss_frame(d.frame ?? null)
    if (r.ok && r.value) dat('frame', r.value)
  }

  async function canLuoi() {
    const r = await py.pick_inv_grid(d.grid?.frame ?? null, d.grid?.cells ?? null)
    if (r.ok && r.value) dat('grid', { frame: r.value.frame, cells: r.value.cells })
  }

  function themDieuKien() {
    if (!modChon) { setLoi('Hãy chọn 1 mod trong danh sách trước.'); return }
    const c: Draft = { mod: modChon }
    if (t === 'abyss') {
      if (nguong.trim()) {
        const v = Number(nguong.replace(',', '.'))
        if (Number.isNaN(v)) { setLoi('Ngưỡng phải là số (hoặc để trống).'); return }
        c.min_value = v
      }
    } else {
      c.tier = tier.trim() ? Number(tier) : null
      if (tier.trim() && Number.isNaN(c.tier)) { setLoi('Tier phải là số (hoặc để trống).'); return }
      if (hybrid !== NHAN_HYBRID_MAC_DINH) c.hybrid = hybrid
    }
    setLoi(null)
    dat('conditions', [...(d.conditions ?? []), c])
  }

  function themLoaiTru() {
    if (!modChon) { setLoi('Hãy chọn 1 mod trong danh sách trước.'); return }
    if ((d.excludes ?? []).some((e: Draft) => e.mod === modChon)) return
    dat('excludes', [...(d.excludes ?? []), { mod: modChon }])
  }

  function doiCho(ds: Draft[], i: number, huong: number) {
    const j = i + huong
    if (i < 0 || j < 0 || j >= ds.length) return null
    const x = [...ds]
    ;[x[i], x[j]] = [x[j], x[i]]
    return x
  }

  async function luu() {
    const r = await py.save_action(d)
    if (!r.ok) { setLoi(r.error ?? 'không lưu được'); return }
    onLuu(r.value!.action)
  }

  /* ------------------------------ khối dùng lại ------------------------------ */
  const oXY = (nhan = 'X:') => (
    <O nhan={nhan}>
      <input ref={oDauTien} className="o so" value={d.point?.[0] ?? ''}
             onChange={e => datDiem(0, e.target.value)} />
      <label className="nhan-o phu">Y:</label>
      <input className="o so" value={d.point?.[1] ?? ''} onChange={e => datDiem(1, e.target.value)} />
    </O>
  )
  const nutChonDiem = (
    <button className="nut day-ngang" onClick={chonDiem}><Icon name="target" /> Chọn điểm (crosshair)</button>
  )

  const bangMod = (
    <>
      <O nhan="Tìm mod:" rong>
        <input className="o day" value={tim} onChange={e => setTim(e.target.value)} spellCheck={false} />
      </O>
      <div className="danh-sach cao-5">
        {modLoc.map(m => (
          <div key={m} className={'muc' + (m === modChon ? ' chon' : '')}
               onClick={() => setModChon(m)} onDoubleClick={themDieuKien}>{m}</div>
        ))}
        {modLoc.length === 0 && <div className="muc mo">không có mod nào khớp</div>}
        {modLoc.length >= TRAN_MOD && <div className="muc mo">… gõ thêm để lọc hẹp lại</div>}
      </div>
    </>
  )

  const bangDieuKien = (
    <>
      <div className="tieu-de-phu">Điều kiện — dòng TRÊN ưu tiên trước (kéo-thả để đổi thứ tự):</div>
      <div className="danh-sach cao-4">
        {dongCond.map((s, i) => (
          <div key={i} draggable
               onDragStart={() => setKeoCond(i)}
               onDragOver={e => e.preventDefault()}
               onDrop={() => thaCond(i)}
               onDragEnd={() => setKeoCond(null)}
               className={'muc' + (i === chonCond ? ' chon' : '') + (keoCond === i ? ' dang-keo' : '')}
               onClick={() => setChonCond(i)}>{i + 1}.  {s}</div>
        ))}
        {dongCond.length === 0 && <div className="muc mo">chưa có điều kiện nào</div>}
      </div>
      <div className="hang">
        <button className="nut" disabled={chonCond < 0}
                onClick={() => { dat('conditions', (d.conditions ?? []).filter((_: unknown, i: number) => i !== chonCond)); setChonCond(-1) }}><Icon name="trash" /> Xoá</button>
        <button className="nut" disabled={chonCond < 0}
                onClick={() => { const x = doiCho(d.conditions ?? [], chonCond, -1); if (x) { dat('conditions', x); setChonCond(chonCond - 1) } }}><Icon name="up" /> Lên</button>
        <button className="nut" disabled={chonCond < 0}
                onClick={() => { const x = doiCho(d.conditions ?? [], chonCond, 1); if (x) { dat('conditions', x); setChonCond(chonCond + 1) } }}><Icon name="down" /> Xuống</button>
      </div>
    </>
  )

  /* --------------------------------- thân ---------------------------------- */
  let than: React.ReactNode = null

  if (laDiem) {
    const luoiBat = !!d.grid
    than = (
      <>
        <O nhan="X:">
          <input ref={oDauTien} className="o so" value={d.point?.[0] ?? ''} disabled={luoiBat}
                 onChange={e => datDiem(0, e.target.value)} />
          <label className="nhan-o phu">Y:</label>
          <input className="o so" value={d.point?.[1] ?? ''} disabled={luoiBat}
                 onChange={e => datDiem(1, e.target.value)} />
        </O>
        <button className="nut day-ngang" onClick={chonDiem} disabled={luoiBat}>
          <Icon name="target" /> Chọn điểm (crosshair)
        </button>
        {t === 'right_click' && (
          <>
            <hr className="vach" />
            <label className="tick">
              <input type="checkbox" checked={luoiBat}
                     onChange={e => dat('grid', e.target.checked ? { frame: null, cells: [] } : undefined)} />
              Nâng cao: lấy từ nhiều ô, hết ô này tự sang ô khác
            </label>
            <div className="hang">
              <button className="nut" onClick={canLuoi} disabled={!luoiBat}><Icon name="grid" /> Căn lưới</button>
              <span className="mo">
                {!luoiBat ? '(đang tắt — dùng đúng 1 điểm X/Y ở trên)'
                  : !d.grid?.frame ? 'chưa căn lưới'
                    : `(${d.grid.frame[0]}, ${d.grid.frame[1]}) ${d.grid.frame[2]}×${d.grid.frame[3]}  ·  đã tick ${d.grid.cells?.length ?? 0} ô`}
              </span>
            </div>
            <Goi>
              Tick sẵn những ô CHỨA ĐÚNG loại currency cần dùng.<br />
              App tự nhìn ô nào còn hàng — không đếm, không nhớ, nên bỏ thêm currency
              giữa chừng hay chạy lại đều đúng. Hết sạch thì DỪNG.
            </Goi>
          </>
        )}
      </>
    )
  } else if (t === 'mod_click') {
    const giu = String(d.keys ?? '').split('+').filter(Boolean)
    const doiGiu = (k: string, on: boolean) =>
      dat('keys', boot.mod_keys.filter(x => (x === k ? on : giu.includes(x))).join('+'))
    than = (
      <>
        <O nhan="Giữ phím:">
          {boot.mod_keys.map(k => (
            <label key={k} className="tick ngang">
              <input type="checkbox" checked={giu.includes(k)}
                     onChange={e => doiGiu(k, e.target.checked)} />
              {k === 'ctrl' ? 'Ctrl' : k === 'shift' ? 'Shift' : 'Alt'}
            </label>
          ))}
          <label className="nhan-o phu">Nút chuột:</label>
          <select className="o" value={d.button ?? 'left'} onChange={e => dat('button', e.target.value)}>
            <option value="left">Trái</option>
            <option value="right">Phải</option>
          </select>
        </O>
        <Goi>(tick được nhiều phím cùng lúc, vd Ctrl + Shift)</Goi>
        {oXY()}
        {nutChonDiem}
      </>
    )
  } else if (t === 'move_wasd') {
    const ks = String(d.keys ?? '').split('+').filter(Boolean)
    const NGUOC: Record<string, string> = { w: 's', s: 'w', a: 'd', d: 'a' }
    const doiHuong = (k: string, on: boolean) => {
      let x = ks.filter(v => v !== k && (!on || v !== NGUOC[k]))
      if (on) x = [...x, k]
      dat('keys', ['w', 's', 'a', 'd'].filter(v => x.includes(v)).join('+'))
    }
    const oTick = (k: string) => (
      <label className="tick wasd">
        <input type="checkbox" checked={ks.includes(k)} onChange={e => doiHuong(k, e.target.checked)} />
        {k.toUpperCase()}
      </label>
    )
    than = (
      <>
        <O nhan="Hướng đi:">
          <div className="ban-phim-wasd">
            <div>{oTick('w')}</div>
            <div>{oTick('a')}{oTick('s')}{oTick('d')}</div>
          </div>
        </O>
        <O nhan="Giữ trong:">
          <input className="o so" value={d.ms ?? ''} onChange={e => dat('ms', e.target.value)} />
          <span className="mo">ms</span>
        </O>
        <Goi>
          W/S và A/D ngược chiều nhau nên không tick cùng lúc được — tick cái này thì
          cái kia tự bỏ. Đang giữ mà bấm Dừng/F6 thì nhả ngay.
        </Goi>
      </>
    )
  } else if (t === 'key_press') {
    than = (
      <O nhan="Phím (vd: enter, a, space, escape):" rong>
        <input ref={oDauTien} className="o" style={{ width: 140 }} value={d.key ?? ''}
               onChange={e => dat('key', e.target.value)} spellCheck={false} />
      </O>
    )
  } else if (t === 'delay') {
    than = (
      <O nhan="Min ms:">
        <input ref={oDauTien} className="o so" value={d.min_ms ?? ''} onChange={e => dat('min_ms', e.target.value)} />
        <label className="nhan-o phu">Max ms:</label>
        <input className="o so" value={d.max_ms ?? ''} onChange={e => dat('max_ms', e.target.value)} />
      </O>
    )
  } else if (t === 'check_mod') {
    than = (
      <>
        <Goi>Item sẽ "biến mất" nếu khớp — dừng cả Loop, coi như đã đạt.</Goi>
        {oXY('Rê chuột tới item — X:')}
        {nutChonDiem}
        {bangMod}
        <O nhan="Tier (trống = mọi):">
          <input className="o so" value={tier} onChange={e => setTier(e.target.value)} />
          <label className="nhan-o phu">Loại mod:</label>
          <select className="o" value={hybrid} onChange={e => setHybrid(e.target.value)}>
            {Object.entries(boot.hybrid_labels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </O>
        <Goi>
          mod hybrid = 1 affix cho nhiều dòng stat (vd Armour + Energy Shield);<br />
          tier của họ hybrid KHÁC tier của mod thuần cùng tên
        </Goi>
        <button className="nut" onClick={themDieuKien}><Icon name="plus" /> Thêm điều kiện ↓</button>
        {bangDieuKien}
      </>
    )
  } else if (t === 'abyss') {
    than = (
      <>
        <Goi>
          Panel Abyss không Ctrl+C được → app ĐỌC CHỮ bằng ảnh.<br />
          Bấm REVEAL → quét 3 ô → khớp thì chọn ô đó + CONFIRM rồi DỪNG Loop;<br />
          không khớp thì bấm refresh (nếu có) → quét lại → vẫn không thì chọn bừa
          1 ô KHÔNG bị loại trừ + CONFIRM rồi chạy tiếp vòng sau.
        </Goi>
        {boot.ocr_reason && <div className="bao-loi">⚠ {boot.ocr_reason}</div>}
        <div className="hang">
          <button className="nut" onClick={canKhungAbyss}><Icon name="frame" /> Căn khung Abyss</button>
          <span className="mo">
            {d.frame ? `(${d.frame[0]}, ${d.frame[1]})  ${d.frame[2]}×${d.frame[3]}` : 'chưa căn khung'}
          </span>
        </div>
        <O nhan="Số lần reroll:">
          <input className="o so" value={d.rerolls ?? ''} onChange={e => dat('rerolls', e.target.value)} />
          <label className="nhan-o phu">Chờ sau mỗi lần bấm (ms):</label>
          <input className="o so" value={d.wait_ms ?? ''} onChange={e => dat('wait_ms', e.target.value)} />
        </O>
        {bangMod}
        <O nhan="Ngưỡng số tối thiểu (trống = mọi giá trị):">
          <input className="o so" value={nguong} onChange={e => setNguong(e.target.value)} />
        </O>
        <Goi>
          Panel Abyss KHÔNG hiện tier — dùng ngưỡng số thay cho tier.<br />
          Mod 2 số (vd "Adds # to # Chaos damage") so theo giá trị trung bình.
        </Goi>
        <div className="hang">
          <button className="nut" onClick={themDieuKien}><Icon name="plus" /> Thêm điều kiện ↓</button>
          <button className="nut" onClick={themLoaiTru}><Icon name="ban" /> Thêm vào loại trừ ↓</button>
        </div>
        {bangDieuKien}
        <div className="tieu-de-phu">
          Loại trừ — không bao giờ chốt mấy mod này, kể cả lúc phải chọn bừa:
        </div>
        <div className="danh-sach cao-4">
          {dongExcl.map((s, i) => (
            <div key={i} className={'muc' + (i === chonExcl ? ' chon' : '')}
                 onClick={() => setChonExcl(i)}>{i + 1}.  {s}</div>
          ))}
          {dongExcl.length === 0 && <div className="muc mo">chưa loại trừ mod nào</div>}
        </div>
        <div className="hang">
          <button className="nut" disabled={chonExcl < 0}
                  onClick={() => { dat('excludes', (d.excludes ?? []).filter((_: unknown, i: number) => i !== chonExcl)); setChonExcl(-1) }}><Icon name="trash" /> Xoá</button>
          <span className="mo">cả 3 ô đều bị loại trừ → reroll; hết reroll thì DỪNG, không chốt bừa</span>
        </div>
      </>
    )
  }

  return (
    <Modal title="Hành động" width={560} onClose={onDong}
           footer={<>
             {loi && <span className="loi-chan">{loi}</span>}
             <span className="day" />
             <button className="nut" onClick={onDong}>Huỷ</button>
             <button className="nut chinh" onClick={luu}>Lưu</button>
           </>}>
      <O nhan="Loại:" rong>
        <select className="o day" value={t} onChange={e => doiLoai(e.target.value)}>
          {boot.action_types.map(x => (
            <option key={x} value={x}>{boot.action_labels[x] ?? x}</option>
          ))}
        </select>
      </O>
      <O nhan="Tên:" rong>
        <input className="o day" value={d.name ?? ''} onChange={e => dat('name', e.target.value)}
               spellCheck={false} />
      </O>
      <Goi>(tuỳ chọn — để trống thì dùng mô tả tự sinh)</Goi>
      <hr className="vach" />
      {than}
    </Modal>
  )
}
