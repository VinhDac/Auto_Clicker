import { useState } from 'react'
import { py } from '../api'
import type { Bootstrap } from '../types'
import Modal from './Modal'

/** ⚙ Cài đặt — dựng lại đúng bố cục hộp thoại cũ: Game, 4 ô số/phím, khung "Giao diện"
 *  (màu nhấn, đổi là thấy ngay), khung "Danh sách mod" (⟳ cập nhật từ mạng).
 *
 *  Đây là thứ app-wide, lưu vào settings.json bên cạnh exe — khác với template Process
 *  vốn lưu từng file riêng.
 */
export default function SettingsDialog({ boot, onLuu, onDong, doiMauNgay }: {
  boot: Bootstrap
  onLuu: (s: Record<string, unknown>) => void
  onDong: () => void
  doiMauNgay: (mau: string) => void
}) {
  const s = boot.settings as Record<string, any>
  const [game, setGame] = useState(String(s.game ?? 'poe2'))
  const [pre, setPre] = useState(String(s.pre_click_ms ?? 60))
  const [hover, setHover] = useState(String(s.hover_ms ?? 250))
  const [copy, setCopy] = useState(String(s.copy_keys ?? 'ctrl+c'))
  const [hotkey, setHotkey] = useState(String(s.stop_hotkey ?? 'f6'))
  const [accent, setAccent] = useState(String(s.accent ?? '#ffa657'))
  const [loi, setLoi] = useState<string | null>(null)
  const [tinMod, setTinMod] = useState('')

  function datMau(m: string) {
    setAccent(m)
    doiMauNgay(m)          // áp ngay, đúng như bản cũ: "(đổi là thấy ngay)"
  }

  async function capNhatMod() {
    setTinMod('Đang tải…')
    const r = await py.update_mods(game)
    setTinMod(r.ok ? `Đã cập nhật: ${r.value?.so_luong} mod` : `Lỗi: ${r.error}`)
  }

  async function luu() {
    const r = await py.save_settings({
      game, pre_click_ms: pre, hover_ms: hover,
      copy_keys: copy, stop_hotkey: hotkey, accent,
    })
    if (!r.ok) { setLoi(r.error ?? 'không lưu được'); return }
    onLuu(r.value as Record<string, unknown>)
  }

  return (
    <Modal title="⚙ Cài đặt" width={470} onClose={onDong}
           footer={<>
             {loi && <span className="loi-chan">{loi}</span>}
             <span className="day" />
             <button className="nut" onClick={onDong}>Huỷ</button>
             <button className="nut chinh" onClick={luu}>Lưu &amp; đóng</button>
           </>}>
      <div className="hang">
        <label className="nhan-o" style={{ width: 170 }}>Game:</label>
        <select className="o" value={game} onChange={e => setGame(e.target.value)}>
          {Object.entries(boot.games).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {([
        ['Delay trước click (ms):', pre, setPre],
        ['Chờ tooltip hiện (ms):', hover, setHover],
        ['Phím copy item:', copy, setCopy],
        ['Phím dừng khẩn:', hotkey, setHotkey],
      ] as [string, string, (v: string) => void][]).map(([nhan, v, dat]) => (
        <div className="hang" key={nhan}>
          <label className="nhan-o" style={{ width: 170 }}>{nhan}</label>
          <input className="o" style={{ width: 120 }} value={v}
                 onChange={e => dat(e.target.value)} spellCheck={false} />
        </div>
      ))}

      <fieldset className="khung-nhom">
        <legend>Giao diện</legend>
        <div className="hang">
          <label className="nhan-o">Màu nhấn:</label>
          <select className="o" value={accent}
                  onChange={e => datMau(e.target.value)}>
            {Object.entries(boot.accent_presets).map(([n, c]) => (
              <option key={c} value={c}>{n}</option>
            ))}
            {!Object.values(boot.accent_presets).includes(accent) &&
              <option value={accent}>Tuỳ chỉnh</option>}
          </select>
          <input type="color" className="o o-mau" value={accent}
                 onChange={e => datMau(e.target.value)} title="Tuỳ chọn…" />
        </div>
        <div className="goi-y">(đổi là thấy ngay)</div>
      </fieldset>

      <fieldset className="khung-nhom">
        <legend>Danh sách mod</legend>
        <div className="hang">
          <button className="nut" onClick={capNhatMod}>⟳ Cập nhật từ mạng</button>
          <span className="mo">{tinMod}</span>
        </div>
      </fieldset>
    </Modal>
  )
}
